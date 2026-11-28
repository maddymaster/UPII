#!/usr/bin/env python3
"""Re-grade saved LoCoMo answers with another judge prompt, without re-answering.

The pinned harness's judge prompt is newer and more lenient than the one behind the
Mem0 paper's numbers. This script takes the answers a run already saved
(results/<run>/raw/*.json) and grades them again with the paper's original prompt,
so the two scores can be put side by side. Only the question, the gold answer and
the saved answer are sent to the judge.

    # cost estimate only: no calls
    python bench/memory/regrade.py --run locomo-full-gpt4omini --estimate
    # re-grade (paid endpoint: needs OPENAI_API_KEY and the human's approval)
    python bench/memory/regrade.py --run locomo-full-gpt4omini --judge-model gpt-4o-mini --judge-url openai
    # a fixed random sample of gradings as CSV, for hand-checking
    python bench/memory/regrade.py --run locomo-full-gpt4omini --sample 50 --seed 7 --sample-csv out.csv

Writes results/<run>/regrade-<prompt>/summary.json and grades.jsonl.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import glob
import hashlib
import json
import os
import random
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import run as runner  # noqa: E402  (spend guard, prices, URLs)

# Mem0's original LoCoMo judge, as released with the paper (arXiv 2504.19413 v1, 28 Apr 2025):
# https://github.com/mem0ai/mem0/blob/393a4fd5a6cfeb754857a2229726f567a9fadf36/evaluation/metrics/llm_judge.py
# Copied verbatim to prompts/mem0_paper_judge.txt (typographic quotes and trailing spaces kept). Their judge
# used gpt-4o-mini, temperature 0, JSON output, this text as the only (user) message.
MEM0_PAPER_SOURCE = ("mem0ai/mem0@393a4fd5a6cfeb754857a2229726f567a9fadf36:"
                     "evaluation/metrics/llm_judge.py")
MEM0_PAPER_PROMPT_FILE = os.path.join(HERE, "prompts", "mem0_paper_judge.txt")
MEM0_PAPER_PROMPT_SHA256 = "44fb3d8f7a1f37b2430772cf90518a32172e4056b7a0dec085402763fd179b9f"


def load_prompt(path: str, sha256: str) -> str:
    """The prompt file byte for byte (it has trailing spaces), refused if it was changed."""
    with open(path, "rb") as f:
        data = f.read()
    if hashlib.sha256(data).hexdigest() != sha256:
        raise SystemExit(f"{path} does not match its pinned sha256")
    return data.decode("utf-8")


MEM0_PAPER_PROMPT = load_prompt(MEM0_PAPER_PROMPT_FILE, MEM0_PAPER_PROMPT_SHA256)

PROMPTS = {"mem0-paper": (MEM0_PAPER_PROMPT, MEM0_PAPER_SOURCE)}

# Measured on full-history LoCoMo prompts with gpt-4o-mini (METHOD.md); used for estimates only.
CHARS_PER_TOKEN_GPT = 4.16
EST_OUTPUT_TOKENS = 60  # one-sentence reason plus {"label": ...}


def load_answers(raw_dir: str, cutoff: str | None = None) -> list[dict]:
    rows = []
    for path in sorted(glob.glob(os.path.join(raw_dir, "*.json"))):
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
        results = d.get("cutoff_results") or {}
        key = cutoff or (next(iter(results)) if results else None)
        r = results.get(key) if key else None
        if not r:
            continue
        rows.append({"question_id": d["question_id"], "category": d.get("category_name"),
                     "question": d["question"], "gold": str(d["ground_truth_answer"]),
                     "answer": r.get("generated_answer", ""), "harness_verdict": r.get("judgment"),
                     "harness_reason": r.get("reason", ""), "cutoff": key})
    return rows


def judge_message(prompt: str, row: dict) -> str:
    return prompt.format(question=row["question"], gold_answer=row["gold"], generated_answer=row["answer"])


def parse_label(text: str) -> str | None:
    """CORRECT/WRONG from the judge's reply, as Mem0's script reads it (JSON key "label")."""
    m = re.search(r"\{.*\}", text or "", re.S)
    if m:
        try:
            label = str(json.loads(m.group(0)).get("label", "")).strip().upper()
            if label in ("CORRECT", "WRONG"):
                return label
        except (json.JSONDecodeError, AttributeError):
            pass
    t = (text or "").upper()
    if ("CORRECT" in t) != ("WRONG" in t):
        return "CORRECT" if "CORRECT" in t else "WRONG"
    return None


def estimate(rows: list[dict], prompt: str, model: str) -> dict:
    chars = sum(len(judge_message(prompt, r)) for r in rows)
    n_in = int(chars / CHARS_PER_TOKEN_GPT)
    n_out = EST_OUTPUT_TOKENS * len(rows)
    price = runner.price_for(model)
    usd = None if price is None else n_in * price[0] / 1e6 + n_out * price[1] / 1e6
    return {"calls": len(rows), "input_tokens_est": n_in, "output_tokens_est": n_out,
            "usd_est": None if usd is None else round(usd, 4), "model": model}


def score(grades: list[dict]) -> dict:
    by_cat: dict[str, list[int]] = {}
    for g in grades:
        by_cat.setdefault(g["category"], []).append(g["verdict"] == "CORRECT")
    allv = [v for vs in by_cat.values() for v in vs]
    pct = lambda vs: round(100 * sum(vs) / len(vs), 2) if vs else None
    return {"overall": {"accuracy": pct(allv), "correct": sum(allv), "total": len(allv)},
            "by_category": {c: {"accuracy": pct(vs), "correct": sum(vs), "total": len(vs)}
                            for c, vs in sorted(by_cat.items())}}


def write_sample(rows: list[dict], n: int, seed: int, path: str) -> list[dict]:
    """A fixed random sample of the harness's gradings, with blank columns for a reviewer."""
    pick = random.Random(seed).sample(rows, min(n, len(rows)))
    pick.sort(key=lambda r: r["question_id"])
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["question_id", "category", "question", "gold_answer", "generated_answer",
                    "judge_verdict", "judge_reason", "reviewer_verdict (CORRECT/WRONG)", "reviewer_note"])
        for r in pick:
            w.writerow([r["question_id"], r["category"], r["question"], r["gold"], r["answer"],
                        r["harness_verdict"], r["harness_reason"], "", ""])
    return pick


