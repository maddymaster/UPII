#!/usr/bin/env python3
"""Run LoCoMo or LongMemEval from the pinned memory-benchmarks harness on one backend.

The harness's own ingest, answer prompt, judge prompt and metrics are used as they
are; only the memory client is replaced by a backend from bench/memory/backends.
Inputs are checked against HARNESS.lock before anything runs.

Writes bench/memory/results/<name>/:
    REPORT.md     summary, settings, pins and model digests
    summary.json  the same, machine-readable
    raw/          per-question JSON from the harness
None of it is committed: run output stays local until the G1 benchmark gate.

Examples:
    # full-history baseline, LoCoMo, all 10 conversations, local models
    python bench/memory/run.py --benchmark locomo --backend full_history --name locomo-full-local

    # one-conversation smoke test of another backend
    python bench/memory/run.py --benchmark locomo --backend vector --conversations 0 --max-questions 5 --name smoke-vector

Models are reached through OpenAI-compatible endpoints. Local Ollama is the default
(answerer on the Spark through an SSH tunnel, judge on this machine). For OpenAI,
pass --answerer-url openai / --judge-url openai and set OPENAI_API_KEY; that sends
the public benchmark text to OpenAI and costs money (a human gate: see METHOD.md).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import platform
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from importlib import metadata as importlib_metadata

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)  # backends, fetch
if os.path.join(REPO, "src") not in sys.path:
    sys.path.insert(1, os.path.join(REPO, "src"))

import fetch  # noqa: E402
from backends import BACKENDS, make_backend  # noqa: E402

# Local default (see METHOD.md): the answerer needs the long context (full history is up to
# ~37k tokens), which the Spark serves (65536); the judge's prompts are short, so the Mac's 32768 is enough.
DEFAULT_ANSWERER = "qwen3.6:35b-a3b-mtp-q4_K_M"
DEFAULT_ANSWERER_URL = "http://127.0.0.1:11545/v1"  # ssh -f -N -L 127.0.0.1:11545:127.0.0.1:11434 spark
DEFAULT_JUDGE = "qwen3.8:27b"
DEFAULT_JUDGE_URL = "http://127.0.0.1:11434/v1"
MEM0_LLM_URL = "http://127.0.0.1:11434/v1"  # mem0_oss fact extraction: this machine's Ollama
OPENAI_URL = "https://api.openai.com/v1"
# Conservative estimate for the context guard: measured 3.76 chars/token on full-history
# LoCoMo prompts and 3.04 on upii chunk prompts (qwen3.8 tokenizer).
CHARS_PER_TOKEN = 3.0
RESERVED_TOKENS = 4096  # the harness asks for up to 4096 output tokens
UNLIMITED = 100_000  # "cutoff" that keeps every memory (full-history backend)
LOG = logging.getLogger("bench.memory")

# OpenAI list prices, USD per 1M tokens (input, output), checked 2026-11-24. A paid model that is
# not listed here is refused, so the spend guard never runs blind.
PRICES_PER_M = {"gpt-4o-mini": (0.15, 0.60)}
DEFAULT_MAX_SPEND_USD = 15.0


class BudgetExceeded(BaseException):
    """Spend cap reached. A BaseException, so the harness's ``except Exception`` retry loop
    cannot swallow it: the run stops at once."""


def price_for(model: str):
    for name, price in PRICES_PER_M.items():
        if model == name or model.startswith(name + "-"):
            return price
    return None


class Spend:
    """Running cost estimate of paid API calls, kept in ``spend.json`` so ``--resume`` keeps
    counting. Tokens come from each response's ``usage``; cost from PRICES_PER_M."""

    def __init__(self, path: str, cap_usd: float, untracked_usd: float = 0.0):
        self.path, self.cap = path, cap_usd
        self.data = {"input_tokens": 0, "output_tokens": 0, "calls": 0, "usd": 0.0,
                     "untracked_usd": 0.0, "cap_usd": cap_usd}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                self.data.update(json.load(f))
        self.data["cap_usd"] = cap_usd
        if untracked_usd and not self.data.get("untracked_usd"):
            self.data["untracked_usd"] = untracked_usd
        self.save()

    @property
    def usd(self) -> float:
        return self.data["usd"] + self.data["untracked_usd"]

    def check(self) -> None:
        if self.usd >= self.cap:
            raise BudgetExceeded(f"estimated spend ${self.usd:.4f} reached the cap ${self.cap:.2f}")

    def add(self, model: str, input_tokens: int, output_tokens: int) -> None:
        p_in, p_out = price_for(model)
        self.data["input_tokens"] += input_tokens
        self.data["output_tokens"] += output_tokens
        self.data["calls"] += 1
        self.data["usd"] += input_tokens * p_in / 1e6 + output_tokens * p_out / 1e6
        self.save()

    def save(self) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, sort_keys=True)
        os.replace(tmp, self.path)

    def line(self) -> str:
        return f"spend ${self.usd:.4f} of ${self.cap:.2f}"


