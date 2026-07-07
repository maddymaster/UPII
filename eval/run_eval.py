#!/usr/bin/env python3
"""Run the labelled retrieval eval and write a report.

Loads ``dataset/labels.json``, runs every query through the *current* retrieval
path, and computes Recall@{1,5,10}, MRR and nDCG@10. Writes a human-readable
``results/REPORT.md`` and a machine-readable ``results/results.json``, and prints a
summary. Exit code is non-zero if Recall@10 falls below the grant target (0.85),
so this can gate CI.

Usage:
    python eval/run_eval.py                 # score against committed labels
    python eval/run_eval.py --rebuild        # rebuild labels from corpus first
    python eval/run_eval.py --target 0.85    # override the Recall@10 gate
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eval import harness, metrics  # noqa: E402

# Cutoffs required by the grant demonstration.
KS = (1, 5, 10)
NDCG_K = 10
DEFAULT_TARGET_RECALL_AT_10 = 0.85


def _load_labels() -> dict:
    if not os.path.exists(harness.LABELS_PATH):
        raise SystemExit(
            f"No labels at {harness.LABELS_PATH}. Run:  python eval/build_dataset.py build"
        )
    with open(harness.LABELS_PATH) as fh:
        return json.load(fh)


def evaluate(target: float) -> dict:
    labels = _load_labels()

    # Fail loudly if the corpus drifted from what the labels were built against —
    # otherwise chunk ids won't line up and every query silently scores 0.
    current_fp = harness.corpus_fingerprint()
    if labels.get("corpus_fingerprint") != current_fp:
        raise SystemExit(
            "Corpus fingerprint mismatch: labels.json was built against a different\n"
            "corpus. Rebuild with:  python eval/run_eval.py --rebuild"
        )

    # Rebuild the isolated index so retrieval runs against the labelled corpus.
    harness.ingest_corpus(reset=True)

    per_query = []
    for q in labels["queries"]:
        relevant = q["relevant_chunk_ids"]
        if not relevant:
            # Not scorable; record and skip so the mean isn't polluted.
            per_query.append({"id": q["id"], "query": q["query"], "scorable": False})
            continue

        ranked = harness.retrieve(q["query"], limit=max(KS))
        row = {
            "id": q["id"],
            "query": q["query"],
            "scorable": True,
            "n_relevant": len(relevant),
            "n_retrieved": len(ranked),
            "first_relevant_rank": _first_rank(ranked, set(relevant)),
            "recall": {k: metrics.recall_at_k(ranked, relevant, k) for k in KS},
            "mrr": metrics.reciprocal_rank(ranked, relevant),
            "ndcg@%d" % NDCG_K: metrics.ndcg_at_k(ranked, relevant, NDCG_K),
        }
        per_query.append(row)

    scored = [r for r in per_query if r.get("scorable")]
    agg = {
        "recall": {k: metrics.mean(r["recall"][k] for r in scored) for k in KS},
        "mrr": metrics.mean(r["mrr"] for r in scored),
        "ndcg@%d" % NDCG_K: metrics.mean(r["ndcg@%d" % NDCG_K] for r in scored),
    }
    recall10 = agg["recall"][10]
    return {
        "corpus_fingerprint": current_fp,
        "n_queries_total": len(per_query),
        "n_queries_scored": len(scored),
        "target_recall@10": target,
        "passed": recall10 >= target,
        "aggregate": agg,
        "per_query": per_query,
    }


def _first_rank(ranked, relevant) -> int:
    for i, cid in enumerate(ranked):
        if cid in relevant:
            return i + 1
    return 0  # 0 == not retrieved


def write_report(result: dict) -> None:
    os.makedirs(harness.RESULTS_DIR, exist_ok=True)
    with open(os.path.join(harness.RESULTS_DIR, "results.json"), "w") as fh:
        json.dump(result, fh, indent=2)
        fh.write("\n")

    agg = result["aggregate"]
    ndcg_key = "ndcg@%d" % NDCG_K
    status = "✅ PASS" if result["passed"] else "❌ FAIL"

    lines = []
    lines.append("# UPII Retrieval Eval — REPORT")
    lines.append("")
    lines.append(
        f"**{status}** — Recall@10 = {agg['recall'][10]:.3f} "
        f"(target ≥ {result['target_recall@10']:.2f})"
    )
    lines.append("")
    lines.append(
        f"Scored {result['n_queries_scored']} / {result['n_queries_total']} queries "
        f"against the current retrieval path (semantic + temporal + relational fusion)."
    )
    lines.append("")
    lines.append("## Aggregate metrics")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("| --- | --- |")
    lines.append(f"| Recall@1 | {agg['recall'][1]:.3f} |")
    lines.append(f"| Recall@5 | {agg['recall'][5]:.3f} |")
    lines.append(f"| Recall@10 | {agg['recall'][10]:.3f} |")
    lines.append(f"| MRR | {agg['mrr']:.3f} |")
    lines.append(f"| nDCG@{NDCG_K} | {agg[ndcg_key]:.3f} |")
    lines.append("")
    lines.append("## Per-query")
    lines.append("")
    lines.append("| Query | R@1 | R@5 | R@10 | RR | nDCG@10 | 1st hit |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for r in result["per_query"]:
        if not r.get("scorable"):
            lines.append(f"| {r['query']} | — | — | — | — | — | (no labels) |")
            continue
        rank = r["first_relevant_rank"]
        rank_str = str(rank) if rank else "miss"
        lines.append(
            f"| {r['query']} "
            f"| {r['recall'][1]:.2f} | {r['recall'][5]:.2f} | {r['recall'][10]:.2f} "
            f"| {r['mrr']:.2f} | {r[ndcg_key]:.2f} | {rank_str} |"
        )
    lines.append("")
    lines.append(
        f"_Corpus fingerprint: `{result['corpus_fingerprint'][:16]}…` — "
        f"regenerate labels with `python eval/build_dataset.py build`._"
    )
    lines.append("")

    with open(os.path.join(harness.RESULTS_DIR, "REPORT.md"), "w") as fh:
        fh.write("\n".join(lines))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--rebuild", action="store_true", help="rebuild labels from corpus first")
    p.add_argument("--target", type=float, default=DEFAULT_TARGET_RECALL_AT_10,
                   help="Recall@10 pass threshold (default 0.85)")
    args = p.parse_args(argv)

    if args.rebuild:
        from eval.build_dataset import cmd_build

        cmd_build(argparse.Namespace())

    result = evaluate(args.target)
    write_report(result)

    agg = result["aggregate"]
    ndcg_key = "ndcg@%d" % NDCG_K
    print("\n=== UPII Retrieval Eval ===")
    print(f"  Recall@1 : {agg['recall'][1]:.3f}")
    print(f"  Recall@5 : {agg['recall'][5]:.3f}")
    print(f"  Recall@10: {agg['recall'][10]:.3f}   (target ≥ {args.target:.2f})")
    print(f"  MRR      : {agg['mrr']:.3f}")
    print(f"  nDCG@{NDCG_K} : {agg[ndcg_key]:.3f}")
    print(f"  -> {'PASS' if result['passed'] else 'FAIL'}")
    print(f"  report: {os.path.join(harness.RESULTS_DIR, 'REPORT.md')}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