async def regrade(rows, prompt, model, url, out_dir, concurrency=8):
    import openai
    paid = not runner.is_ollama(url)
    key = os.environ.get("OPENAI_API_KEY") if paid else "ollama"
    if not key:
        raise SystemExit("OPENAI_API_KEY is not set")
    if paid and runner.price_for(model) is None:
        raise SystemExit(f"no price for {model}; refusing to call a paid API unguarded")
    client = openai.AsyncOpenAI(base_url=url, api_key=key, timeout=120.0)
    done_path = os.path.join(out_dir, "grades.jsonl")
    done = {}
    if os.path.exists(done_path):
        with open(done_path, encoding="utf-8") as f:
            for line in f:
                g = json.loads(line)
                done[g["question_id"]] = g
    sem = asyncio.Semaphore(concurrency)
    lock = asyncio.Lock()

    async def one(r):
        if r["question_id"] in done:
            return
        async with sem:
            if paid:
                runner.SPEND.check()
            kw = {"model": model, "temperature": 0.0,
                  "messages": [{"role": "user", "content": judge_message(prompt, r)}],
                  "response_format": {"type": "json_object"}}
            if not paid:
                kw["reasoning_effort"] = "none"
            for attempt in range(3):
                try:
                    resp = await client.chat.completions.create(**kw)
                    break
                except openai.APIError:
                    if attempt == 2:
                        raise
                    await asyncio.sleep(2 * (attempt + 1))
            text = resp.choices[0].message.content or ""
            if paid:
                u = resp.usage
                runner.SPEND.add(model, u.prompt_tokens, u.completion_tokens)
            label = parse_label(text)
            if label is None:
                raise runner.ModelCallFailed(f"no CORRECT/WRONG label for {r['question_id']}: {text[:200]!r}")
            g = {"question_id": r["question_id"], "category": r["category"], "verdict": label,
                 "harness_verdict": r["harness_verdict"], "reply": text}
            async with lock:
                done[r["question_id"]] = g
                with open(done_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(g) + "\n")
                if len(done) % 50 == 0:
                    print(f"{len(done)}/{len(rows)} graded"
                          + (f" | {runner.SPEND.line()}" if paid else ""), flush=True)

    await asyncio.gather(*(one(r) for r in rows))
    return [done[r["question_id"]] for r in rows]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--run", required=True, help="results folder of a finished run")
    ap.add_argument("--prompt", default="mem0-paper", choices=sorted(PROMPTS))
    ap.add_argument("--cutoff", default=None, help="cutoff key in the raw files (default: the first)")
    ap.add_argument("--judge-model", default="gpt-4o-mini")
    ap.add_argument("--judge-url", default="openai")
    ap.add_argument("--estimate", action="store_true", help="print the cost estimate and exit")
    ap.add_argument("--max-spend-usd", type=float, default=2.0)
    ap.add_argument("--sample", type=int, default=0, help="write this many gradings as CSV and exit")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--sample-csv", default=None)
    args = ap.parse_args(argv)

    run_dir = os.path.join(HERE, "results", args.run)
    rows = load_answers(os.path.join(run_dir, "raw"), args.cutoff)
    if not rows:
        raise SystemExit(f"no saved answers in {run_dir}/raw")
    prompt, source = PROMPTS[args.prompt]

    if args.sample:
        path = args.sample_csv or os.path.join(run_dir, f"sample-{args.sample}-seed{args.seed}.csv")
        pick = write_sample(rows, args.sample, args.seed, path)
        print(f"wrote {len(pick)} gradings to {path}")
        return 0
    if args.estimate:
        print(json.dumps(estimate(rows, prompt, args.judge_model), indent=2))
        return 0

    url = runner.resolve_url(args.judge_url)
    out_dir = os.path.join(run_dir, f"regrade-{args.prompt}-{args.judge_model.replace(':', '_')}")
    os.makedirs(out_dir, exist_ok=True)
    if not runner.is_ollama(url):
        runner.SPEND = runner.Spend(os.path.join(out_dir, "spend.json"), args.max_spend_usd)
    t0 = time.time()
    try:
        grades = asyncio.run(regrade(rows, prompt, args.judge_model, url, out_dir))
    except runner.BudgetExceeded as e:
        print(f"stopped: {e}", file=sys.stderr)
        return 3
    summary = {"run": args.run, "prompt": args.prompt, "prompt_source": source,
               "judge": {"model": args.judge_model, "endpoint": url}, "cutoff": rows[0]["cutoff"],
               "regrade": score(grades),
               "harness_judge": score([{"category": r["category"], "verdict": r["harness_verdict"]}
                                       for r in rows]),
               "disagreements": sum(g["verdict"] != g["harness_verdict"] for g in grades),
               "spend": dict(runner.SPEND.data) if runner.SPEND else None,
               "wall_seconds": round(time.time() - t0)}
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
    print(json.dumps({k: summary[k] for k in ("regrade", "harness_judge", "disagreements")}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
