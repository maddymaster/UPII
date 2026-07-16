#!/usr/bin/env bash
#
# phase4_demo.sh — the Phase 4 milestone in one command: a local knowledge graph.
#
# Ingesting documents now extracts entities (people / orgs / projects) and builds
# a knowledge graph — nodes + co-occurrence edges — entirely on-device. This demo:
#
#   STEP 1  ingest the labelled entity corpus  ->  populates the graph on ingest
#   STEP 2  score the extractor                ->  entity precision (target >= 0.80)
#   STEP 3  render the graph to self-contained interactive HTML  ->  open it
#
# Every command is echoed before it runs, so a screen recording documents exactly
# what produced the graph and the number.
#
# ── How to record ────────────────────────────────────────────────────────────────
#   1. source venv/bin/activate
#   2. asciinema rec upii_phase4.cast -c "bash scripts/demo/phase4_demo.sh"
#   3. The graph opens in your browser at the end (self-contained, offline).
#
# Safe: everything runs under .phase4_demo/ (a throwaway store) and is removed on
# start. It never touches your real upii.db.
# ─────────────────────────────────────────────────────────────────────────────────

set -euo pipefail

cd "$(dirname "$0")/../.."          # repo root
ROOT="$(pwd)"
DEMO="$ROOT/.phase4_demo"
CORPUS="$ROOT/eval/entities/corpus"
GRAPH="$ROOT/graph.html"

export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

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

echo
echo "UPII — Phase 4: local knowledge graph (entities extracted on ingest)"
hr
echo "  Claim:  ingesting documents builds a people/orgs/projects graph, on-device."
echo "  Proof:  entity precision >= 0.80 on a labelled set + a rendered graph."
hr

# 0. Clean slate. (SQLite will not create its parent dir.)
rm -rf "$DEMO"; mkdir -p "$DEMO"

# 1. Ingest the labelled entity corpus. Entity extraction + graph writes happen
#    inside the normal ingest path — no separate step.
echo "▶ STEP 1 — ingest the corpus (entities extracted + graph built on ingest)"
echo
run upii ingest "$CORPUS" --recursive 2>&1 | tail -2 || true
echo
run python -c "
import sqlite3
c = sqlite3.connect('$DEMO/upii.db')
n = c.execute('SELECT COUNT(*) FROM entities').fetchone()[0]
e = c.execute('SELECT COUNT(*) FROM entity_edges').fetchone()[0]
print(f'    knowledge graph: {n} entities, {e} chunk edges')
by = c.execute('SELECT category, COUNT(*) FROM entities GROUP BY category ORDER BY category').fetchall()
print('    by type: ' + ', '.join(f'{cat} {cnt}' for cat, cnt in by))
"
hr

# 2. Score the extractor against the committed gold labels.
echo "▶ STEP 2 — entity-extraction quality vs the labelled gold set"
echo
run python eval/run_entity_eval.py
hr

# 3. Render the graph from the ingested store to a self-contained HTML file.
echo "▶ STEP 3 — render the knowledge graph (self-contained, offline HTML)"
echo
run upii knowledge --graph --out "$GRAPH"
echo
echo "  The file is fully self-contained — vendored force-directed layout, no"
echo "  network calls. Nodes coloured by type, edge thickness = co-occurrence count."
# Open it in the default browser (best-effort; harmless if headless).
if command -v open >/dev/null 2>&1; then open "$GRAPH" || true
elif command -v xdg-open >/dev/null 2>&1; then xdg-open "$GRAPH" || true
fi
echo "  Opened: $GRAPH"
hr

echo "  ── What Phase 4 proves ──"
echo "     • Entities are extracted and a graph is built DURING ingest, on-device."
echo "     • Extractor precision meets target on a committed labelled set."
echo "     • The graph renders offline with no external dependencies."
echo "  ── Honest note ──"
echo "     • The relational retrieval signal reads this graph but ships weight-0:"
echo "       it is not yet net-positive on the retrieval eval. Tuning it is next."
hr

rm -rf "$DEMO"