SPEND: "Spend | None" = None


class AnswerTokens:
    """Prompt tokens of every answer call, as the answering model reported them.

    Accuracy alone has little headroom (full history scores above 90% on this
    harness), so every report gives the context each answer cost beside it. Kept in
    ``answer_tokens.json`` so ``--resume`` keeps earlier questions.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        self.tokens: list[int] = []
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                self.tokens = list(json.load(f).get("prompt_tokens", []))

    def add(self, prompt_tokens: int) -> None:
        self.tokens.append(int(prompt_tokens))
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"prompt_tokens": self.tokens}, f)
        os.replace(tmp, self.path)

    def stats(self) -> dict | None:
        if not self.tokens:
            return None
        t = sorted(self.tokens)
        pick = lambda q: t[min(len(t) - 1, int(q * len(t)))]
        return {"answers": len(t), "mean": round(sum(t) / len(t)), "p50": pick(0.5), "p95": pick(0.95)}


# -- models ---------------------------------------------------------------------
def resolve_url(url: str) -> str:
    return OPENAI_URL if url == "openai" else url


def is_ollama(url: str) -> bool:
    return "api.openai.com" not in url


def ollama_root(url: str) -> str:
    return url[:-3] if url.rstrip("/").endswith("/v1") else url.rstrip("/")


def _get_json(url: str, timeout: float = 10.0):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.load(r)


def model_info(url: str, model: str) -> dict:
    """Name, endpoint and (for Ollama) the exact build digest and served context."""
    info = {"model": model, "endpoint": url}
    if not is_ollama(url):
        info["provider"] = "openai"
        return info
    info["provider"] = "ollama"
    root = ollama_root(url)
    try:
        info["ollama_version"] = _get_json(f"{root}/api/version").get("version")
        for m in _get_json(f"{root}/api/tags").get("models", []):
            if m.get("name") == model:
                info["digest"] = m.get("digest")
                info["quantization"] = (m.get("details") or {}).get("quantization_level")
        for m in _get_json(f"{root}/api/ps").get("models", []):
            if m.get("name") == model:
                info["context_length"] = m.get("context_length")
    except OSError as e:
        info["error"] = f"could not query Ollama: {e}"
    return info


def make_llm(model: str, url: str, thinking: bool, record: "AnswerTokens | None" = None):
    """The harness's LLMClient, pointed at ``url``; thinking off unless asked for.

    With ``record``, the prompt tokens each call reports are kept (for the answerer).
    """
    from benchmarks.common.llm_client import LLMClient

    key = os.environ.get("OPENAI_API_KEY") if not is_ollama(url) else "ollama"
    if not key:
        raise SystemExit("OPENAI_API_KEY is not set (needed for --*-url openai)")
    client = LLMClient(model=model, provider="openai", api_key=key, base_url=url, timeout=600.0)
    if not is_ollama(url):
        if price_for(model) is None:
            raise SystemExit(f"no price for {model} in PRICES_PER_M; refusing to call a paid API unguarded")
        if SPEND is None:
            raise SystemExit("paid endpoint without a spend guard")
        completions = client._client.chat.completions
        paid_create = completions.create

        async def create_guarded(*a, **kw):
            SPEND.check()  # before: never start a call over the cap
            resp = await paid_create(*a, **kw)
            u = getattr(resp, "usage", None)
            if u is None:  # no usage reported: count the request text conservatively
                n_in = sum(len(str(m.get("content", ""))) for m in kw.get("messages", [])) // 3
                n_out = kw.get("max_tokens") or kw.get("max_completion_tokens") or 4096
            else:
                n_in, n_out = u.prompt_tokens, u.completion_tokens
            SPEND.add(model, n_in, n_out)
            SPEND.check()  # after: stop as soon as the cap is reached
            return resp

        completions.create = create_guarded
    if is_ollama(url) and not thinking:
        completions = client._client.chat.completions
        create = completions.create

        async def create_no_think(*a, **kw):
            kw.setdefault("reasoning_effort", "none")
            return await create(*a, **kw)

        completions.create = create_no_think
    if record is not None:
        completions = client._client.chat.completions
        counted_create = completions.create

        async def create_counted(*a, **kw):
            resp = await counted_create(*a, **kw)
            u = getattr(resp, "usage", None)
            if u is not None and getattr(u, "prompt_tokens", None) is not None:
                record.add(u.prompt_tokens)
            return resp

        completions.create = create_counted
    ctx = None
    if is_ollama(url):
        # Load the model once so /api/ps reports the context it is served with.
        import openai
        openai.OpenAI(base_url=url, api_key="ollama").chat.completions.create(
            model=model, messages=[{"role": "user", "content": "ok"}], max_tokens=1,
            reasoning_effort="none")
        ctx = model_info(url, model).get("context_length")
    return strict(client, context_length=ctx)


class ModelCallFailed(RuntimeError):
    """A model call failed after the harness's retries."""


