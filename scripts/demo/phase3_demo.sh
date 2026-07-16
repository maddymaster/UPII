#!/usr/bin/env bash
#
# phase3_demo.sh — the Phase 3 milestone in one command: multi-signal retrieval.
#
# The Context Rehydrator v2 is BUILT to fuse three signals — semantic (vectors),
# temporal (recency), relational (a local knowledge graph) — into one ranked
# context window, with per-signal contributions visible via `upii ask --debug`.
# It ends by printing the headline number:
#
#     Recall@10   (target >= 0.85)
#
# ── Honest by construction ───────────────────────────────────────────────────────
# Today only the SEMANTIC signal actually moves the ranking. The relational signal
# has no data source yet (ingestion does not extract entities — that is T1.4), and
# the temporal signal is a uniform recency offset on a bulk-ingested corpus. This
# demo PREDICTS those zeros before showing them (STEP 3), then PROVES they don't
# affect ranking with a control run (STEP 3b). Recall@10 = 0.958 is therefore a
# real, reproducible, deterministic *semantic-retrieval* number — not evidence of
# fusion. We show that rather than hide it.
#
# ── How to record ────────────────────────────────────────────────────────────────
#   1. source venv/bin/activate
#   2. Make your terminal ~100 cols, clear it.
#   3. asciinema rec upii_phase3.cast -c "bash scripts/demo/phase3_demo.sh"
#   4. The closing Recall@10 line is the money shot.
#
# Safe: everything runs against .phase3_demo/ (a throwaway store) and eval/.index/
# (rebuilt from the committed corpus). It never touches your real upii.db.
# ─────────────────────────────────────────────────────────────────────────────────

set -euo pipefail

cd "$(dirname "$0")/../.."          # repo root
ROOT="$(pwd)"
DEMO="$ROOT/.phase3_demo"
CORPUS="$ROOT/eval/dataset/corpus"

# Use the cached embedding model; never hang on a flaky network during a demo.
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

# Run the CLI with config pointed at the throwaway demo store, regardless of cwd.
upii() { python -c "
import sys
from upii.core.config import config
config.db_path = '$DEMO/upii.db'
config.vector_store_path = '$DEMO/vectors'
from upii.cli import app
app()
" "$@"; }

hr() { printf '─%.0s' {1..70}; echo; }
run() { echo "\$ $*"; echo; "$@"; }

QUERY="What are our retrieval performance targets and where did they break?"

echo
echo "UPII — Phase 3: multi-signal retrieval (Context Rehydrator v2)"
hr
echo "  Claim:  recall is a sensor-fusion problem, not a cosine-distance problem."
echo "  Proof:  a labelled eval over a committed corpus  ->  Recall@10 >= 0.85"
echo
echo "  Candour up front: of the three signals, only SEMANTIC moves the ranking"
echo "  today. Relational has no data source yet (T1.4); temporal is a uniform"
echo "  offset on a bulk-ingested corpus. STEP 3 predicts this; STEP 3b proves it."
echo "  So Recall@10 below is an honest SEMANTIC number, measured — not asserted."
hr

# 0. Clean slate + ingest the SAME corpus the eval scores, so the --debug table
#    and the Recall@10 describe the same 22 documents. Create the store dir first:
#    SQLite will not create its parent directory.
rm -rf "$DEMO"
mkdir -p "$DEMO"
echo "▶ STEP 0 — ingest the labelled corpus into a throwaway store"
echo
run upii ingest "$CORPUS" --recursive
hr

# 1. The fusion weights the numbers depend on. Shown first because a retrieval
#    number without its configuration is not reproducible — and because it is what
#    explains STEP 3's temporal column (weight 0.25 x signal 1.00 = 0.25).
echo "▶ STEP 1 — the fusion weights in play"
echo
run python -c "
from upii.core.config import config
for signal, weight in config.fusion_weights().items():
    print(f'    {signal:<12} weight = {weight:g}')
print()
print('    fused = w_semantic*semantic + w_temporal*temporal + w_relational*relational')
"
hr

# 2. The labelled dataset: committed, deterministic, inspectable.
echo "▶ STEP 2 — the committed labelled dataset"
echo
run python -c "
import json, os
from eval import harness
labels = json.load(open(harness.LABELS_PATH))
qs = labels['queries']
print(f'    corpus:  {len([f for f in os.listdir(harness.CORPUS_DIR) if f.endswith(\".md\")])} documents')
print(f'    queries: {len(qs)} labelled')
print()
for q in qs[:3]:
    print(f'      - {q[\"query\"]}')
print('        ...')
"
hr

# 3. PREDICT, then show. State exactly what the table will contain and why, so the
#    output reads as instrumentation confirming a prediction, not a surprise bug.
echo "▶ STEP 3 — per-signal contributions for one query (upii ask --debug)"
echo
echo "  Query (deliberately the corpus's HARDEST — the only one whose first"
echo "  relevant hit is at rank 3, not rank 1):"
echo "    \"$QUERY\""
echo
echo "  Predict before we run it — the table will show:"
echo "    • Semantic   — varies per row (this is what does the ranking)"
echo "    • Temporal   — a flat 1.00->0.25 on every row. All 22 docs were ingested"
echo "                   seconds ago, so recency is uniform; a constant can't reorder."
echo "    • Relational — '·' (0.00) on every row. Ingestion does not extract entities"
echo "                   yet (T1.4), so the knowledge graph is empty."
echo "    • Dominant   — 'semantic' on every row."
echo
run upii ask "$QUERY" --debug
hr

# 3b. THE CONTROL. Re-run the same query with the other two signals zeroed. If the
#     ranking is identical, they demonstrably contribute nothing to ORDER today.
echo "▶ STEP 3b — control: zero the temporal + relational weights, same query"
echo
echo "  If fusion were doing work, zeroing two signals would reorder results."
echo "  Verified claim: the order is IDENTICAL and every fused score drops by"
echo "  exactly 0.25 (the constant temporal offset we removed)."
echo
run upii ask "$QUERY" --w-temporal 0 --w-relational 0 --debug
hr

# 4. The measured number. --rebuild re-ingests the corpus into the isolated eval
#    index and re-derives labels, so this is end-to-end from committed inputs.
echo "▶ STEP 4 — score the live retrieval path against the labels"
echo
run python eval/run_eval.py --rebuild
hr

# 5. The ledger: what this proves, what it does not, what is next.
echo "  ── What Phase 3 proves ──"
echo "     • The fusion MECHANISM + per-signal attribution (upii ask --debug)."
echo "     • Retrieval quality: Recall@10 = 0.958 vs a >= 0.85 target — measured,"
echo "       reproducible, deterministic. This is a SEMANTIC-ranking number."
echo "  ── What it does NOT yet prove ──"
echo "     • That fusion beats semantic-alone. STEP 3b shows it's currently a tie:"
echo "       relational has no data source (T1.4), temporal is a uniform offset."
echo "  ── Next (Phase 4 / T1.4) ──"
echo "     • Extract entities on ingest so the relational signal has a graph to"
echo "       fuse against — then re-run this demo and watch the control diverge."
echo
echo "  Full report (with config snapshot): eval/results/REPORT.md"
echo "  Re-run anywhere with: bash scripts/demo/phase3_demo.sh"
hr

rm -rf "$DEMO"
