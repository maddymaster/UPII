import logging
import pytest
from unittest.mock import MagicMock, patch
from upii.analysis.diagnostics import Doctor
from upii.core.logger import setup_logging

def test_logger_setup(tmp_path):
    log_file = tmp_path / "test.log"
    logger = setup_logging(debug=True, log_file=str(log_file))
    
    logger.debug("Debug message")
    logger.info("Info message")
    
    assert log_file.exists()
    content = log_file.read_text()
    assert "Debug message" in content
    assert "Info message" in content
    
    # Check handler count (File + Console)
    assert len(logger.handlers) == 2

@patch("upii.analysis.llm.LocalLLM")
@patch("upii.analysis.diagnostics.config")
@patch("upii.analysis.diagnostics.DB")
@patch("upii.analysis.diagnostics.LocalVectorStore")
@patch("upii.analysis.diagnostics.ollama")
@patch("upii.analysis.diagnostics.shutil")
@patch("upii.analysis.diagnostics.os.path.exists")
def test_doctor_checks(mock_exists, mock_shutil, mock_ollama, mock_vs, mock_db, mock_config, mock_llm):
    # Setup happy path
    mock_exists.return_value = True

    # check_model() constructs a LocalLLM to detect mock-mode; without a running
    # Ollama its __init__ would flip is_mock=True and short-circuit. Pin it False so
    # the test exercises the real model-lookup path and is hermetic (no daemon).
    mock_llm.return_value.is_mock = False
    mock_llm.return_value.use_gemini = False  # llm_provider=local
    
    mock_db_instance = mock_db.return_value
    mock_db_instance.get_connection.return_value.cursor.return_value.fetchone.return_value = ["2023-01-01"]
    
    mock_vs_instance = mock_vs.return_value
    mock_vs_instance.count.return_value = 100
    
    mock_shutil.disk_usage.return_value = (100, 50, 5*1024**3) # 5GB free
    
    mock_ollama.list.return_value = {'models': [{'name': 'llama3.2:latest'}]}
    mock_config.llm_model = 'llama3.2'
    
    doc = Doctor()
    report = doc.check_all()
    
    assert report["sqlite"] == "OK"
    assert "100 vectors" in report["vector_db"]
    assert "5 GB free" in report["disk"]
    assert "Found llama3.2" in report["model"]
    assert "2023-01-01" in report["ingestion"]

@patch("upii.analysis.diagnostics.ollama")
def test_doctor_fail_model(mock_ollama):
    mock_ollama.list.return_value = {'models': []}
    doc = Doctor()
    res = doc.check_model()
    assert "WARN" in res

@patch("upii.analysis.diagnostics.os.path.exists")
def test_doctor_missing_db_is_ready(mock_exists):
    # A missing DB is an empty memory (created on first ingest), not a failure.
    # Genuine corruption is covered in tests/test_doctor_fresh_install.py.
    mock_exists.return_value = False
    doc = Doctor()
    res = doc.check_sqlite()
    assert res.startswith("READY")
    assert "FAIL" not in res


# --- T-005: tokens and latency per answer -----------------------------------
# Every model call reports input/output tokens, latency and model; no model is
# ever reached here (Ollama and Gemini are mocked), and no surface logs text.
import io
import json as _json

from upii.analysis.llm import Answer, LocalLLM, Usage, estimate_tokens
from upii.core.config import config as _config
from upii.core.types import Chunk, RankedChunk

_PROMPT = "x" * 400  # 100 estimated tokens


def _local_llm(monkeypatch):
    monkeypatch.setattr(_config, "llm_provider", "local")
    monkeypatch.setattr("upii.analysis.llm.ollama.list", lambda: {"models": []})
    return LocalLLM()


def _chunks():
    return [Chunk(doc_hash="d1", chunk_hash="c1", text="Alpha starts Monday.", start_char=0, end_char=20)]


def test_ollama_counts_come_from_the_response(monkeypatch):
    llm = _local_llm(monkeypatch)
    monkeypatch.setattr("upii.analysis.llm.ollama.generate",
                        lambda **_: {"response": "hi", "prompt_eval_count": 812, "eval_count": 64,
                                     "total_duration": 1})
    text, usage = llm._generate_with_usage(_PROMPT)
    assert text == "hi"
    assert (usage.input_tokens, usage.output_tokens, usage.estimated) == (812, 64, False)
    assert usage.model == _config.llm_model
    assert isinstance(usage.latency_ms, int) and usage.latency_ms >= 0


def test_ollama_without_counts_is_estimated(monkeypatch):
    llm = _local_llm(monkeypatch)
    monkeypatch.setattr("upii.analysis.llm.ollama.generate", lambda **_: {"response": "y" * 40})
    _, usage = llm._generate_with_usage(_PROMPT)
    assert (usage.input_tokens, usage.output_tokens, usage.estimated) == (100, 10, True)


