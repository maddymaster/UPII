"""Offline tests for bench/memory: backends, pins and the strict model wrapper.

No network and no model calls. Run with the benchmark venv:
    bench/memory/.venv/bin/python -m pytest bench/memory/tests -q
(CI runs ``pytest tests/`` only, so these do not affect the main suite.)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(1, os.path.join(REPO, "src"))

np = pytest.importorskip("numpy")

import fetch  # noqa: E402
from backends import BACKENDS, iso_at, make_backend  # noqa: E402
from backends.full_history import FullHistoryBackend  # noqa: E402
from backends.mem0_oss import Mem0OSSBackend, mem0_config  # noqa: E402
from backends.vector import VectorBackend  # noqa: E402

T0 = 1683554160  # 8 May 2023 13:56 UTC


def run(coro):
    return asyncio.run(coro)


def msgs(*texts):
    return [{"role": "user", "content": t} for t in texts]


# -- shared interface -------------------------------------------------------------
def test_backend_names_are_the_four_planned():
    assert BACKENDS == ("full_history", "vector", "mem0_oss", "upii")
    with pytest.raises(ValueError):
        make_backend("nope")


def test_iso_at_is_parseable_and_keeps_order():
    a, b = iso_at(T0, 0), iso_at(T0, 1)
    assert a == "2023-05-08T13:56:00" and a < b
    assert iso_at(None) == ""


def test_backends_are_async_context_managers():
    async def go():
        async with FullHistoryBackend() as b:
            assert await b.get_user_profile("u") is None
    run(go())


# -- full history -----------------------------------------------------------------------
def test_full_history_returns_every_turn_in_order():
    b = FullHistoryBackend()
    run(b.add(msgs("A: one", "B: two"), "u", timestamp=T0))
    run(b.add(msgs("A: three"), "u", timestamp=T0 + 86400))
    run(b.add(msgs("X: other user"), "v", timestamp=T0))
    res = run(b.search("anything", "u", top_k=1))  # top_k is ignored: full history
    assert [r["memory"] for r in res] == ["A: one", "B: two", "A: three"]
    scores = [r["score"] for r in res]
    assert scores == sorted(scores, reverse=True)  # harness score sort keeps order
    created = [r["created_at"] for r in res]
    assert created == sorted(created)  # answer prompt's date sort keeps order


def test_full_history_skips_empty_turns_and_deletes_users():
    b = FullHistoryBackend()
    out = run(b.add(msgs("A: hi", "  "), "u", timestamp=T0))
    assert len(out["results"]) == 1
    assert run(b.delete_user("u")) is True
    assert run(b.search("q", "u")) == []


def test_full_history_survives_harness_format_and_prompt_sort():
    # Mirrors format_search_results (sort by score) then the prompt (sort by date).
    b = FullHistoryBackend()
    run(b.add(msgs(*[f"S: turn {i}" for i in range(50)]), "u", timestamp=T0))
    res = sorted(run(b.search("q", "u")), key=lambda r: r["score"], reverse=True)
    res = sorted(res, key=lambda r: r["created_at"])
    assert [r["memory"] for r in res] == [f"S: turn {i}" for i in range(50)]


# -- vector -----------------------------------------------------------------------------
def fake_embed(texts):
    # Bag of words over a tiny vocabulary: deterministic, no model download.
    vocab = ["cat", "dog", "paris", "tea"]
    return np.array([[t.lower().count(w) + 1e-3 for w in vocab] for t in texts], dtype=np.float32)


def test_vector_ranks_by_cosine_and_respects_top_k():
    b = VectorBackend(embed=fake_embed)
    run(b.add(msgs("A: my dog barks", "B: tea in paris", "A: the cat sleeps"), "u", timestamp=T0))
    res = run(b.search("where is paris", "u", top_k=2))
    assert len(res) == 2
    assert res[0]["memory"] == "B: tea in paris"
    assert res[0]["score"] >= res[1]["score"]
    assert run(b.search("x", "nobody")) == []


def test_vector_keeps_users_apart():
    b = VectorBackend(embed=fake_embed)
    run(b.add(msgs("A: dog"), "u", timestamp=T0))
    run(b.add(msgs("A: cat"), "v", timestamp=T0))
    assert [r["memory"] for r in run(b.search("dog", "v"))] == ["A: cat"]
    run(b.delete_user("u"))
    assert run(b.search("dog", "u")) == []


# -- mem0 OSS (fake Memory, no model) --------------------------------------------------
class FakeMemory:
    def __init__(self):
        self.calls = []

    def add(self, messages, *, user_id, metadata=None):
        self.calls.append(("add", user_id, metadata["session_date"], messages[0]["content"]))
        return {"results": [{"memory": "fact", "event": "ADD"}]}

    def search(self, query, *, top_k, filters, threshold):
        self.calls.append(("search", filters["user_id"], top_k))
        return {"results": [{"id": "1", "memory": "fact", "score": 0.9,
                             "created_at": "2026-11-24T10:00:00",
                             "metadata": {"session_date": "2023-05-08T13:56:00"}}]}

    def delete_all(self, user_id):
        self.calls.append(("delete", user_id))


def test_mem0_oss_maps_the_harness_interface():
    fm = FakeMemory()
    b = Mem0OSSBackend(memory=fm)
    assert run(b.add(msgs("A: hi"), "u", timestamp=T0))["results"]
    res = run(b.search("q", "u", top_k=7))
    assert res == [{"id": "1", "memory": "fact", "score": 0.9, "created_at": "2023-05-08T13:56:00"}]
    run(b.delete_user("u"))
    assert fm.calls == [("add", "u", "2023-05-08T13:56:00", "(2023-05-08) A: hi"),
                        ("search", "u", 7), ("delete", "u")]
    run(b.close())


def test_mem0_oss_failed_add_is_reported_as_none():
    class Boom(FakeMemory):
        def add(self, *a, **k):
            raise RuntimeError("model down")
    assert run(Mem0OSSBackend(memory=Boom()).add(msgs("A: hi"), "u")) is None


def test_mem0_telemetry_is_off_before_mem0_is_imported():
    assert os.environ.get("MEM0_TELEMETRY") == "False"


def test_mem0_config_is_local_only():
    cfg = mem0_config("/tmp/x", "qwen3.8:27b", "http://127.0.0.1:11434")
    assert cfg["llm"]["provider"] == "ollama"
    assert cfg["embedder"]["provider"] == "huggingface"
    assert cfg["vector_store"]["config"]["path"] == "/tmp/x"
    assert "api_key" not in json.dumps(cfg)


# -- upii (real ingest path; needs the cached MiniLM model) -----------------------------
def test_upii_backend_ingests_sessions_and_searches(tmp_path):
    pytest.importorskip("lancedb")
    from upii.analysis.model_cache import model_is_cached
    if not model_is_cached("all-MiniLM-L6-v2"):
        pytest.skip("MiniLM model not cached")
    from upii.core.config import config
    saved = (config.db_path, config.vector_store_path)
    try:
        b = make_backend("upii", root=str(tmp_path))
        run(b.add(msgs("Caroline: I adopted a dog named Max"), "u", timestamp=T0))
        run(b.add(msgs("Melanie: I painted a sunrise over the lake"), "u", timestamp=T0 + 86400))
        res = run(b.search("What is the name of Caroline's dog?", "u", top_k=5))
        assert res and "Max" in res[0]["memory"]
        assert res[0]["created_at"].startswith("2023-05-08")
        assert run(b.search("q", "other")) == []
        run(b.delete_user("u"))
    finally:
        config.db_path, config.vector_store_path = saved


# -- pins -------------------------------------------------------------------------------
def test_lock_pins_harness_commit_and_dataset_hashes():
    lock = fetch.load_lock()
    assert len(lock["harness"]["commit"]) == 40
    for name, spec in lock["datasets"].items():
        assert len(spec["sha256"]) == 64, name
        assert spec["source_commit"] in spec["url"], name  # URL pinned to a commit, not a branch
        assert "/main/" not in spec["url"], name


def test_verify_dataset_refuses_a_mismatch(tmp_path):
    f = tmp_path / "locomo10.json"
    f.write_bytes(b"[]")
    good = hashlib.sha256(b"[]").hexdigest()
    lock = {"datasets": {"locomo": {"file": "locomo10.json", "sha256": good}}}
    assert fetch.verify_dataset("locomo", lock, str(tmp_path)) == str(f)
    lock["datasets"]["locomo"]["sha256"] = "0" * 64
    with pytest.raises(ValueError):
        fetch.verify_dataset("locomo", lock, str(tmp_path))
    with pytest.raises(FileNotFoundError):
        fetch.verify_dataset("locomo", lock, str(tmp_path / "missing"))


# -- strict model wrapper ---------------------------------------------------------------
class FakeLLM:
    model = "fake"

    def __init__(self, text="", structured=None, raw=""):
        self._t, self._s, self._r = text, structured, raw

    async def generate(self, system, user):
        return self._t

    async def generate_structured(self, system, user):
        return self._s

    async def judge_yes_no(self, prompt):
        return (self._r == "yes"), self._r


def test_strict_raises_on_failed_calls_instead_of_scoring_wrong():
    import run as runner
    bad = runner.strict(FakeLLM(text="", structured={}, raw=""))
    for call in (bad.generate("", "q"), bad.generate_structured("", "q"), bad.judge_yes_no("q")):
        with pytest.raises(runner.ModelCallFailed):
            run(call)
    good = runner.strict(FakeLLM(text="Paris", structured={"label": "WRONG"}, raw="no"))
    assert run(good.generate("", "q")) == "Paris"
    assert run(good.generate_structured("", "q")) == {"label": "WRONG"}
    assert run(good.judge_yes_no("q")) == (False, "no")


def test_default_cutoff_is_unlimited_only_for_full_history():
    import run as runner
    assert runner.parse_args(["--name", "x"]).cutoff_list == [runner.UNLIMITED]
    assert runner.parse_args(["--name", "x", "--backend", "vector"]).cutoff_list == [10, 20, 50, 200]
    assert runner.parse_args(["--name", "x", "--judge-url", "openai"]).judge_url == runner.OPENAI_URL


def test_context_guard_refuses_a_prompt_the_served_context_cannot_hold():
    import run as runner
    llm = runner.strict(FakeLLM(text="ok"), context_length=8192)
    short = "x" * (int((8192 - runner.RESERVED_TOKENS) * runner.CHARS_PER_TOKEN) - 10)
    assert run(llm.generate(system="", user=short)) == "ok"
    with pytest.raises(runner.ModelCallFailed, match="OLLAMA_CONTEXT_LENGTH"):
        run(llm.generate(system="", user="x" * 8192 * 4))
    # No known context (e.g. OpenAI): no guard.
    assert run(runner.strict(FakeLLM(text="ok")).generate("", "x" * 10**6)) == "ok"


# -- spend guard ------------------------------------------------------------------------
def test_spend_accumulates_persists_and_caps(tmp_path):
    import run as runner
    p = str(tmp_path / "spend.json")
    s = runner.Spend(p, cap_usd=0.01, untracked_usd=0.002)
    s.add("gpt-4o-mini", 20_000, 100)  # 0.003 + 0.00006
    assert abs(s.usd - (0.002 + 0.003 + 0.00006)) < 1e-9
    s.check()  # under the cap
    again = runner.Spend(p, cap_usd=0.01)  # --resume keeps counting, untracked not added twice
    assert abs(again.usd - s.usd) < 1e-12
    again.add("gpt-4o-mini-2024-07-18", 40_000, 0)  # dated model names use the same price
    with pytest.raises(runner.BudgetExceeded):
        again.check()
    assert json.load(open(p))["calls"] == 2


def test_unknown_paid_model_has_no_price():
    import run as runner
    assert runner.price_for("gpt-4o-mini") == (0.15, 0.60)
    assert runner.price_for("gpt-5") is None


def test_budget_stop_is_not_swallowed_by_a_retry_loop():
    # The harness retries on `except Exception`; the cap must still stop the run.
    import run as runner

    async def harness_like_call():
        for _ in range(5):
            try:
                raise runner.BudgetExceeded("cap")
            except Exception:
                continue
        return ""
    with pytest.raises(runner.BudgetExceeded):
        run(harness_like_call())


# -- tokens per answer --------------------------------------------------------------------
def test_answer_tokens_persist_and_summarise(tmp_path):
    import run as runner
    p = str(tmp_path / "answer_tokens.json")
    assert runner.AnswerTokens(p).stats() is None
    t = runner.AnswerTokens(p)
    for n in (100, 200, 300, 400):
        t.add(n)
    again = runner.AnswerTokens(p)  # --resume keeps earlier answers
    again.add(1000)
    assert again.stats() == {"answers": 5, "mean": 400, "p50": 300, "p95": 1000}


def test_make_llm_records_answer_prompt_tokens(tmp_path, monkeypatch):
    import types
    import run as runner

    class FakeCompletions:
        async def create(self, *a, **kw):
            return types.SimpleNamespace(usage=types.SimpleNamespace(prompt_tokens=1234, completion_tokens=5))

    class FakeClient:
        def __init__(self, **kw):
            self.model = kw["model"]
            self._client = types.SimpleNamespace(chat=types.SimpleNamespace(completions=FakeCompletions()))
            self.generate = self.generate_structured = self.judge_yes_no = None

    # The harness is not on the path in offline tests: stand in for its LLMClient module.
    for name in ("benchmarks", "benchmarks.common"):
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    monkeypatch.setitem(sys.modules, "benchmarks.common.llm_client",
                        types.SimpleNamespace(LLMClient=FakeClient))
    monkeypatch.setenv("OPENAI_API_KEY", "test-not-a-key")
    monkeypatch.setattr(runner, "SPEND", runner.Spend(str(tmp_path / "spend.json"), cap_usd=1.0))
    rec = runner.AnswerTokens(str(tmp_path / "answer_tokens.json"))
    client = runner.make_llm("gpt-4o-mini", runner.OPENAI_URL, thinking=False, record=rec)
    run(client._client.chat.completions.create(model="gpt-4o-mini", messages=[]))
    assert rec.tokens == [1234]
    assert runner.SPEND.data["calls"] == 1  # still counted by the spend guard


# -- re-grading with the Mem0 paper's judge prompt ---------------------------------------
def _raw(tmp_path, n=6):
    raw = tmp_path / "raw"
    raw.mkdir()
    for i in range(n):
        (raw / f"conv0_q{i}.json").write_text(json.dumps({
            "question_id": f"conv0_q{i}", "category_name": "temporal" if i % 2 else "single-hop",
            "question": f"q{i}?", "ground_truth_answer": f"gold {i}",
            "cutoff_results": {"top_100000": {"generated_answer": f"answer {i}",
                                              "judgment": "CORRECT" if i < 4 else "WRONG",
                                              "reason": "r"}}}))
    return str(raw)


def test_mem0_paper_prompt_is_pinned_and_formats():
    import regrade
    p = regrade.MEM0_PAPER_PROMPT
    assert "be generous with your grading" in p and p.count("{question}") == 1
    assert "(posed by one user to another user), \n" in p  # trailing spaces kept, as released
    msg = regrade.judge_message(p, {"question": "Q?", "gold": "G", "answer": "A"})
    assert "Question: Q?\nGold answer: G\nGenerated answer: A" in msg


def test_parse_label_reads_json_and_refuses_ambiguity():
    import regrade
    assert regrade.parse_label('{"label": "CORRECT"}') == "CORRECT"
    assert regrade.parse_label('Same date. {"label":"wrong"}') == "WRONG"
    assert regrade.parse_label("It is CORRECT") == "CORRECT"
    assert regrade.parse_label("CORRECT or WRONG?") is None
    assert regrade.parse_label("") is None


def test_regrade_loads_scores_samples_and_estimates(tmp_path):
    import csv as _csv
    import regrade
    rows = regrade.load_answers(_raw(tmp_path))
    assert len(rows) == 6 and rows[0]["cutoff"] == "top_100000"
    s = regrade.score([{"category": r["category"], "verdict": r["harness_verdict"]} for r in rows])
    assert s["overall"] == {"accuracy": 66.67, "correct": 4, "total": 6}
    path = str(tmp_path / "s.csv")
    a = regrade.write_sample(rows, 3, seed=1, path=path)
    b = regrade.write_sample(rows, 3, seed=1, path=path)
    assert [r["question_id"] for r in a] == [r["question_id"] for r in b]  # fixed seed, same sample
    lines = list(_csv.reader(open(path)))
    assert len(lines) == 4 and lines[0][7].startswith("reviewer_verdict")
    est = regrade.estimate(rows, regrade.MEM0_PAPER_PROMPT, "gpt-4o-mini")
    assert est["calls"] == 6 and est["usd_est"] > 0
