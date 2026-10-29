"""Loading a cached embedding model never waits on a Hugging Face network check.

When the model is already on disk, importing the embedder sets HF_HUB_OFFLINE and
TRANSFORMERS_OFFLINE; an explicit value of either always wins; an uncached model
is left online so first use can still download it.
"""
import os
import subprocess
import sys

import pytest

from upii.analysis import embeddings

MODEL = "all-MiniLM-L6-v2"
OFFLINE_VARS = ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE")


def _fake_cache(root, weights=True, modules=True):
    snap = root / "models--sentence-transformers--all-MiniLM-L6-v2" / "snapshots" / "abc123"
    snap.mkdir(parents=True)
    if modules:
        (snap / "modules.json").write_text("[]")
    if weights:
        (snap / "model.safetensors").write_bytes(b"\0")
    return root


@pytest.fixture
def env(tmp_path, monkeypatch):
    for var in OFFLINE_VARS + ("HF_HOME", "SENTENCE_TRANSFORMERS_HOME", "XDG_CACHE_HOME"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "hub"))
    return tmp_path


def test_cached_model_turns_offline_on(env):
    _fake_cache(env / "hub")
    assert embeddings.prefer_offline_if_cached(MODEL) is True
    assert all(os.environ[v] == "1" for v in OFFLINE_VARS)


def test_uncached_or_incomplete_model_stays_online(env):
    assert embeddings.prefer_offline_if_cached(MODEL) is False
    _fake_cache(env / "hub", weights=False)
    assert embeddings.prefer_offline_if_cached(MODEL) is False
    assert not any(v in os.environ for v in OFFLINE_VARS)


@pytest.mark.parametrize("var", OFFLINE_VARS)
def test_explicit_setting_wins(env, monkeypatch, var):
    _fake_cache(env / "hub")
    monkeypatch.setenv(var, "0")
    assert embeddings.prefer_offline_if_cached(MODEL) is False
    assert os.environ[var] == "0"
    other = next(v for v in OFFLINE_VARS if v != var)
    assert other not in os.environ


def test_cache_locations(env, monkeypatch):
    monkeypatch.delenv("HF_HUB_CACHE")
    monkeypatch.setenv("HF_HOME", str(env / "hf"))
    _fake_cache(env / "hf" / "hub")
    assert embeddings.model_is_cached(MODEL)
    monkeypatch.delenv("HF_HOME")
    monkeypatch.setenv("SENTENCE_TRANSFORMERS_HOME", str(env / "st"))
    _fake_cache(env / "st")
    assert embeddings.model_is_cached(MODEL)
    assert embeddings.model_is_cached(str(env))  # a local model folder
    assert not embeddings.model_is_cached("someone/other-model")


def test_import_sets_offline_before_huggingface_hub_reads_it(env):
    # Fresh interpreter: the import order is what matters, so it can't be faked here.
    _fake_cache(env / "hub")
    code = ("import os, upii.analysis.embeddings, huggingface_hub.constants as c;"
            "print(os.environ.get('HF_HUB_OFFLINE'), os.environ.get('TRANSFORMERS_OFFLINE'), c.HF_HUB_OFFLINE)")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         env={k: v for k, v in os.environ.items()}, timeout=120)
    assert out.returncode == 0, out.stderr
    assert out.stdout.split() == ["1", "1", "True"]
