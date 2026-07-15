#!/usr/bin/env bash
#
# repro_demo.sh — a clean, narratable terminal demo of DETERMINISTIC ingestion.
# Demonstrates re-ingestion to an identical state.
#
# It wipes a throwaway demo store, ingests a small sample corpus, prints the chunk
# count and a few chunk hashes, then RE-ingests the identical corpus and shows the
# count and hashes are unchanged (every file a no-op).
#
# ── How to record ────────────────────────────────────────────────────────────────
#   1. source venv/bin/activate
#   2. Make your terminal ~100 cols, clear it.
#   3. asciinema rec upii_repro.cast  -c "bash scripts/demo/repro_demo.sh"
#      (or just run it and screen-record the window).
#   4. The closing "IDENTICAL ✓" line is the money shot.
#
# Safe: everything happens under .repro_demo/ and is deleted on start. It never
# touches your real upii.db / upii_vectors.
# ─────────────────────────────────────────────────────────────────────────────────

set -euo pipefail

cd "$(dirname "$0")/../.."          # repo root
ROOT="$(pwd)"
DEMO="$ROOT/.repro_demo"
CORPUS="$DEMO/corpus"
export UPII_DB="$DEMO/upii.db"

# Run the CLI with config pointed at the demo store, regardless of cwd config.
upii() { python -c "
import sys
from upii.core.config import config
config.db_path = '$DEMO/upii.db'
config.vector_store_path = '$DEMO/vectors'
from upii.cli import app
app()
" "$@"; }

hr() { printf '─%.0s' {1..70}; echo; }
sql() { sqlite3 "$DEMO/upii.db" "$1"; }

echo
echo "UPII — deterministic re-ingestion demo (T1.2)"
hr

# 0. Clean slate.
rm -rf "$DEMO"
mkdir -p "$CORPUS"

# 1. A tiny sample corpus (distinct content per file).
cat > "$CORPUS/strategy.md" <<'EOF'
# Strategy
We are pivoting to a stream-first architecture. Latency goal under 15 minutes.
Primary partner is ICEYE for the Firewatch programme. Burn rate stays low.
EOF
cat > "$CORPUS/meeting.md" <<'EOF'
# Meeting notes
Action: calibrate the NASA PACE blue band by Nov 15.
Decision: enterprise licensing at fifty thousand per seat for regulated sectors.
EOF
echo "Sample corpus:"
ls -1 "$CORPUS" | sed 's/^/  • /'
hr

# 2. First ingest.
echo "▶ FIRST ingest"
upii ingest "$CORPUS" --recursive | sed 's/^/    /'
COUNT1=$(sql "SELECT COUNT(*) FROM chunks;")
echo
echo "  chunks in store: $COUNT1"
echo "  sample chunk hashes:"
sql "SELECT '    ' || substr(chunk_id,1,24) || '…' FROM chunks ORDER BY chunk_id LIMIT 4;"
HASHES1=$(sql "SELECT chunk_id FROM chunks ORDER BY chunk_id;")
hr

# 3. Re-ingest the IDENTICAL corpus — expect all no-ops.
echo "▶ SECOND ingest (identical corpus)"
upii ingest "$CORPUS" --recursive | sed 's/^/    /'
COUNT2=$(sql "SELECT COUNT(*) FROM chunks;")
echo
echo "  chunks in store: $COUNT2"
HASHES2=$(sql "SELECT chunk_id FROM chunks ORDER BY chunk_id;")
hr

# 4. Verdict.
if [ "$COUNT1" = "$COUNT2" ] && [ "$HASHES1" = "$HASHES2" ]; then
  echo "  Chunk count unchanged ($COUNT1 = $COUNT2) and every chunk hash IDENTICAL ✓"
  echo "  Re-ingestion converged to an identical state — deterministic. ✅"
  STATUS=0
else
  echo "  MISMATCH — re-ingestion was not identical ❌"
  STATUS=1
fi
hr
rm -rf "$DEMO"
exit $STATUS
