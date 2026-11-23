"""`upii doctor` health-check helpers — a clean-machine check that never downloads
or imports sentence-transformers / huggingface_hub / torch.
"""

import os
import shutil
import sqlite3
import logging
from typing import Dict, Any

import ollama
from upii.analysis.model_cache import model_is_cached as _model_is_cached  # noqa: F401
from upii.core.config import config
from upii.storage.db import DB
from upii.storage.vector import LocalVectorStore

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# remediation hints                                                           #
# --------------------------------------------------------------------------- #

_HINTS: dict[str, str] = {
    "sqlite": (
        "Move the damaged database file aside, then re-run "
        "`upii ingest <folder>`. Check the file's permissions."
    ),
    "vector_db": (
        "Move the vectors folder aside, then re-run "
        "`upii ingest <folder>` to rebuild it."
    ),
    "disk": "Free space on the drive that holds the memory folder.",
    "model": (
        "Start Ollama (`ollama serve`), or install it from ollama.com. "
        "Until then answers use the built-in mock model."
    ),
    "embedding": (
        "Online, with HF_HUB_OFFLINE unset, run `upii ingest <folder>` once. "
        "The model is then cached and later runs work offline."
    ),
    "ingestion": "Run `upii ingest <folder>` to add your first documents.",
}


def remediation(name: str, result: str) -> str:
    """Return a one-line fix hint for a WARN or FAIL check."""
    if name == "sqlite":
        return _HINTS["sqlite"]
    if name == "vector_db":
        return _HINTS["vector_db"]
    if name == "disk":
        return _HINTS["disk"]
    if name == "model":
        if "remote" in result.lower() or "gemini" in result.lower():
            return "Check llm_provider and GEMINI_API_KEY, or set llm_provider: local."
        if "connection error" in result.lower() or "ollama offline" in result.lower() or "mock" in result.lower():
            return _HINTS["model"]
        return f"Run `ollama pull {config.llm_model}`, or set llm_model in .upii_config.yaml."
    if name == "embedding":
        return _HINTS["embedding"]
    if name == "ingestion":
        return _HINTS["ingestion"]
    return ""


class Doctor:
    """System health checks."""

    def check_all(self) -> Dict[str, Any]:
        return {
            "sqlite": self.check_sqlite(),
            "vector_db": self.check_vector_db(),
            "disk": self.check_disk(),
            "model": self.check_model(),
            "embedding": self.check_embedding(),
            "ingestion": self.check_last_ingestion(),
        }

    def check_sqlite(self) -> str:
        try:
            # An empty memory is a valid state: the DB is created on first ingest.
            # Checked before connecting, since sqlite3.connect would create the file.
            if not os.path.exists(config.db_path):
                return "READY: empty memory, created on first ingest"
            db = DB()
            conn = db.get_connection()
            try:
                # SELECT 1 never touches the file; reading the schema forces SQLite
                # to parse the header, so a corrupt file fails here.
                conn.execute("PRAGMA schema_version").fetchone()
            finally:
                conn.close()
            return "OK"
        except sqlite3.DatabaseError as e:
            return f"FAIL: database is unreadable or corrupt ({config.db_path}): {e}"
        except Exception as e:
            return f"FAIL: {e}"

    def check_vector_db(self) -> str:
        try:
            if not os.path.exists(config.vector_store_path):
                return "READY: no vectors yet, created on first ingest"
            vs = LocalVectorStore()
            count = vs.count()
            return f"OK ({count} vectors)"
        except Exception as e:
            return f"FAIL: {e}"

    def check_disk(self) -> str:
        try:
            # Check current directory partition
            total, used, free = shutil.disk_usage(".")
            free_gb = free // (2**30)
            if free_gb < 1:
                return f"WARN: Low disk space ({free_gb} GB free)"
            return f"OK ({free_gb} GB free)"
        except Exception as e:
            return f"FAIL: {e}"

    def check_model(self) -> str:
        try:
            # Check for mock fallback in LocalLLM
            from upii.analysis.llm import LocalLLM
            from upii.core.errors import ModelError
            try:
                llm = LocalLLM()
            except ModelError as e:
                return f"FAIL: {e}"
            if llm.use_gemini:
                return f"OK (remote: {llm.gemini_model}, llm_provider=remote)"
            if llm.is_mock:
                return "WARN: Ollama offline (Using Mock LLM)"

            # Verify we can talk to Ollama.
            # Older ollama clients return a plain dict with 'models' -> [{'name': ...}].
            # Newer clients (>=0.4) return a Pydantic ListResponse with .models -> [Model(model='...')].
            resp = ollama.list()
            raw_models = getattr(resp, "models", None)
            if raw_models is None and isinstance(resp, dict):
                raw_models = resp.get("models", [])
            raw_models = raw_models or []

            model_names = []
            for m in raw_models:
                name = getattr(m, "model", None) or getattr(m, "name", None)
                if name is None and isinstance(m, dict):
                    name = m.get("model") or m.get("name")
                if name:
                    model_names.append(name)

            # config.llm_model might be "llama3.2" or "llama3.2:latest"
            # We do a loose check
            if any(config.llm_model in m for m in model_names):
                return f"OK (Found {config.llm_model})"

            return f"WARN: Model {config.llm_model} not found in Ollama list: {model_names}"
        except Exception as e:
            return f"FAIL: Ollama connection error: {e}"

    def check_embedding(self) -> str:
        """Embedding model readiness. Never downloads or imports transformers."""
        model_name = getattr(config, "embedding_model", "all-MiniLM-L6-v2")
        if _model_is_cached(model_name):
            return "OK"
        return f"WARN: embedding model {model_name} is not cached; the first ingest downloads it (needs internet)"

    def check_last_ingestion(self) -> str:
        try:
            # Doctor must never create files; DB() would create an empty upii.db.
            if not os.path.exists(config.db_path):
                return "READY: nothing ingested yet"
            db = DB()
            conn = db.get_connection()
            cur = conn.cursor()
            cur.execute("SELECT MAX(ingestion_time) FROM documents")
            last = cur.fetchone()[0]
            conn.close()
            if not last:
                return "WARN: No documents ingested yet"
            return f"OK (Last: {last})"
        except Exception as e:
            return f"FAIL: {e}"
