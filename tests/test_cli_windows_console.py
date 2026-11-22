"""CLI output must encode on the legacy Windows console (cp1252).

`upii doctor` crashed with UnicodeEncodeError on Windows because its hint lines started
with "→" (found by the release build smoke test, T-054)."""
from unittest.mock import patch

from typer.testing import CliRunner

from upii.cli import app


def _encodes_cp1252(text):
    text.encode("cp1252")  # raises UnicodeEncodeError like the Windows console did


def test_doctor_output_with_hints_encodes_on_windows_console():
    from upii.analysis.diagnostics import Doctor
    checks = {"sqlite": "READY: empty memory, created on first ingest",
              "vector_db": "READY: no vectors yet, created on first ingest",
              "disk": "OK (24 GB free)",
              "model": "WARN: Ollama offline (Using Mock LLM)",
              "embedding": "WARN: embedding model all-MiniLM-L6-v2 is not cached; the first ingest downloads it (needs internet)",
              "ingestion": "FAIL: database is unreadable or corrupt (upii.db): file is not a database"}
    with patch.object(Doctor, "check_all", return_value=checks):
        r = CliRunner().invoke(app, ["doctor"])
    assert r.exit_code == 1  # one FAIL
    assert "->" in r.output  # hints are printed
    _encodes_cp1252(r.output)


def test_ask_debug_table_encodes_on_windows_console(monkeypatch):
    import io
    from rich.console import Console
    import upii.cli as cli
    from upii.core.types import RankedChunk

    class Cp1252(io.StringIO):
        encoding = "cp1252"  # what the legacy Windows console reports

    buf = Cp1252()
    monkeypatch.setattr(cli, "console", Console(file=buf, width=120, color_system=None))
    r = RankedChunk(doc_hash="d1", chunk_hash="c1", text="Budget notes", start_char=0, end_char=12,
                    score=0.9, boost_reason="semantic", source_signal="semantic",
                    signals={"semantic": 1.0, "temporal": 0.25, "relational": 0.0})
    cli._print_fusion_debug([r], None)
    out = buf.getvalue()
    assert "Fusion Ranking" in out and "->" in out
    _encodes_cp1252(out)
