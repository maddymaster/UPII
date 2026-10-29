"""Local HTTP API over UPII's retrieval stack, so a web app can use it without the CLI.

Everything runs in-process against the same code paths as the CLI: the shared
ingestion pipeline, the fusion rehydrator (via ``SearchEngine``), ``LocalLLM`` and the
approval inbox (``upii.ambient.inbox``). Nothing shells out.

Sovereignty and safety defaults:

- binds to 127.0.0.1 (see ``upii serve``) and answers only requests whose Host header
  is loopback, which blocks DNS-rebinding pages from reaching the API through the
  browser; extra hosts come from ``UPII_ALLOWED_HOSTS``;
- ``UPII_API_KEY`` set -> every request must carry it in ``X-API-Key``;
- CORS is off unless ``UPII_ALLOWED_ORIGINS`` lists origins;
- /ask answers locally by default (``local_only: true``) and returns 503 rather than
  falling back to a mock or a cloud model; a remote model is reachable only when the
  client sends ``local_only: false`` AND the server's ``llm_provider`` is ``remote``
  (a GEMINI_API_KEY alone never switches to remote);
- every request is appended to the existing audit trail (``audit_logs`` in
  staging.db, source ``api``) with the endpoint, status and a SHA-256 of the query,
  never the query, document text or key.

Errors always have the shape ``{"error": "<code>", "detail": "<message>"}``.
"""
import hashlib
import hmac
import json
import logging
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from upii import __version__
from upii.core.config import config

logger = logging.getLogger("upii.api")

LOOPBACK_HOSTS = ["127.0.0.1", "localhost", "::1", "[::1]"]
_STATUS_RE = re.compile(r"^\s*(READY|OK|WARN|FAIL)\b[:\s]*(.*)$", re.DOTALL)
_HTTP_ERROR_CODES = {400: "bad_request", 401: "unauthorized", 403: "forbidden",
                     404: "not_found", 405: "method_not_allowed", 409: "conflict"}


class APIError(Exception):
    """Raised by handlers; rendered as ``{"error": code, "detail": detail}``."""

    def __init__(self, status_code: int, error: str, detail: str):
        self.status_code, self.error, self.detail = status_code, error, detail


# -- request bodies -----------------------------------------------------------
class IngestRequest(BaseModel):
    path: str = Field(..., min_length=1)
    recursive: bool = True
    background: bool = False


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    limit: int = Field(10, ge=1, le=100)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1)
    no_answer: bool = False
    local_only: bool = True
    debug: bool = False


# -- helpers ------------------------------------------------------------------
def _env_list(name: str) -> List[str]:
    return [v.strip() for v in os.environ.get(name, "").split(",") if v.strip()]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _host_only(host_header: str) -> str:
    """``"[::1]:8765"`` -> ``"[::1]"``, ``"localhost:8765"`` -> ``"localhost"``."""
    if host_header.startswith("["):
        return host_header[: host_header.find("]") + 1]
    return host_header.split(":")[0]


def _parse_check(result: str) -> Dict[str, str]:
    """``"OK (5 vectors)"`` -> ``{"status": "OK", "detail": "(5 vectors)"}``."""
    m = _STATUS_RE.match(str(result))
    if not m:
        return {"status": "FAIL", "detail": str(result)}
    return {"status": m.group(1), "detail": m.group(2).strip()}


def _overall(statuses: List[str]) -> str:
    for level in ("FAIL", "WARN", "READY"):
        if level in statuses:
            return level
    return "OK"


def _scores(r) -> Dict[str, float]:
    signals = getattr(r, "signals", None) or {}
    return {
        "semantic": round(float(signals.get("semantic", 0.0)), 6),
        "temporal": round(float(signals.get("temporal", 0.0)), 6),
        "relational": round(float(signals.get("relational", 0.0)), 6),
        "fused": round(float(getattr(r, "score", 0.0)), 6),
    }


