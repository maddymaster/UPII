#!/usr/bin/env bash
#
# phaseM_demo.sh — the MCP milestone in one command: UPII as a local MCP server.
#
# UPII now exposes your on-device memory to any MCP client (Claude Desktop, Claude
# Code, Cursor) as three read-only tools, over stdio, in-process against the real
# retrieval stack. No corpus byte leaves the machine. This demo proves the bridge
# is live end-to-end:
#
#   STEP 1  ingest a small real corpus            ->  a local index to answer from
#   STEP 2  enable the MCP server (off by default)->  consent gate opened
#   STEP 3  a scripted MCP CLIENT (official SDK)  ->  spawns `upii mcp serve` over
#           stdio, lists the tools, calls upii_search + upii_ask, prints the
#           CITED CHUNKS the client received — the assistant's private memory.
#   STEP 4  the local egress audit log            ->  every tool call, on-device
#
# Every command is echoed before it runs, so a screen recording documents exactly
# what produced the cited answer.
#
# ── Requirements ─────────────────────────────────────────────────────────────────
#   Python >= 3.10 with the MCP extra installed:   pip install "upii[mcp]"
#   (the official `mcp` SDK needs 3.10+; the repo's 3.9 venv cannot run this.)
#
# ── How to record ────────────────────────────────────────────────────────────────
#   asciinema rec upii_phaseM.cast -c "bash scripts/demo/phaseM_demo.sh"
#
# Safe: everything runs under .phaseM_demo/ (a throwaway store) and is removed on
# start. It never touches your real upii.db.
# ─────────────────────────────────────────────────────────────────────────────────

set -euo pipefail

cd "$(dirname "$0")/../.."          # repo root
ROOT="$(pwd)"
export DEMO="$ROOT/.phaseM_demo"
CORPUS="$ROOT/eval/dataset/corpus"

# Use the cached embedding model; never hang on a flaky network during a demo.
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

# The scripted client will ask this — answerable from the corpus, with a citation.
export QUERY="Where does UPII store its vectors and document metadata?"

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

echo
echo "UPII — MCP phase: a local, cited memory for any MCP client"
hr
echo "  Claim:  UPII is an MCP server — read-only, on localhost, consent-gated."
echo "  Proof:  a real MCP client spawns 'upii mcp serve' and gets CITED chunks"
echo "          from your private corpus, with no byte leaving the device."
hr

# 0. Clean slate + a config file the spawned server subprocess will read.
rm -rf "$DEMO"; mkdir -p "$DEMO"
cat > "$DEMO/.upii_config.yaml" <<EOF
db_path: $DEMO/upii.db
vector_store_path: $DEMO/vectors
EOF

# Guard: this demo needs the optional MCP SDK on a 3.10+ interpreter.
if ! python -c "import mcp" >/dev/null 2>&1; then
  echo "  ✗ The 'mcp' SDK is not importable on this Python."
  echo "    Install the extra on a Python >= 3.10:  pip install \"upii[mcp]\""
  exit 1
fi

# 1. Ingest a small real corpus into the throwaway store.
echo "▶ STEP 1 — ingest a small real corpus (builds the local index)"
echo
run upii ingest "$CORPUS" --recursive 2>&1 | tail -2 || true
hr

# 2. Enable the server — it is OFF by default (consent-gated).
echo "▶ STEP 2 — enable the MCP server (off by default; writes mcp.yaml)"
echo
run upii mcp enable
hr

# 3. The scripted MCP client: spawn `upii mcp serve` over stdio and call the tools.
echo "▶ STEP 3 — a real MCP client drives the server over stdio"
echo
python - <<'PY'
import asyncio, json, os, sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

DEMO = os.environ["DEMO"]
QUERY = os.environ["QUERY"]

def as_list(result):
    return [json.loads(c.text) for c in result.content]

def as_obj(result):
    return json.loads(result.content[0].text)

async def main():
    # Spawn the *real* installed server exactly as an MCP client would, pointed at
    # the demo store (cwd -> reads $DEMO/.upii_config.yaml and $DEMO/mcp.yaml).
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "upii.cli", "mcp", "serve"],
        cwd=DEMO,
        env={**os.environ},   # inherit HF offline flags + PYTHONPATH
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            info = await session.initialize()
            print(f"    ✓ connected: {info.serverInfo.name} v{info.serverInfo.version}")

            tools = await session.list_tools()
            print(f"    ✓ tools advertised: {', '.join(sorted(t.name for t in tools.tools))}")
            print()

            print(f'    upii_search("{QUERY}")')
            res = await session.call_tool("upii_search", {"query": QUERY, "k": 3})
            rows = as_list(res)
            print(f"    ← {len(rows)} cited chunk(s):")
            for i, r in enumerate(rows, 1):
                snippet = " ".join((r["text"] or "").split())[:90]
                sig = r["signals"]
                print(f"      [{i}] {r['doc_path']}  (score {r['score']:.3f}, "
                      f"sem {sig['semantic']:.2f}/tmp {sig['temporal']:.2f}/rel {sig['relational']:.2f})")
                print(f"          {snippet}…")
            print()

            print(f'    upii_ask("{QUERY}")')
            ans = await session.call_tool("upii_ask", {"question": QUERY})
            obj = as_obj(ans)
            answer = " ".join((obj["answer"] or "").split())
            print(f"    ← answer: {answer[:280]}")
            cites = ", ".join(c["doc_path"] for c in obj["citations"])
            print(f"    ← citations: {cites}")

asyncio.run(main())
PY
hr

# 4. The local egress audit log — every MCP tool call, recorded on-device.
echo "▶ STEP 4 — local egress audit log (every tool call, on your machine)"
echo
run python -c "
import sqlite3, json
c = sqlite3.connect('$DEMO/upii.db')
c.row_factory = sqlite3.Row
rows = c.execute('SELECT ts, tool, query, result_count, chunk_ids FROM mcp_call_log ORDER BY id').fetchall()
for r in rows:
    ids = ', '.join(json.loads(r['chunk_ids'] or '[]')[:3])
    q = (r['query'] or '')[:44]
    print(f\"    {r['ts']}  {r['tool']:<18} n={r['result_count']}  q='{q}'  chunks=[{ids}]\")
"
hr

echo "  ── What the MCP phase proves ──"
echo "     • UPII is a working MCP server: a standard client connects over stdio,"
echo "       lists the tools, and receives CITED chunks from a private corpus."
echo "     • Read-only + consent-gated: off by default, per-tool scopes, source"
echo "       allowlist, and every call written to a local egress audit log."
echo "     • 100% on-device — in-process retrieval, no ports, no byte egress."
hr

# Clean up (leave the demo store out of the tree).
upii mcp disable >/dev/null 2>&1 || true
rm -rf "$DEMO"
