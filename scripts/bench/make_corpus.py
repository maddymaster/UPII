#!/usr/bin/env python3
"""Generate a deterministic synthetic corpus for the Phase 1 benchmark.

The corpus is a pure function of ``--seed``, ``--docs`` and ``--paras``: the same
arguments produce byte-identical files on any machine. That is what makes an
ingestion-throughput or retrieval-latency number comparable across hardware —
the corpus is never the variable.

Each document is topical (a project, a subject, recurring domain terms) rather
than lorem ipsum, so semantic retrieval has real signal to rank on. Alongside the
documents it writes ``queries.txt``: one natural-language query per sampled
document, which `benchmark.py` replays to measure retrieval latency.

Examples
--------
    python scripts/bench/make_corpus.py --docs 100 --out /tmp/corpus
    python scripts/bench/make_corpus.py --docs 12000 --paras 60 --out /tmp/corpus
"""

import argparse
import os
import random
from pathlib import Path

PROJECTS = [
    "Project Omega", "Project Atlas", "Project Borealis", "Project Nimbus",
    "Project Meridian", "Project Cascade", "Project Halcyon", "Project Vertex",
]

# (subject, terms that recur in that subject's paragraphs)
SUBJECTS = [
    ("ingestion latency", ["watcher", "debounce", "backlog", "throughput"]),
    ("retrieval quality", ["recall", "reranking", "fusion", "embedding"]),
    ("storage layout", ["sqlite", "lancedb", "vector", "index"]),
    ("privacy posture", ["on-device", "consent", "telemetry", "sovereignty"]),
    ("capacity planning", ["disk", "memory", "growth", "shard"]),
    ("incident review", ["postmortem", "regression", "rollback", "alert"]),
    ("release process", ["installer", "signing", "notarization", "tag"]),
    ("hiring plan", ["headcount", "onboarding", "interview", "offer"]),
]

WORDS = (
    "measured baseline target median throughput corpus chunk hash pipeline cache "
    "budget deadline owner blocker tradeoff rollout canary rollback threshold "
    "quarter roadmap dependency mitigation estimate variance capacity retention "
    "latency percentile ingest query rank signal weight temporal relational"
).split()


def make_doc(rng: random.Random, idx: int, paras: int) -> str:
    project = PROJECTS[idx % len(PROJECTS)]
    subject, terms = SUBJECTS[(idx // len(PROJECTS)) % len(SUBJECTS)]
    lines = [f"# {project} — {subject} notes (doc {idx:06d})", ""]
    for p in range(paras):
        body = " ".join(rng.choice(WORDS) for _ in range(12))
        term = rng.choice(terms)
        # The [doc/para] marker keeps every ~1KB window distinct, so no two chunks
        # collide by accident and the chunk count scales predictably with --paras.
        lines.append(f"[doc {idx:06d} para {p:04d}] {project} {subject}: {body} {term}.")
    return "\n".join(lines) + "\n"


def make_query(idx: int) -> str:
    project = PROJECTS[idx % len(PROJECTS)]
    subject, _ = SUBJECTS[(idx // len(PROJECTS)) % len(SUBJECTS)]
    return f"What did we decide about {subject} on {project}?"


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--docs", type=int, default=12000, help="number of documents (default 12000)")
    ap.add_argument("--paras", type=int, default=60, help="paragraphs per doc (drives chunks/doc)")
    ap.add_argument("--queries", type=int, default=50, help="queries to emit into queries.txt")
    ap.add_argument("--seed", type=int, default=1729, help="RNG seed — fixes the corpus")
    ap.add_argument("--out", required=True, help="output directory")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    rng = random.Random(args.seed)
    total_chars = 0
    for i in range(args.docs):
        text = make_doc(rng, i, args.paras)
        total_chars += len(text)
        (out / f"doc_{i:06d}.md").write_text(text, encoding="utf-8")

    # Spread the sampled queries across the corpus rather than clustering at the front.
    step = max(1, args.docs // max(1, args.queries))
    picks = [i for i in range(0, args.docs, step)][: args.queries]
    (out / "queries.txt").write_text(
        "\n".join(make_query(i) for i in picks) + "\n", encoding="utf-8"
    )

    print(f"corpus: {args.docs} docs x {args.paras} paras -> {out}")
    print(f"  seed={args.seed} (deterministic)  |  {total_chars / 1e6:.1f} MB of text")
    print(f"  queries: {len(picks)} -> {out / 'queries.txt'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