def _gemini_key_configured() -> bool:
    key = getattr(config, "gemini_api_key", None)
    return bool(key and key not in ("", "YOUR_API_KEY"))


def _note(request: Request, query: Optional[str] = None, results: Optional[int] = None, **extra) -> None:
    """Attach audit fields to this request; the audit middleware writes them."""
    audit = {}
    if query is not None:
        audit["query_sha256"] = _sha256(query)
    if results is not None:
        audit["results"] = results
    audit.update(extra)
    request.state.audit = audit


def use_data_dir(path: str) -> str:
    """Make ``path`` the memory folder, exactly as if ``upii`` had been started there.

    The config singleton is loaded from the CWD at import time, so this changes into
    the folder, reloads ``.upii_config.yaml`` from it into the same object every
    module already holds, and pins the store paths as absolute.
    """
    from dataclasses import fields

    from upii.core.config import Config

    root = os.path.abspath(os.path.expanduser(path))
    os.makedirs(root, exist_ok=True)
    os.chdir(root)
    fresh = Config.load()
    for f in fields(Config):
        setattr(config, f.name, getattr(fresh, f.name))
    for name in ("db_path", "vector_store_path", "staging_db_path"):
        setattr(config, name, os.path.abspath(getattr(config, name)))
    return root


# -- app ----------------------------------------------------------------------
def create_app(allowed_hosts: Optional[List[str]] = None) -> FastAPI:
    """Build the API. Security settings are read from the environment here, once."""
    api_key = os.environ.get("UPII_API_KEY") or None
    origins = _env_list("UPII_ALLOWED_ORIGINS")
    hosts = set(LOOPBACK_HOSTS + (allowed_hosts or []) + _env_list("UPII_ALLOWED_HOSTS"))

    app = FastAPI(title="UPII local API", version=__version__)

    write_lock = threading.Lock()  # one writer at a time into SQLite + LanceDB
    jobs: Dict[str, Dict] = {}
    jobs_lock = threading.Lock()
    staging_ready = set()

    def staging():
        from upii.ambient.storage import StagingDB

        stg = StagingDB()
        if stg.db_path not in staging_ready:
            stg.init_db()
            staging_ready.add(stg.db_path)
        return stg

    def write_audit(action: str, details: Dict) -> None:
        try:
            staging().log_audit("api", action, details)
        except Exception as e:  # auditing must never break a request
            logger.warning("API audit write failed: %s", type(e).__name__)

    # -- errors -----------------------------------------------------------
    def error(status_code: int, code: str, detail: str) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"error": code, "detail": detail})

    @app.exception_handler(APIError)
    async def _api_error(request: Request, exc: APIError):
        return error(exc.status_code, exc.error, exc.detail)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        return error(exc.status_code, _HTTP_ERROR_CODES.get(exc.status_code, "http_error"), str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        # Location + message only: echoing the input could put a question in a log.
        msgs = ["{}: {}".format(".".join(str(p) for p in e.get("loc", ())), e.get("msg", "invalid"))
                for e in exc.errors()]
        return error(422, "validation_error", "; ".join(msgs))

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        return error(500, "internal_error", f"{type(exc).__name__}: {exc}")

    # -- middleware (last added runs first) -------------------------------
    @app.middleware("http")
    async def audit_requests(request: Request, call_next):
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            if request.method != "OPTIONS":
                route = request.scope.get("route")
                endpoint = getattr(route, "path", None) or "unmatched"
                details = {"method": request.method, "endpoint": endpoint, "status": status}
                details.update(getattr(request.state, "audit", None) or {})
                await run_in_threadpool(write_audit, f"{request.method} {endpoint}", details)

    @app.middleware("http")
    async def loopback_host_guard(request: Request, call_next):
        if _host_only(request.headers.get("host", "")) not in hosts:
            return error(400, "invalid_host", "Host header not allowed; see UPII_ALLOWED_HOSTS")
        return await call_next(request)

    if origins:  # outermost, so error responses carry CORS headers too
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "X-API-Key"],
        )

    def require_key(request: Request) -> None:
        if api_key is None:
            return
        sent = request.headers.get("x-api-key", "")
        if not hmac.compare_digest(sent.encode("utf-8"), api_key.encode("utf-8")):
            raise APIError(401, "unauthorized", "Missing or invalid X-API-Key header")

    auth = [Depends(require_key)]

    # -- shared work ------------------------------------------------------
    def retrieve(query: str, limit: int):
        from upii.analysis.search import SearchEngine

        try:
            return SearchEngine().search(query, limit=limit)
        except Exception as e:
            raise APIError(500, "retrieval_failed", f"{type(e).__name__}: {e}")

    def document_index(results) -> Dict[str, Dict]:
        from upii.storage.db import DB

        db, out = DB(), {}
        for r in results:
            if r.doc_hash not in out:
                try:
                    out[r.doc_hash] = db.get_document_by_id(r.doc_hash) or {}
                except Exception:
                    out[r.doc_hash] = {}
        return out

    def run_ingest(root: str, recursive: bool, progress: Optional[Dict] = None) -> Dict:
        from upii.analysis.embeddings import Embedder
        from upii.ingestion.chunker import RecursiveChunker
        from upii.ingestion.loader import LocalLoader
        from upii.ingestion.pipeline import ingest_documents
        from upii.storage.db import DB
        from upii.storage.vector import LocalVectorStore

        docs = LocalLoader().load(root)
        if os.path.isdir(root) and not recursive:
            top = os.path.normcase(root)
            docs = (d for d in docs if os.path.normcase(os.path.dirname(os.path.abspath(d.path))) == top)

        try:
            from upii.analysis.nlp import TaskExtractor

            extractor = TaskExtractor()
        except Exception:
            extractor = None
        files: List[Dict] = []

        def tick():
            if progress is not None:
                progress["processed"] = len(files)

        with write_lock:
            db = DB()
            db.init_db()

            def on_result(res):
                entry = {
                    "path": res.doc_path,
                    "status": res.status,
                    "document_hash": res.content_hash,
                    "chunks": res.n_chunks,
                }
                if res.status == "updated":
                    entry["removed_chunks"] = res.removed_chunks
                files.append(entry)
                tick()
                if res.chunks and extractor is not None:
                    # Parity with `upii ingest`: pull tasks out of newly stored chunks.
                    try:
                        tasks = extractor.extract(res.chunks)
                        if tasks:
                            db.add_tasks(tasks)
                    except Exception:
                        pass

            def on_error(doc, exc):
                files.append({"path": doc.path, "status": "error",
                              "document_hash": getattr(doc, "content_hash", None),
                              "chunks": 0, "error": f"{type(exc).__name__}: {exc}"})
                tick()

            ingest_documents(docs, db, LocalVectorStore(), Embedder(), RecursiveChunker(),
                             on_result=on_result, on_error=on_error)

        if not files:
            raise APIError(422, "no_supported_files",
                           f"No supported files (.md, .txt, .pdf; .mbox only by direct path) under {root}")

        counts = {s: sum(1 for f in files if f["status"] == s)
                  for s in ("ingested", "updated", "skipped", "error")}
        stored = counts["ingested"] + counts["updated"]
        if stored:
            try:
                from upii.analysis.metrics import MetricsCollector

                MetricsCollector().track_explicit_ingest(stored)
            except Exception:
                pass
        return {"path": root, "recursive": recursive, "summary": counts, "files": files}

    def run_job(job_id: str, root: str, recursive: bool) -> None:
        job = jobs[job_id]
        try:
            result = run_ingest(root, recursive, progress=job["progress"])
            update = {"status": "done", "result": result}
        except APIError as e:
            update = {"status": "failed", "error": {"error": e.error, "detail": e.detail}}
        except Exception as e:
            update = {"status": "failed", "error": {"error": "ingest_failed", "detail": f"{type(e).__name__}: {e}"}}
        update["finished_at"] = datetime.now(timezone.utc).isoformat()
        with jobs_lock:
            job.update(update)
        write_audit("job ingest", {"job_id": job_id, "status": update["status"],
                                   "files": len((update.get("result") or {}).get("files", []))})

    # -- endpoints --------------------------------------------------------
    @app.get("/health", dependencies=auth)
    def health():
        from upii.analysis.diagnostics import Doctor

        checks = {name: _parse_check(res) for name, res in Doctor().check_all().items()}
        return {
            "status": _overall([c["status"] for c in checks.values()]),
            "version": __version__,
            "checks": checks,
            "answer_model": {
                # /ask uses "local" unless a request sends local_only=false, in which
                # case it uses the configured provider.
                "default": "local",
                "configured_provider": config.llm_provider,
                "local": {"provider": "ollama", "name": config.llm_model,
                          "status": checks.get("model", {}).get("status")},
                "remote": {"provider": "gemini", "name": config.gemini_model,
                           "key_configured": _gemini_key_configured(),
                           "enabled": config.llm_provider == "remote"},
            },
        }

    @app.post("/ingest", dependencies=auth)
    def ingest(req: IngestRequest, request: Request):
        _note(request, query=req.path)
        root = os.path.abspath(os.path.expanduser(req.path))
        if not os.path.exists(root):
            raise APIError(400, "path_not_found", f"Path does not exist on the server: {req.path}")

        if req.background:
            job_id = uuid.uuid4().hex
            with jobs_lock:
                jobs[job_id] = {"job_id": job_id, "status": "running", "path": root,
                                "recursive": req.recursive, "progress": {"processed": 0},
                                "started_at": datetime.now(timezone.utc).isoformat()}
            threading.Thread(target=run_job, args=(job_id, root, req.recursive), daemon=True).start()
            _note(request, query=req.path, job_id=job_id)
            return JSONResponse(status_code=202, content={
                "job_id": job_id, "status": "running", "status_url": f"/ingest/jobs/{job_id}"})

        body = run_ingest(root, req.recursive)
        _note(request, query=req.path, results=len(body["files"]))
        return body

    @app.get("/ingest/jobs/{job_id}", dependencies=auth)
    def ingest_job(job_id: str):
        with jobs_lock:
            job = jobs.get(job_id)
            if job is None:
                raise APIError(404, "job_not_found", f"No ingest job {job_id} (jobs are kept in memory until restart)")
            return json.loads(json.dumps(job))

    @app.get("/inbox", dependencies=auth)
    def inbox(request: Request):
        from upii.ambient.inbox import list_pending

        items = [{"id": e["event_id"], "path": e["file_path"], "type": e["event_type"],
                  "hash": e["content_hash"], "time": e["detected_at"], "status": e["status"]}
                 for e in list_pending(staging())]
        _note(request, results=len(items))
        return {"items": items}

    def inbox_target(event_id: str, request: Request):
        from upii.ambient.inbox import find_event

        _note(request, event_id=event_id)
        stg = staging()
        target = find_event(stg, event_id, exact=True)
        if target is None:
            raise APIError(404, "event_not_found", f"No inbox event with id {event_id}")
        return stg, target

    @app.post("/inbox/{event_id}/approve", dependencies=auth)
    def inbox_approve(event_id: str, request: Request):
        from upii.ambient import inbox as ops

        stg, target = inbox_target(event_id, request)
        with write_lock:
            res = ops.approve_event(stg, target)
        if res.outcome == ops.WAS_REJECTED:
            raise APIError(409, "already_rejected", "This capture was rejected; it cannot be approved.")
        return {
            "id": event_id,
            "outcome": res.outcome,
            "in_memory": res.outcome in (ops.APPROVED, ops.ALREADY_APPROVED),
            "path": target["file_path"],
            "document_hash": res.content_hash,
            "chunks": res.chunks,
        }

    @app.post("/inbox/{event_id}/reject", dependencies=auth)
    def inbox_reject(event_id: str, request: Request):
        from upii.ambient import inbox as ops

        stg, target = inbox_target(event_id, request)
        res = ops.reject_event(stg, target)
        if res.outcome == ops.WAS_APPROVED:
            raise APIError(409, "already_approved",
                           "This capture is already in long-term memory; rejecting it would not remove it.")
        return {"id": event_id, "outcome": res.outcome, "path": target["file_path"]}

    @app.post("/search", dependencies=auth)
    def search(req: SearchRequest, request: Request):
        results = retrieve(req.query, req.limit)
        docs = document_index(results)
        out = []
        for rank, r in enumerate(results, start=1):
            doc = docs.get(r.doc_hash, {})
            out.append({
                "rank": rank,
                "text": r.text,
                "document_path": doc.get("source_path"),
                "document_hash": doc.get("content_hash"),
                "doc_id": r.doc_hash,
                "chunk_hash": r.chunk_hash,
                "scores": _scores(r),
            })
        _note(request, query=req.query, results=len(out))
        return {"weights": config.fusion_weights(), "results": out}

    @app.post("/ask", dependencies=auth)
    def ask(req: AskRequest, request: Request):
        _note(request, query=req.question)
        llm = None
        if not req.no_answer:
            from upii.analysis.llm import LocalLLM
            from upii.core.errors import ModelError

            try:
                # local_only -> always Ollama; otherwise the server's llm_provider setting.
                llm = LocalLLM(provider="local" if req.local_only else None)
            except ModelError as e:
                raise APIError(503, "model_unavailable", str(e))
            if req.local_only and llm.is_mock:
                raise APIError(503, "local_model_unavailable",
                               f"No local answer model: Ollama is not reachable (model {config.llm_model}). "
                               "Start Ollama, or send no_answer=true for retrieval only.")

        results = retrieve(req.question, config.rag_max_chunks)
        docs = document_index(results)
        sources = []
        for rank, r in enumerate(results, start=1):
            doc = docs.get(r.doc_hash, {})
            src = {
                "rank": rank,
                "document_path": doc.get("source_path"),
                "document_hash": doc.get("content_hash"),
                "chunk_hash": r.chunk_hash,
                "passage": r.text,
            }
            if req.debug:
                src["scores"] = _scores(r)
            sources.append(src)
        _note(request, query=req.question, results=len(sources))

        answer, model = None, None
        if llm is not None:
            try:
                answer = llm.answer_with_citations(req.question, results)
            except Exception as e:
                raise APIError(500, "generation_failed", f"{type(e).__name__}: {e}")
            if req.local_only and llm.is_mock:
                # Ollama answered the probe but generation failed; never pass off a mock.
                raise APIError(503, "local_model_unavailable",
                               f"Local generation failed (model {config.llm_model}). "
                               "Check `ollama list`, or send no_answer=true for retrieval only.")
            model = llm.model_info()

        return {"answer": answer, "model": model, "sources": sources}

    @app.get("/sources", dependencies=auth)
    def sources(request: Request):
        from upii.storage.db import DB

        if not os.path.exists(config.db_path):
            documents = []  # fresh install: nothing ingested, create nothing
        else:
            db = DB()
            db.init_db()
            documents = [
                {
                    "path": d["path"],
                    "document_hash": d["content_hash"],
                    "source_type": d["source_type"],
                    "ingestion_time": d["ingestion_time"],
                }
                for d in db.list_documents()
            ]
        _note(request, results=len(documents))
        return {"documents": documents}

    @app.get("/audit", dependencies=auth)
    def audit(request: Request, limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0)):
        entries = []
        for row in staging().get_audit_logs(limit=limit, offset=offset):
            try:
                details = json.loads(row.get("details") or "{}")
            except ValueError:
                details = {}
            entries.append({"id": row["audit_id"], "timestamp": row["timestamp"],
                            "source": row["source_name"], "action": row["action"], "details": details})
        _note(request, results=len(entries))
        return {"limit": limit, "offset": offset, "entries": entries}

    return app
