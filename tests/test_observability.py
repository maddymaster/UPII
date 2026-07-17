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
def test_doctor_fail_db(mock_exists):
    mock_exists.return_value = False
    doc = Doctor()
    res = doc.check_sqlite()
    assert "FAIL" in res