def strict(client, context_length: int | None = None):
    """Make a failed call raise instead of returning "" / {}.

    The harness scores an empty answer or an empty judge reply as WRONG, so a
    dropped connection would silently lower the score. Raising stops the run;
    the question is not saved, and ``--resume`` continues from it.
    """
    gen, structured, yes_no = client.generate, client.generate_structured, client.judge_yes_no

    async def generate(*a, **kw):
        user = kw.get("user", a[1] if len(a) > 1 else "")
        if context_length and len(user) / CHARS_PER_TOKEN > context_length - RESERVED_TOKENS:
            # Ollama does not reject an over-long prompt: it truncates or stalls.
            raise ModelCallFailed(
                f"{client.model}: prompt of ~{int(len(user) / CHARS_PER_TOKEN)} tokens does not fit "
                f"the served context of {context_length}; raise OLLAMA_CONTEXT_LENGTH for that "
                "Ollama server, or use smaller --cutoffs")
        out = await gen(*a, **kw)
        if not out:
            raise ModelCallFailed(f"{client.model}: empty answer after retries")
        return out

    async def generate_structured(*a, **kw):
        out = await structured(*a, **kw)
        if not out:
            raise ModelCallFailed(f"{client.model}: no judge verdict after retries")
        return out

    async def judge_yes_no(prompt):
        ok, raw = await yes_no(prompt)
        if not raw:
            raise ModelCallFailed(f"{client.model}: no judge verdict after retries")
        return ok, raw

    client.generate, client.generate_structured, client.judge_yes_no = generate, generate_structured, judge_yes_no
    return client


# -- environment record ---------------------------------------------------------
def git_commit(path: str) -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=path, check=True,
                              capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def git_dirty(path: str) -> bool:
    try:
        out = subprocess.run(["git", "status", "--porcelain", "--", "src", "bench/memory"],
                             cwd=path, check=True, capture_output=True, text=True).stdout
        return bool(out.strip())
    except (OSError, subprocess.CalledProcessError):
        return True