def _gemini_llm(monkeypatch, body):
    monkeypatch.setattr(_config, "llm_provider", "remote")
    monkeypatch.setattr(_config, "gemini_api_key", "AIza-test")

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr("upii.analysis.llm.urllib.request.urlopen",
                        lambda req: Resp(_json.dumps(body).encode("utf-8")))
    return LocalLLM()


def test_gemini_counts_come_from_usage_metadata(monkeypatch):
    llm = _gemini_llm(monkeypatch, {
        "candidates": [{"content": {"parts": [{"text": "remote"}]}}],
        "usageMetadata": {"promptTokenCount": 300, "candidatesTokenCount": 7}})
    text, usage = llm._generate_with_usage(_PROMPT)
    assert text == "remote"
    assert (usage.input_tokens, usage.output_tokens, usage.estimated) == (300, 7, False)
    assert usage.model == _config.gemini_model


def test_gemini_without_usage_metadata_is_estimated(monkeypatch):
    llm = _gemini_llm(monkeypatch, {"candidates": [{"content": {"parts": [{"text": "r" * 8}]}}]})
    _, usage = llm._generate_with_usage(_PROMPT)
    assert (usage.input_tokens, usage.output_tokens, usage.estimated) == (100, 2, True)


def test_mock_mode_is_estimated(monkeypatch):
    monkeypatch.setattr(_config, "llm_provider", "local")
    monkeypatch.setattr("upii.analysis.llm.ollama.list", lambda: (_ for _ in ()).throw(ConnectionError()))
    llm = LocalLLM()
    text, usage = llm._generate_with_usage(_PROMPT)
    assert usage.model == "mock" and usage.estimated is True
    assert usage.input_tokens == 100 and usage.output_tokens == estimate_tokens(text)


def test_drop_to_mock_mid_call_reports_mock(monkeypatch):
    llm = _local_llm(monkeypatch)
    monkeypatch.setattr("upii.analysis.llm.ollama.generate",
                        lambda **_: (_ for _ in ()).throw(RuntimeError("down")))
    _, usage = llm._generate_with_usage(_PROMPT)
    assert usage.model == "mock" and usage.estimated is True


def test_generate_still_returns_text(monkeypatch):
    llm = _local_llm(monkeypatch)
    monkeypatch.setattr("upii.analysis.llm.ollama.generate",
                        lambda **_: {"response": "plain", "prompt_eval_count": 1, "eval_count": 1})
    assert llm.generate("p") == "plain"


def test_answer_without_chunks_has_no_usage(monkeypatch):
    llm = _local_llm(monkeypatch)
    assert llm.answer("q", []).usage is None


def test_abstention_still_reports_usage(monkeypatch):
    llm = _local_llm(monkeypatch)
    monkeypatch.setattr("upii.analysis.llm.ollama.generate",
                        lambda **_: {"response": "NOT_FOUND", "prompt_eval_count": 50, "eval_count": 3})
    a = llm.answer("q", _chunks())
    assert a.found is False
    assert a.usage.to_dict() == {"input_tokens": 50, "output_tokens": 3, "latency_ms": a.usage.latency_ms,
                                 "model": _config.llm_model, "estimated": False}


