# UPII MCP Server — Scope

**Goal:** expose UPII's local memory to MCP clients (Claude Desktop, Claude Code, Cursor, and any MCP-compatible agent) as a set of tools, so users can give their AI assistant a private, cited memory of their own corpus — without any corpus byte leaving the device.

**One-line pitch for launch:** *"Give Claude a local, cited memory of everything you've written."*

## Why this is the highest-leverage feature

- Rides existing assistant adoption instead of competing with it: every MCP-client user is a potential UPII user.
- Converts UPII from a destination CLI into infrastructure other tools build on.
- The privacy story is structural: the MCP server runs on localhost; retrieval happens in-process; only the retrieved, consented chunks are handed to the client.

## Tools (v1)

| Tool | Input | Output | Notes |
|---|---|---|---|
| `upii_search` | `query: str`, `k: int = 8`, `since: date?`, `source: str?` | ranked chunks: text, `chunk_id`, `doc_path`, `score`, signal breakdown (semantic/temporal/relational) | Read-only. The workhorse — most clients will synthesize their own answer from these. |
| `upii_ask` | `question: str` | attributed answer + cited chunk list | Uses the local reasoning path (Ollama/mock). Lets weak clients get a finished answer. |
| `upii_list_sources` | — | enabled sources with doc/chunk counts and last-updated | Transparency: shows the client (and user) exactly what memory is visible. |

Deliberately **not** in v1: ingestion or deletion tools (`upii_ingest`, `upii_forget`). Write access via an agent is a consent minefield; ship read-only first.

## Architecture

- New module `src/upii/mcp/server.py`, entry point `upii mcp serve` (Typer subcommand).
- **Transport: stdio** (v1). Every major MCP client supports spawning a local stdio server; no ports, no auth surface. HTTP/SSE can come later for LAN use.
- **SDK:** official `mcp` Python SDK (FastMCP-style decorators). New optional dependency group: `pip install "upii[mcp]"`.
- Tools call the existing retrieval stack directly (`analysis/search.py`, `analysis/rehydration.py`, `analysis/llm.py`) — in-process, no subprocess, no HTTP hop.
- Read-only DB access; the server never writes to SQLite or LanceDB.

## Consent & scoping (the differentiator — treat as first-class)

1. Server is **off by default**; enabled via `upii mcp enable` or config flag.
2. Respects existing source consent flags: unapproved/disabled sources are invisible to all tools.
3. Per-tool scopes in config (e.g. allow `upii_search` but not `upii_ask`).
4. Optional per-source allowlist for MCP exposure, distinct from local-CLI visibility (a user may want mail searchable locally but never exposed to an agent).
5. Every tool call is logged locally (`upii metrics` integration) — timestamp, tool, query, chunk IDs returned. This is the seed of the future egress audit log.

## Config sketch

```yaml
mcp:
  enabled: false
  tools:
    upii_search: true
    upii_ask: true
    upii_list_sources: true
  expose_sources: all   # or explicit list
  max_chunks_per_call: 12
```

## Client setup (docs deliverable)

One-step instructions for Claude Desktop / Claude Code / Cursor, e.g.:

```json
{ "mcpServers": { "upii": { "command": "upii", "args": ["mcp", "serve"] } } }
```

## Testing

- Integration test driving all three tools end-to-end against a seeded DB via the MCP client SDK (in-memory stdio pair).
- Consent tests: a disabled source's chunks must never appear in any tool result.
- Determinism test: same seeded corpus + query ⇒ identical chunk IDs returned.
- Scope test: disabled tool returns a proper MCP error, not a crash.

## Effort estimate

| Item | Estimate |
|---|---|
| Server skeleton + stdio transport + `upii mcp serve` | 1–2 days |
| Three tools wired to existing retrieval | 1–2 days |
| Consent/scoping + config + call logging | 2 days |
| Tests (integration, consent, determinism) | 1–2 days |
| Docs + client setup guides + demo GIF | 1 day |
| **Total** | **~1.5–2 weeks** part-time |

## Launch checklist

- Demo GIF: Claude Desktop answering from private notes with UPII citations, wifi off.
- Submit to MCP server directories/registries; README badge + section.
- Show HN / r/LocalLLaMA post anchored on the MCP integration.

## Non-goals (v1)

- No write tools, no remote transport, no multi-user auth, no cloud relay.
- Not a general agent framework — UPII stays the memory, the client stays the brain.