def package_versions() -> dict:
    out = {}
    for p in ("openai", "aiohttp", "pydantic", "mem0ai", "qdrant-client",
              "sentence-transformers", "torch", "lancedb", "numpy"):
        try:
            out[p] = importlib_metadata.version(p)
        except importlib_metadata.PackageNotFoundError:
            pass
    return out


# -- LoCoMo -----------------------------------------------------------------------
async def run_locomo(args, backend, answerer, judge, raw_dir: str, run_id: str) -> list[dict]:
    from benchmarks.common.utils import GracefulShutdown, save_result_json
    from benchmarks.locomo import prompts as P
    from benchmarks.locomo import run as L

    if args.backend == "full_history":
        P.ANSWERER_MEMORY_LIMIT = UNLIMITED  # the whole conversation, not the top 200
    dataset = L.load_dataset(args.dataset_path)
    categories = [int(c) for c in args.categories.split(",")]
    conv_indices = [int(c) for c in args.conversations.split(",")]
    shutdown = GracefulShutdown()
    results: list[dict] = []

    with shutdown:
        for ci in conv_indices:
            entry = dataset[ci]
            # Backends live in memory, so ingest every run: the harness's ingest
            # checkpoints go to a throwaway folder, never to raw/.
            ok, user_id, _ = await L.ingest_conversation(ci, entry, backend, LOG, run_id, args.name,
                                                         tempfile.mkdtemp(), shutdown, debug=False)
            if not ok:
                LOG.warning("ingest reported failures for conversation %d", ci)
            sessions = L.get_sorted_sessions(entry["conversation"])
            ref_date = sessions[-1][1] if sessions else None
            qs = [(qi, qa) for qi, qa in enumerate(entry.get("qa", []))
                  if qa.get("category") in categories]
            if args.max_questions is not None:
                qs = qs[: args.max_questions]
            for n, (qi, qa) in enumerate(qs, 1):
                if shutdown.requested:
                    break
                path = os.path.join(raw_dir, f"conv{ci}_q{qi}.json")
                if os.path.exists(path):
                    with open(path) as f:
                        results.append(json.load(f))
                    continue
                t0 = time.monotonic()
                r = await L.process_question(
                    qa=qa, qa_idx=qi, conv_idx=ci, user_id=user_id, mem0=backend,
                    answerer=answerer, judge_llm=judge, cutoffs=args.cutoff_list,
                    top_k=args.top_k, reference_date_human=ref_date, user_profile=None,
                    evidence_lookup=None, predict_only=False, logger=LOG)
                r["elapsed_s"] = round(time.monotonic() - t0, 2)
                save_result_json(path, r)
                results.append(r)
                print(f"conv {ci} q {n}/{len(qs)} {r['elapsed_s']}s "
                      + " ".join(f"{k}={v['judgment']}" for k, v in r["cutoff_results"].items())
                      + (f" | {SPEND.line()}" if SPEND else ""), flush=True)
            await backend.delete_user(user_id)
    return results


def locomo_metrics(results: list[dict], cutoffs: list[int]) -> dict:
    from benchmarks.locomo import run as L
    return L.compute_locomo_metrics(results, cutoffs)


