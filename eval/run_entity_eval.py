#!/usr/bin/env python3
"""Evaluate the entity extractor against the committed labelled fixture.

Runs ``EntityExtractor`` over every doc in ``eval/entities/corpus/`` and scores its
output against ``eval/entities/gold.json`` — set-based precision / recall / F1, per
type (PERSON / ORG / PROJECT) and overall (micro-averaged). Writes
``eval/results/entity_REPORT.md`` and ``entity_results.json``.

Precision-first: the gate is **overall precision ≥ 0.80** (the grant target). Recall
and F1 are reported alongside but do not gate — a precision claim should not be
satisfied by extracting nothing, so recall is always shown so the trade-off is
visible.

Usage
-----
    python eval/run_entity_eval.py                 # score committed labels
    python eval/run_entity_eval.py --rebuild        # regenerate the corpus first
    python eval/run_entity_eval.py --target 0.80    # override the precision gate
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eval import metrics  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ENTITIES_DIR = os.path.join(HERE, "entities")
CORPUS_DIR = os.path.join(ENTITIES_DIR, "corpus")
GOLD_PATH = os.path.join(ENTITIES_DIR, "gold.json")
RESULTS_DIR = os.path.join(HERE, "results")
TYPES = ("PERSON", "ORG", "PROJECT")
DEFAULT_TARGET_PRECISION = 0.80


def _norm(name: str) -> str:
    """Normalise an entity surface for comparison: case- and punctuation-folded."""
    n = name.strip().strip("\"'.,;:?!()[]").strip()
    n = re.sub(r"\s+", " ", n)
    return n.lower()


def _corpus_fingerprint() -> str:
    h = hashlib.sha256()
    for fname in sorted(f for f in os.listdir(CORPUS_DIR) if f.endswith(".md")):
        h.update(fname.encode())
        h.update(b"\0")
        with open(os.path.join(CORPUS_DIR, fname), "rb") as fh:
            h.update(fh.read())
        h.update(b"\0")
    return h.hexdigest()


def config_snapshot() -> dict:
    """What the numbers depend on, so a quoted score is reproducible."""
    cfg = {
        "types": list(TYPES),
        "target_precision": DEFAULT_TARGET_PRECISION,
        "matching": "case- and punctuation-folded (name, type) set match",
        "averaging": "micro (per-entity)",
    }
    blob = json.dumps(cfg, sort_keys=True).encode()
    cfg["fingerprint"] = hashlib.sha256(blob).hexdigest()
    return cfg


def _load_gold() -> dict:
    if not os.path.exists(GOLD_PATH):
        raise SystemExit(
            f"No gold at {GOLD_PATH}. Run:  python eval/entities/generate_corpus.py"
        )
    with open(GOLD_PATH) as fh:
        return json.load(fh)


def evaluate(target: float) -> dict:
    gold = _load_gold()

    current_fp = _corpus_fingerprint()
    if gold.get("corpus_fingerprint") != current_fp:
        raise SystemExit(
            "Corpus fingerprint mismatch: gold.json was built against a different\n"
            "corpus. Rebuild with:  python eval/run_entity_eval.py --rebuild"
        )

    from upii.analysis.entity_extractor import EntityExtractor
    extractor = EntityExtractor()

    # Per-type counters, plus a small sample of false positives/negatives for the
    # report so failures are diagnosable without re-running.
    counts = {t: {"tp": 0, "fp": 0, "fn": 0} for t in TYPES}
    fp_samples, fn_samples = [], []

    for fname, gold_ents in gold["docs"].items():
        text = open(os.path.join(CORPUS_DIR, fname), encoding="utf-8").read()

        gold_set = {(_norm(n), t) for n, t in gold_ents}
        pred_set = {(_norm(e.name), e.category.upper()) for e in extractor.extract(text)}

        for t in TYPES:
            g = {n for (n, ty) in gold_set if ty == t}
            p = {n for (n, ty) in pred_set if ty == t}
            counts[t]["tp"] += len(p & g)
            counts[t]["fp"] += len(p - g)
            counts[t]["fn"] += len(g - p)

        # Predictions whose (name,type) isn't in gold at all -> false positives.
        for n, t in sorted(pred_set - gold_set):
            if len(fp_samples) < 15:
                fp_samples.append({"doc": fname, "name": n, "type": t})
        for n, t in sorted(gold_set - pred_set):
            if len(fn_samples) < 15:
                fn_samples.append({"doc": fname, "name": n, "type": t})

    per_type = {t: metrics.micro_prf1([counts[t]]) for t in TYPES}
    overall = metrics.micro_prf1(list(counts.values()))

    return {
        "corpus_fingerprint": current_fp,
        "config": config_snapshot(),
        "n_docs": gold["n_docs"],
        "n_gold_entities": gold["n_gold_entities"],
        "target_precision": target,
        "passed": overall["precision"] >= target,
        "overall": overall,
        "per_type": per_type,
        "fp_samples": fp_samples,
        "fn_samples": fn_samples,
    }


def write_report(result: dict) -> None:
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, "entity_results.json"), "w") as fh:
        json.dump(result, fh, indent=2)
        fh.write("\n")

    ov = result["overall"]
    status = "✅ PASS" if result["passed"] else "❌ FAIL"
    L = []
    L.append("# UPII Entity-Extraction Eval — REPORT")
    L.append("")
    L.append(f"**{status}** — overall precision = {ov['precision']:.3f} "
             f"(target ≥ {result['target_precision']:.2f})")
    L.append("")
    L.append(f"Scored **{result['n_gold_entities']}** gold entities across "
             f"**{result['n_docs']}** documents. Precision-first: only precision gates; "
             f"recall and F1 are reported so the trade-off is visible.")
    L.append("")
    L.append("## Overall (micro-averaged)")
    L.append("")
    L.append("| Metric | Value |")
    L.append("| --- | --- |")
    L.append(f"| Precision | **{ov['precision']:.3f}** |")
    L.append(f"| Recall | {ov['recall']:.3f} |")
    L.append(f"| F1 | {ov['f1']:.3f} |")
    L.append(f"| TP / FP / FN | {ov['tp']} / {ov['fp']} / {ov['fn']} |")
    L.append("")
    L.append("## Per entity type")
    L.append("")
    L.append("| Type | Precision | Recall | F1 | TP | FP | FN |")
    L.append("| --- | --- | --- | --- | --- | --- | --- |")
    for t in TYPES:
        m = result["per_type"][t]
        L.append(f"| {t} | {m['precision']:.3f} | {m['recall']:.3f} | {m['f1']:.3f} "
                 f"| {m['tp']} | {m['fp']} | {m['fn']} |")
    L.append("")
    if result["fp_samples"]:
        L.append("## Sample false positives (extracted, not in gold)")
        L.append("")
        for s in result["fp_samples"]:
            L.append(f"- `{s['name']}` as **{s['type']}** ({s['doc']})")
        L.append("")
    if result["fn_samples"]:
        L.append("## Sample false negatives (gold, missed)")
        L.append("")
        for s in result["fn_samples"]:
            L.append(f"- `{s['name']}` as **{s['type']}** ({s['doc']})")
        L.append("")
    cfg = result["config"]
    L.append("## Configuration")
    L.append("")
    L.append(f"- Types: {', '.join(cfg['types'])}")
    L.append(f"- Matching: {cfg['matching']}")
    L.append(f"- Averaging: {cfg['averaging']}")
    L.append(f"- Config fingerprint: `{cfg['fingerprint'][:16]}…`")
    L.append(f"- Corpus fingerprint: `{result['corpus_fingerprint'][:16]}…`")
    L.append("")
    L.append("_Regenerate: `python eval/run_entity_eval.py --rebuild`._")
    L.append("")
    with open(os.path.join(RESULTS_DIR, "entity_REPORT.md"), "w") as fh:
        fh.write("\n".join(L))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--rebuild", action="store_true", help="regenerate the corpus + gold first")
    p.add_argument("--target", type=float, default=DEFAULT_TARGET_PRECISION,
                   help="overall-precision pass threshold (default 0.80)")
    args = p.parse_args(argv)

    if args.rebuild:
        import subprocess
        subprocess.check_call([sys.executable,
                               os.path.join(ENTITIES_DIR, "generate_corpus.py")])

    result = evaluate(args.target)
    write_report(result)

    ov = result["overall"]
    print("\n=== UPII Entity Eval ===")
    for t in TYPES:
        m = result["per_type"][t]
        print(f"  {t:<8} P {m['precision']:.3f}  R {m['recall']:.3f}  F1 {m['f1']:.3f}")
    print(f"  {'OVERALL':<8} P {ov['precision']:.3f}  R {ov['recall']:.3f}  F1 {ov['f1']:.3f}"
          f"   (precision target ≥ {args.target:.2f})")
    print(f"  -> {'PASS' if result['passed'] else 'FAIL'}")
    print(f"  report: {os.path.join(RESULTS_DIR, 'entity_REPORT.md')}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