# -- HTTP /ask ------------------------------------------------------------------
def test_http_ask_returns_usage_and_audits_counts_only(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from upii.api import server

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("UPII_API_KEY", raising=False)
    monkeypatch.setattr(_config, "staging_db_path", str(tmp_path / "staging.db"))
    monkeypatch.setattr(_config, "gemini_api_key", "")
    monkeypatch.setattr(_config, "llm_provider", "local")
    monkeypatch.setattr("upii.analysis.llm.ollama.list", lambda: {"models": []})
    monkeypatch.setattr("upii.analysis.llm.ollama.generate",
                        lambda **_: {"response": "Monday [1].", "prompt_eval_count": 812, "eval_count": 64})
    hits = [RankedChunk(doc_hash="d1", chunk_hash="c1", text="Alpha starts Monday.", start_char=0, end_char=20)]
    found = {"hits": hits}
    engine = MagicMock()
    engine.return_value.search.side_effect = lambda *a, **k: found["hits"]
    monkeypatch.setattr("upii.analysis.search.SearchEngine", engine)
    monkeypatch.setattr("upii.storage.db.DB.get_document_by_id", lambda self, doc_id: None)
    monkeypatch.setattr(_config, "db_path", str(tmp_path / "upii.db"))
    client = TestClient(server.create_app(), base_url="http://127.0.0.1")

    question = "a very private question about Alpha"
    body = client.post("/ask", json={"question": question}).json()
    assert body["usage"]["input_tokens"] == 812 and body["usage"]["output_tokens"] == 64
    assert body["usage"]["model"] == _config.llm_model and body["usage"]["estimated"] is False
    assert isinstance(body["usage"]["latency_ms"], int)

    assert client.post("/ask", json={"question": question, "no_answer": True}).json()["usage"] is None
    found["hits"] = []
    assert client.post("/ask", json={"question": question}).json()["usage"] is None

    entries = client.get("/audit").json()["entries"]
    asks = [e["details"] for e in entries if e["action"] == "POST /ask"]
    answered = [d for d in asks if d.get("usage")]
    assert len(answered) == 1
    assert answered[0]["usage"] == body["usage"]
    assert all("usage" not in d for d in asks if d is not answered[0])
    raw = (tmp_path / "staging.db").read_bytes()
    assert question.encode() not in raw and b"Monday [1]" not in raw and b"Alpha starts" not in raw


# -- MCP ------------------------------------------------------------------------
def test_mcp_ask_returns_usage(monkeypatch):
    from upii.mcp.config import MCPConfig
    from upii.mcp.service import MCPService

    monkeypatch.setattr(_config, "llm_provider", "local")
    monkeypatch.setattr(_config, "gemini_api_key", "")
    monkeypatch.setattr("upii.analysis.llm.ollama.list", lambda: {"models": []})
    monkeypatch.setattr("upii.analysis.llm.ollama.generate",
                        lambda **_: {"response": "Monday [1].", "prompt_eval_count": 20, "eval_count": 4})
    rows = [{"chunk_id": "c1", "doc_path": "/n/a.md", "source": "markdown", "text": "Alpha starts Monday."}]
    svc = MCPService(mcp_config=MCPConfig(enabled=True), search_engine=MagicMock())
    monkeypatch.setattr(svc, "_enrich_and_filter", lambda raw: list(rows))
    monkeypatch.setattr(svc, "_log", lambda *a: None)

    out = svc.ask("when?")
    assert out["usage"]["input_tokens"] == 20 and out["usage"]["output_tokens"] == 4
    assert out["usage"]["estimated"] is False

    rows.clear()
    assert svc.ask("when?")["usage"] is None


# -- Overlay ----------------------------------------------------------------------
def test_overlay_query_returns_usage(monkeypatch):
    from upii.overlay.app import OverlayAPI

    usage = Usage(input_tokens=9, output_tokens=2, latency_ms=15, model="m", estimated=True)
    hits = {"chunks": [RankedChunk(doc_hash="d1", chunk_hash="c1", text="Alpha.", start_char=0, end_char=6)]}

    class Rehydrator:
        def rehydrate(self, query, limit=5, **_):
            return hits["chunks"]

    class LLM:
        def answer(self, query, context):
            return Answer(text="Alpha [1].", found=True, cited=[1], usage=usage)

        def model_info(self):
            return {"name": "m", "provider": "ollama", "location": "local"}

    monkeypatch.setattr("upii.overlay.app.ContextRehydrator", Rehydrator)
    monkeypatch.setattr("upii.overlay.app.LocalLLM", LLM)
    monkeypatch.setattr("upii.storage.db.DB.get_document_by_id", lambda self, doc_id: None)
    api = OverlayAPI()
    assert api.query("q")["usage"] == usage.to_dict()
    hits["chunks"] = []
    assert api.query("q")["usage"] is None


# -- CLI --------------------------------------------------------------------------
def _cli_ask(usage):
    from typer.testing import CliRunner
    from upii.cli import app

    results = [RankedChunk(doc_hash="d1", chunk_hash="c1", text="Alpha.", start_char=0, end_char=6)]
    with patch("upii.analysis.search.SearchEngine") as engine, patch("upii.analysis.llm.LocalLLM") as llm:
        engine.return_value.search.return_value = results
        llm.return_value.answer.return_value = Answer(text="Alpha [1].", found=True, cited=[1], usage=usage)
        llm.return_value.model_label.return_value = "mock (mock, local)"
        return CliRunner().invoke(app, ["ask", "What is Alpha?"])


def test_cli_ask_prints_tokens_line():
    r = _cli_ask(Usage(input_tokens=812, output_tokens=64, latency_ms=2300, model="llama3.2", estimated=False))
    assert r.exit_code == 0, r.output
    assert "Tokens: 812 in, 64 out · 2.3 s" in r.stdout
    assert "(estimated)" not in r.stdout


def test_cli_ask_marks_estimated_tokens():
    r = _cli_ask(Usage(input_tokens=100, output_tokens=12, latency_ms=4, model="mock", estimated=True))
    assert r.exit_code == 0, r.output
    assert "Tokens: 100 in, 12 out · 0.0 s (estimated)" in r.stdout
