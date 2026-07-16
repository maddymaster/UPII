#!/usr/bin/env bash
#
# phase1_demo.sh — the Phase 1 benchmark, end to end, in one command.
#
# Builds a deterministic ~100k-chunk corpus (fixed seed), ingests it through the
# REAL pipeline with the REAL embedder, replays queries through the live retrieval
# path, and prints the two headline numbers:
#
#     ingestion throughput   (target >= 500 docs/min)
#     retrieval latency p50  (target <  300 ms)
#
# Every command is echoed before it runs, so a screen recording doubles as
# documentation of exactly what produced the numbers.
#
# ── How to record ────────────────────────────────────────────────────────────────
#   1. source venv/bin/activate
#   2. Make your terminal ~100 cols, clear it.
#   3. asciinema rec upii_phase1.cast -c "bash scripts/demo/phase1_demo.sh"
#      (or just run it and screen-record the window).
#   4. The closing headline table is the money shot.
#
# ── Knobs ────────────────────────────────────────────────────────────────────────
#   DOCS=7700   documents to generate (13 chunks/doc => ~100k chunks)
#   PARAS=60    paragraphs per doc
#   NOTE="..."  free-text note recorded in the report (e.g. which machine this is)
#   MAX_SECONDS=1500  wall-clock budget for ingestion. On hitting it the run stops
#                     early and still writes an honest, clearly-marked truncated
#                     report — better than being killed and producing nothing.
#
#   A full run takes roughly 15-30 minutes. For a quick smoke of the harness:
#       DOCS=100 bash scripts/demo/phase1_demo.sh
#
# Safe: the corpus and store live under .phase1_demo/ and are removed on start.
# It never touches your real upii.db / upii_vectors.
# ─────────────────────────────────────────────────────────────────────────────────

set -euo pipefail

cd "$(dirname "$0")/../.."          # repo root
ROOT="$(pwd)"
DEMO="$ROOT/.phase1_demo"
CORPUS="$DEMO/corpus"

DOCS="${DOCS:-7700}"
PARAS="${PARAS:-60}"
NOTE="${NOTE:-}"
MAX_SECONDS="${MAX_SECONDS:-0}"

hr() { printf '─%.0s' {1..70}; echo; }

# Echo a command, then run it — the demo documents itself.
run() { echo "\$ $*"; echo; "$@"; }

echo
echo "UPII — Phase 1 benchmark: ingestion throughput & retrieval latency"
hr
echo "  Targets:  ingestion >= 500 docs/min   |   retrieval p50 < 300 ms"
echo "  Corpus:   ${DOCS} docs x ${PARAS} paras  (~13 chunks/doc, deterministic seed)"
echo "  Note:     a full run takes ~15-30 min; DOCS=100 for a quick smoke."
hr

# 0. Clean slate.
rm -rf "$DEMO"
mkdir -p "$DEMO"

# 1. Generate the corpus — a pure function of the seed, so the same corpus is
#    rebuilt identically on any machine and the numbers stay comparable.
echo "▶ STEP 1 — generate the deterministic corpus"
echo
run python scripts/bench/make_corpus.py --docs "$DOCS" --paras "$PARAS" --out "$CORPUS"
hr

# 2. Benchmark: real pipeline, real embedder, live retrieval path.
echo "▶ STEP 2 — ingest + measure (real embedder, no mocks)"
echo
ARGS=(--corpus "$CORPUS" --paras "$PARAS" --max-seconds "$MAX_SECONDS")
[ -n "$NOTE" ] && ARGS+=(--note "$NOTE")
run python scripts/bench/benchmark.py "${ARGS[@]}"
hr

echo "  Full report: bench/results/REPORT.md"
echo "  Re-run anywhere with: bash scripts/demo/phase1_demo.sh"
hr

rm -rf "$DEMO"
