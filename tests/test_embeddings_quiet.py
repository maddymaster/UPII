"""Verify that Embedder.get_instance suppresses tqdm progress bars and logging.

Requires no real embedding model — stubs SentenceTransformer via monkeypatch.
"""
import logging
from unittest.mock import MagicMock


def test_get_instance_suppresses_progress_bars(monkeypatch):
    # Stub SentenceTransformer so the test does not load weights or download anything.
    stub = MagicMock()
    monkeypatch.setattr("upii.analysis.embeddings.SentenceTransformer", stub)

    # Ensure Embedder starts fresh (may be populated from other tests).
    import upii.analysis.embeddings as emb
    monkeypatch.setattr(emb.Embedder, "_instance", None)

    # Save original sentence_transformers logger level for restoration.
    st_logger = logging.getLogger("sentence_transformers")
    orig_level = st_logger.getEffectiveLevel()

    emb.Embedder.get_instance()

    # 1. transformers tqdm is disabled.
    from transformers.utils.logging import is_progress_bar_enabled, enable_progress_bar
    assert not is_progress_bar_enabled(), "progress bar should be disabled"

    # 2. sentence_transformers logger (package root) set to WARNING or above.
    log_level = logging.getLogger("sentence_transformers").getEffectiveLevel()
    assert log_level >= logging.WARNING, f"logger level {log_level} < WARNING"

    # 3. The specific encode() logger used in sentence_transformer/model.py also inherits WARNING.
    encode_logger = logging.getLogger(
        "sentence_transformers.sentence_transformer.model"
    )
    assert (
        encode_logger.getEffectiveLevel() >= logging.WARNING
    ), f"encode logger level {encode_logger.getEffectiveLevel()} < WARNING"

    # Restore original levels so other tests are unaffected.
    st_logger.setLevel(orig_level)
    enable_progress_bar()
