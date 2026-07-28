#!/usr/bin/env bash
#
# phase3_demo.sh — the Phase 3 milestone in one command: multi-signal retrieval.
#
# Shows that UPII ranks on more than cosine similarity. The Context Rehydrator v2
# fuses three signals — semantic (vectors), temporal (recency), relational (the
# local knowledge graph) — and the fused ranking is MEASURED against a committed,
# labelled dataset rather than asserted.
#
# It ends by printing the headline number:
#
#     Recall@10   (target >= 0.85)
#
# Every command is echoed before it runs, so a screen recording doubles as
# documentation of exactly what produced the number.
#
# ── How to record ────────────────────────────────────────────────────────────────
#   1. source venv/bin/activate
#   2. Make your terminal ~100 cols, clear it.
#   3. asciinema rec upii_phase3.cast -c "bash scripts/demo/phase3_demo.sh"
#   4. The closing Recall@10 line is the money shot.
#
# Safe: retrieval runs against eval/.index/ (gitignored, rebuilt from the committed
# corpus). It never touches your real upii.db / upii_vectors.
# ─────────────────────────────────────────────────────────────────────────────────

set -euo pipefail

cd "$(dirname "$0")/../.."          # repo root

hr() { printf '─%.0s' {1..70}; echo; }
run() { echo "\$ $*"; echo; "$@"; }

echo
echo "UPII — Phase 3: multi-signal retrieval (Context Rehydrator v2)"
hr
echo "  Claim:  recall is a sensor-fusion problem, not a cosine-distance problem."
echo "  Proof:  a labelled eval over a committed corpus  ->  Recall@10 >= 0.85"
hr

# 1. The fusion weights the numbers depend on. Shown first, because a retrieval
#    number without its configuration is not reproducible.
echo "▶ STEP 1 — the fusion weights in play"
echo
run python -c "
from upii.core.config import config
w = config.fusion_weights()
for signal, weight in w.items():
    print(f'    {signal:<12} weight = {weight:g}')
print()
print('    fused = w_semantic*semantic + w_temporal*temporal + w_relational*relational')
"
hr

# 2. The labelled dataset: committed, deterministic, inspectable.
echo "▶ STEP 2 — the committed labelled dataset"
echo
run python -c "
import json
from eval import harness
labels = json.load(open(harness.LABELS_PATH))
qs = labels['queries']
print(f'    corpus:  {len(__import__(\"os\").listdir(harness.CORPUS_DIR))} documents')
print(f'    queries: {len(qs)} labelled')
print()
for q in qs[:3]:
    print(f'      • {q[\"query\"]}')
print('        ...')
"
hr

# 3. Why a chunk ranked where it did — the per-signal breakdown. This is the
#    Rehydrator v2 claim made visible: a chunk can win on relational or temporal
#    evidence, not only on vector distance.
echo "▶ STEP 3 — per-signal contributions for one query (upii ask --debug shows this too)"
echo
run python -c "
from eval import harness
harness.use_isolated_index()
harness.ingest_corpus(reset=False)

from upii.analysis.search import SearchEngine
from upii.analysis.rehydration import SIGNALS

q = 'What are our retrieval performance targets and where did they break?'
print(f'    query: {q}')
print()
print('    ' + f'{\"#\":<3}{\"fused\":>8}  ' + '  '.join(f'{s:>11}' for s in SIGNALS) + '   dominant')
for i, r in enumerate(SearchEngine().search(q, limit=5), 1):
    cells = '  '.join(f'{r.signals.get(s, 0.0):>5.2f}->{r.contributions.get(s, 0.0):<5.2f}' for s in SIGNALS)
    print(f'    {i:<3}{r.score:>8.3f}  {cells}   {r.source_signal}')
print()
print('    (raw signal -> weighted contribution to the fused score)')
"
hr

# 4. The measured number. --rebuild re-ingests the corpus into the isolated index
#    and re-derives the labels, so this is end-to-end from committed inputs.
echo "▶ STEP 4 — score the live retrieval path against the labels"
echo
run python eval/run_eval.py --rebuild
hr

echo "  Full report (with the config snapshot): eval/results/REPORT.md"
echo "  Re-run anywhere with: bash scripts/demo/phase3_demo.sh"
hr
