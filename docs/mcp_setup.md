# UPII MCP Server — Setup

Give your AI assistant a **local, cited memory** of everything you've written —
without any corpus byte leaving your machine.

UPII ships an [MCP](https://modelcontextprotocol.io) server that exposes your
local memory to any MCP-compatible client (Claude Desktop, Claude Code, Cursor, …)
as three **read-only** tools:

| Tool | What it does |
|---|---|
| `upii_search` | Ranked chunks for a query — text, `chunk_id`, `doc_path`, `source`, fused score, and a semantic/temporal/relational breakdown. |
| `upii_ask` | A finished, attributed answer with its cited chunks, via the on-device reasoning path (Ollama, or a deterministic mock if Ollama isn't running). |
| `upii_list_sources` | The sources currently visible to the client, with document/chunk counts and last-updated times. |

It runs on **stdio** (no ports, no network), in-process against your existing
UPII index. It is **off by default** and consent-gated.

## 1. Install

The server needs the optional `mcp` dependency group:

```bash
pip install "upii[mcp]"
```

## 2. Enable it (off by default)

```bash
upii mcp enable      # flips `enabled: true` in mcp.yaml (next to your DB)
upii mcp status      # show enabled state, per-tool scopes, and exposure
```

Turn it back off any time with `upii mcp disable`.

Verify it starts (Ctrl-C to stop — it blocks, speaking MCP over stdio):

```bash
upii mcp serve
```

## 3. Point your client at it

All three clients spawn the same local command. Use the **same working directory
as your UPII index** (where `upii.db` lives) so the server finds your memory —
either `cd` there before launching the client, or make the command an absolute
path with a `cwd`.

### Claude Desktop

Edit `claude_desktop_config.json`
(macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`,
Windows: `%APPDATA%\Claude\claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "upii": {
      "command": "upii",
      "args": ["mcp", "serve"],
      "cwd": "/absolute/path/to/your/upii/workspace"
    }
  }
}
```

Restart Claude Desktop. The `upii_*` tools appear in the tool menu.

### Claude Code

```bash
claude mcp add upii -- upii mcp serve
```

Or add the same `mcpServers` block to `.mcp.json` / your Claude Code settings.

### Cursor

Add to `~/.cursor/mcp.json` (or the project's `.cursor/mcp.json`):

```json
{
  "mcpServers": {
    "upii": {
      "command": "upii",
      "args": ["mcp", "serve"],
      "cwd": "/absolute/path/to/your/upii/workspace"
    }
  }
}
```

## 4. Consent & scoping

Config lives in `mcp.yaml` next to your database. Everything is off/closed by
default:

```yaml
enabled: false             # `upii mcp enable` sets this to true
tools:
  upii_search: true        # per-tool scopes — allow only what you want exposed
  upii_ask: true
  upii_list_sources: true
expose_sources: all        # or an explicit list, e.g. [markdown, pdf]
max_chunks_per_call: 12     # hard ceiling on chunks any single call can return
```

- **Off by default.** No client can reach your memory until you `upii mcp enable`.
- **Per-tool scopes.** Set a tool to `false` and it isn't advertised; calling it
  returns a clean MCP error, never data.
- **Source allowlist.** `expose_sources` is distinct from local-CLI visibility —
  you can keep, say, `email` searchable in the CLI but never exposed to an agent
  by listing only the sources you want, e.g. `expose_sources: [markdown, pdf]`.
- **Ambient consent respected.** A source disabled in `upii sources` is invisible
  to MCP too.
- **Local egress audit.** Every tool call is logged on-device (timestamp, tool,
  query, returned chunk ids). Review it with `upii metrics show`.

> You can also put an `mcp:` block in `.upii_config.yaml`; UPII tolerates it, but
> `upii mcp enable/disable` persist to the dedicated `mcp.yaml`, which is the
> authoritative source of truth.

## 5. Try it

With the server enabled and your client configured, ask your assistant something
only your notes would know — e.g. *"Using UPII, what did I decide about Project
Alpha?"* The client calls `upii_search` / `upii_ask`, and the answer comes back
with citations to your own files. Turn your wifi off first to prove it's local.
