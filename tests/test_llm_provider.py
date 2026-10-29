"""The answer model is an explicit setting: `llm_provider: local | remote`.

A GEMINI_API_KEY on its own must never route answers off the machine. These tests
set a real-looking key with provider=local and assert the Gemini path is never
called from any entry point (LocalLLM, CLI ask, CLI write, MCP, overlay, doctor),
and that every answer names the model that produced it.
"""
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from upii.analysis.llm import LocalLLM
from upii.core.config import Config, config
from upii.core.errors import ModelError
from upii.core.types import RankedChunk

KEY = "AIza-real-looking-key"
LOCAL = {"name": config.llm_model, "provider": "ollama", "location": "local"}


@pytest.fixture
def key_set_provider_local(monkeypatch):
    monkeypatch.delenv("UPII_LLM_PROVIDER", raising=False)
    monkeypatch.setattr(config, "gemini_api_key", KEY)
    monkeypatch.setattr(config, "llm_provider", "local")
    with patch("upii.analysis.llm.LocalLLM._call_gemini") as gemini, \
         patch("upii.analysis.llm.ollama.list", return_value={"models": []}), \
         patch("upii.analysis.llm.ollama.generate", return_value={"response": "local answer"}):
        yield gemini


def _chunks():
    return [RankedChunk(doc_hash="doc-1", chunk_hash="c1", text="The Q3 budget is $50k.",
                        start_char=0, end_char=0)]


# -- LocalLLM -------------------------------------------------------------------
def test_key_alone_never_selects_remote(key_set_provider_local):
    llm = LocalLLM()
    assert llm.provider == "local" and not llm.use_gemini
    assert llm.answer_with_citations("Q3 budget?", _chunks()) == "local answer"
    key_set_provider_local.assert_not_called()
    assert llm.model_info() == LOCAL
    assert llm.model_label() == f"{config.llm_model} (ollama, local)"


def test_remote_only_when_configured(monkeypatch):
    monkeypatch.setattr(config, "gemini_api_key", KEY)
    monkeypatch.setattr(config, "llm_provider", "remote")
    with patch("upii.analysis.llm.LocalLLM._call_gemini", return_value="remote answer") as gemini:
        llm = LocalLLM()
        assert llm.generate("p") == "remote answer"
    gemini.assert_called_once()
    assert llm.model_info() == {"name": config.gemini_model, "provider": "gemini", "location": "remote"}


def test_explicit_local_overrides_remote_config(monkeypatch):
    monkeypatch.setattr(config, "gemini_api_key", KEY)
    monkeypatch.setattr(config, "llm_provider", "remote")
    with patch("upii.analysis.llm.ollama.list", return_value={"models": []}):
        assert not LocalLLM(provider="local").use_gemini


def test_remote_without_key_and_unknown_provider_raise(monkeypatch):
    monkeypatch.setattr(config, "gemini_api_key", "")
    with pytest.raises(ModelError, match="GEMINI_API_KEY"):
        LocalLLM(provider="remote")
    with pytest.raises(ModelError, match="local' or 'remote"):
        LocalLLM(provider="gemini")


def test_env_var_sets_provider(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("UPII_LLM_PROVIDER", raising=False)
    assert Config.load().llm_provider == "local"
    (tmp_path / ".upii_config.yaml").write_text("llm_provider: remote\n", encoding="utf-8")
    assert Config.load().llm_provider == "remote"
    monkeypatch.setenv("UPII_LLM_PROVIDER", "local")
    assert Config.load().llm_provider == "local"


# -- entry points ---------------------------------------------------------------
def test_cli_ask_stays_local_and_prints_model(key_set_provider_local):
    from upii.cli import app

    with patch("upii.analysis.search.SearchEngine") as engine:
        engine.return_value.search.return_value = _chunks()
        result = CliRunner().invoke(app, ["ask", "What is the Q3 budget?"])
    assert result.exit_code == 0, result.output
    key_set_provider_local.assert_not_called()
    assert "local answer" in result.stdout
    assert f"Answered by: {config.llm_model} (ollama, local)" in result.stdout


def test_cli_write_stays_local_and_prints_model(key_set_provider_local):
    from upii.cli import app

    with patch("upii.analysis.search.SearchEngine") as engine:
        engine.return_value.search.return_value = _chunks()
        result = CliRunner().invoke(app, ["write", "a note about the budget", "--target", "email"])
    assert result.exit_code == 0, result.output
    key_set_provider_local.assert_not_called()
    assert "Answered by:" in result.stdout and "ollama, local" in result.stdout


def test_cli_ask_remote_without_key_is_an_error_not_a_fallback(monkeypatch):
    from upii.cli import app

    monkeypatch.setattr(config, "gemini_api_key", "")
    monkeypatch.setattr(config, "llm_provider", "remote")
    with patch("upii.analysis.search.SearchEngine") as engine, \
         patch("upii.analysis.llm.ollama.generate") as local:
        engine.return_value.search.return_value = _chunks()
        result = CliRunner().invoke(app, ["ask", "What is the Q3 budget?"])
    local.assert_not_called()
    assert "GEMINI_API_KEY is not set" in result.stdout


def test_mcp_ask_stays_local_and_returns_model(key_set_provider_local, tmp_path, monkeypatch):
    from upii.mcp.config import MCPConfig
    from upii.mcp.service import MCPService
    from upii.storage.db import DB

    monkeypatch.setattr(config, "db_path", str(tmp_path / "upii.db"))

    class Engine:
        def search(self, q, limit=5, **_):
            return _chunks()

    svc = MCPService(mcp_config=MCPConfig(enabled=True), search_engine=Engine(), db=DB())
    out = svc.ask("Q3 budget?")
    key_set_provider_local.assert_not_called()
    assert out["model"] == LOCAL


def test_overlay_stays_local_and_returns_model(key_set_provider_local, monkeypatch):
    from upii.overlay.app import OverlayAPI

    class Rehydrator:
        def rehydrate(self, query, limit=5, **_):
            return _chunks()

    monkeypatch.setattr("upii.overlay.app.ContextRehydrator", Rehydrator)
    out = OverlayAPI().query("Q3 budget?")
    key_set_provider_local.assert_not_called()
    assert out["answer"] == "local answer" and out["model"] == LOCAL


def test_doctor_reports_the_configured_provider(monkeypatch):
    from upii.analysis.diagnostics import Doctor

    monkeypatch.setattr(config, "gemini_api_key", KEY)
    monkeypatch.setattr(config, "llm_provider", "remote")
    assert Doctor().check_model().startswith("OK (remote:")
    monkeypatch.setattr(config, "gemini_api_key", "")
    assert Doctor().check_model().startswith("FAIL:")