# -- LongMemEval -------------------------------------------------------------------
async def run_longmemeval(args, backend, answerer, judge, raw_dir: str, run_id: str) -> list[dict]:
    from benchmarks.common.utils import GracefulShutdown, save_result_json
    from benchmarks.longmemeval import run as M

    questions = M.load_dataset(args.dataset_path)
    if args.max_questions is not None:
        questions = M.sample_questions_stratified(questions, per_type=max(1, args.max_questions // 6))
        questions = questions[: args.max_questions]
    shutdown = GracefulShutdown()
    results = []
    with shutdown:
        for n, q in enumerate(questions, 1):
            if shutdown.requested:
                break
            path = os.path.join(raw_dir, f"{q['question_id']}.json")
            if os.path.exists(path):
                with open(path) as f:
                    results.append(json.load(f))
                continue
            ok, user_id, _ = await M.ingest_question(q, backend, LOG, run_id, tempfile.mkdtemp(),
                                                     shutdown, debug=False)
            t0 = time.monotonic()
            r = await M.process_question_answerer(
                question=q, user_id=user_id, mem0=backend, answerer=answerer, judge_llm=judge,
                cutoffs=args.cutoff_list, top_k=args.top_k, user_profile=None,
                predict_only=False, logger=LOG)
            r["elapsed_s"] = round(time.monotonic() - t0, 2)
            save_result_json(path, r)
            results.append(r)
            await backend.delete_user(user_id)
            print(f"q {n}/{len(questions)} {r['elapsed_s']}s "
                  + " ".join(f"{k}={v['judgment']}" for k, v in r["cutoff_results"].items())
                  + (f" | {SPEND.line()}" if SPEND else ""), flush=True)
    return results


def longmemeval_metrics(results: list[dict], cutoffs: list[int]) -> dict:
    from benchmarks.longmemeval import run as M
    return M.compute_longmemeval_metrics(results, cutoffs)


# -- report -----------------------------------------------------------------------------
def overall_score(metrics: dict) -> dict:
    """label -> overall accuracy, whatever key the harness used for it."""
    out = {}
    for label, m in metrics.items():
        if not isinstance(m, dict):
            continue
        for key in ("overall", "overall_accuracy", "accuracy", "j_score", "score"):
            v = m.get(key)
            if isinstance(v, dict):
                v = v.get("accuracy", v.get("score", v.get("mean")))
            if isinstance(v, (int, float)):
                out[label] = v
                break
    return out


def write_report(out_dir: str, summary: dict) -> str:
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
        f.write("\n")
    s = summary
    lines = [
        f"# Memory benchmark: {s['benchmark']} / {s['backend']} ({s['name']})",
        "",
        "Internal. Do not publish or quote any number here without human approval (GATES.md).",
        "",
        "LoCoMo is CC BY-NC 4.0: LoCoMo results may appear in the public UPII repo only, never in",
        "Smritium product, sales, investor or website material (METHOD.md, Licences)."
        if s["benchmark"] == "locomo" else "Licence of this dataset: see METHOD.md, Licences.",
        "",
        f"Generated by `{s['command']}`.",
        "",
        "## Result",
        "",
        "| Cutoff | Overall accuracy |",
        "|---|---|",
    ]
    for label, v in s["overall"].items():
        lines.append(f"| {label} | {v:.3f} |" if isinstance(v, float) and v <= 1 else f"| {label} | {v} |")
    lines += [
        "",
        f"- Questions scored: {s['questions']} (categories {s.get('categories', 'n/a')})",
        f"- Conversations / questions in scope: {s.get('scope')}",
        f"- Mean seconds per question (answer + judge): {s['mean_seconds_per_question']}",
        (f"- Answer context (prompt tokens per answer, as the answerer reported): mean "
         f"{s['answer_prompt_tokens']['mean']:,}, p50 {s['answer_prompt_tokens']['p50']:,}, "
         f"p95 {s['answer_prompt_tokens']['p95']:,} over {s['answer_prompt_tokens']['answers']} answer calls"
         if s.get("answer_prompt_tokens") else "- Answer context: not recorded"),
        f"- Wall time: {s['wall_seconds']} s",
        "",
        "## Settings",
        "",
        f"- Answerer: `{s['answerer']['model']}` via {s['answerer']['provider']}"
        f" (digest `{s['answerer'].get('digest', 'n/a')}`, context {s['answerer'].get('context_length', 'n/a')})",
        f"- Judge: `{s['judge']['model']}` via {s['judge']['provider']}"
        f" (digest `{s['judge'].get('digest', 'n/a')}`, context {s['judge'].get('context_length', 'n/a')})",
        f"- Thinking: {'on' if s['thinking'] else 'off'} for Ollama models; temperature 0",
        (f"- Paid API spend (estimated from list prices): ${s['spend']['total_usd']:.4f} "
         f"({s['spend']['input_tokens']:,} input and {s['spend']['output_tokens']:,} output tokens, "
         f"{s['spend']['calls']} calls; cap ${s['spend']['cap_usd']:.2f})" if s.get("spend") else
         "- Paid API spend: none (local models only)"),
        f"- Top-k {s['top_k']}, cutoffs {s['cutoffs']}",
        f"- Harness `{s['harness_commit']}`; dataset sha256 `{s['dataset_sha256']}`",
        f"- upii commit `{s['upii_commit']}`{' (with local changes)' if s['upii_dirty'] else ''}",
        f"- Python {s['python']}, {s['platform']}; packages {s['packages']}",
        f"- Started {s['started']}, finished {s['finished']}",
        "",
        "## Metrics (harness output)",
        "",
        "```json",
        json.dumps(s["metrics"], indent=2, sort_keys=True),
        "```",
        "",
    ]
    path = os.path.join(out_dir, "REPORT.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


# -- main -------------------------------------------------------------------------------
def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--benchmark", choices=["locomo", "longmemeval"], default="locomo")
    ap.add_argument("--backend", choices=BACKENDS, default="full_history")
    ap.add_argument("--name", required=True, help="results folder name under bench/memory/results/")
    ap.add_argument("--answerer-model", default=DEFAULT_ANSWERER)
    ap.add_argument("--answerer-url", default=DEFAULT_ANSWERER_URL, help="OpenAI-compatible /v1 URL, or 'openai'")
    ap.add_argument("--judge-model", default=DEFAULT_JUDGE)
    ap.add_argument("--judge-url", default=DEFAULT_JUDGE_URL, help="OpenAI-compatible /v1 URL, or 'openai'")
    ap.add_argument("--thinking", action="store_true", help="leave Ollama model thinking on (default off)")
    ap.add_argument("--conversations", default="0,1,2,3,4,5,6,7,8,9", help="LoCoMo conversation indices")
    ap.add_argument("--categories", default="1,2,3,4", help="LoCoMo categories (5 = adversarial, excluded as in the harness)")
    ap.add_argument("--max-questions", type=int, default=None, help="per conversation (LoCoMo) or total (LongMemEval)")
    ap.add_argument("--top-k", type=int, default=200)
    ap.add_argument("--cutoffs", default=None, help="default: unlimited for full_history, else 10,20,50,200")
    ap.add_argument("--mem0-llm", default="qwen3.8:27b", help="extraction model for mem0_oss (this machine's Ollama)")
    ap.add_argument("--upii-min-similarity", type=float, default=None)
    ap.add_argument("--resume", action="store_true", help="keep raw/ results of an earlier run with this name")
    ap.add_argument("--max-spend-usd", type=float, default=DEFAULT_MAX_SPEND_USD,
                    help="stop when the estimated paid-API spend reaches this (default 15)")
    ap.add_argument("--untracked-spend-usd", type=float, default=0.0,
                    help="spend from calls made before the guard existed, counted toward the cap")
    args = ap.parse_args(argv)
    args.answerer_url = resolve_url(args.answerer_url)
    args.judge_url = resolve_url(args.judge_url)
    if args.cutoffs is None:
        args.cutoffs = str(UNLIMITED) if args.backend == "full_history" else "10,20,50,200"
    args.cutoff_list = [int(c) for c in args.cutoffs.split(",") if c.strip()]
    return args


async def amain(args) -> dict:
    lock = fetch.load_lock()
    harness_dir = fetch.HARNESS_DIR
    if fetch.harness_commit(harness_dir) != lock["harness"]["commit"]:
        raise SystemExit("pinned harness not fetched; run: python bench/memory/fetch.py")
    sys.path.insert(0, harness_dir)
    args.dataset_path = fetch.verify_dataset(args.benchmark, lock)

    out_dir = os.path.join(HERE, "results", args.name)
    raw_dir = os.path.join(out_dir, "raw")
    if os.path.isdir(raw_dir) and os.listdir(raw_dir) and not args.resume:
        raise SystemExit(f"{raw_dir} has results; pass --resume or pick another --name")
    os.makedirs(raw_dir, exist_ok=True)

    global SPEND
    if not (is_ollama(args.answerer_url) and is_ollama(args.judge_url)):
        SPEND = Spend(os.path.join(out_dir, "spend.json"), args.max_spend_usd, args.untracked_spend_usd)
        print(f"spend guard on: cap ${args.max_spend_usd:.2f}; {SPEND.line()}", flush=True)
    answer_tokens = AnswerTokens(os.path.join(out_dir, "answer_tokens.json"))
    answerer = make_llm(args.answerer_model, args.answerer_url, args.thinking, record=answer_tokens)
    judge = make_llm(args.judge_model, args.judge_url, args.thinking)
    kwargs = {}
    if args.backend == "mem0_oss":
        kwargs = {"llm_model": args.mem0_llm, "ollama_url": ollama_root(MEM0_LLM_URL)}
    if args.backend == "upii":
        kwargs = {"min_similarity": args.upii_min_similarity}
    backend = make_backend(args.backend, **kwargs)

    started = datetime.now(timezone.utc)
    t0 = time.monotonic()
    run_id = uuid.uuid4().hex[:8]
    async with backend:
        if args.benchmark == "locomo":
            results = await run_locomo(args, backend, answerer, judge, raw_dir, run_id)
            metrics = locomo_metrics(results, args.cutoff_list) if results else {}
        else:
            results = await run_longmemeval(args, backend, answerer, judge, raw_dir, run_id)
            metrics = longmemeval_metrics(results, args.cutoff_list) if results else {}
    wall = time.monotonic() - t0
    secs = [r.get("elapsed_s") for r in results if r.get("elapsed_s") is not None]

    summary = {
        "name": args.name, "benchmark": args.benchmark, "backend": args.backend,
        "command": "python bench/memory/run.py " + " ".join(sys.argv[1:]),
        "questions": len(results),
        "scope": (f"conversations {args.conversations}, max {args.max_questions} per conversation"
                  if args.benchmark == "locomo" else f"max {args.max_questions} questions"),
        "categories": args.categories if args.benchmark == "locomo" else None,
        "overall": overall_score(metrics), "metrics": metrics,
        "mean_seconds_per_question": round(sum(secs) / len(secs), 1) if secs else None,
        "wall_seconds": round(wall),
        "answerer": model_info(args.answerer_url, args.answerer_model),
        "judge": model_info(args.judge_url, args.judge_model),
        "thinking": args.thinking, "top_k": args.top_k, "cutoffs": args.cutoff_list,
        "spend": dict(SPEND.data, total_usd=round(SPEND.usd, 4)) if SPEND else None,
        "answer_prompt_tokens": answer_tokens.stats(),
        "context_guard_chars_per_token": CHARS_PER_TOKEN,
        "harness_commit": lock["harness"]["commit"],
        "dataset_sha256": lock["datasets"][args.benchmark]["sha256"],
        "upii_commit": git_commit(REPO), "upii_dirty": git_dirty(REPO),
        "python": platform.python_version(), "platform": platform.platform(),
        "packages": package_versions(),
        "started": started.isoformat(timespec="seconds"),
        "finished": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    print(f"report: {write_report(out_dir, summary)}")
    print("overall:", summary["overall"])
    return summary


def main(argv=None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    args = parse_args(argv)
    try:
        asyncio.run(amain(args))
    except BudgetExceeded as e:
        print(f"stopped: {e}. Saved questions are kept; spend is in spend.json.", file=sys.stderr)
        return 3
    except ModelCallFailed as e:
        print(f"stopped: {e}. Saved questions are kept; rerun the same command with --resume.",
              file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
