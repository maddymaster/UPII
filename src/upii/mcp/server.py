"""FastMCP server exposing UPII's local memory over stdio.

Three read-only tools — ``upii_search``, ``upii_ask``, ``upii_list_sources`` —
wired in-process to the existing retrieval stack via :class:`~upii.mcp.service.MCPService`.
No ports, no auth surface, no corpus byte leaves the machine.

Only tools enabled in the config are registered, and the server refuses to start
unless ``mcp.enabled`` is true (``upii mcp enable``). Requires the optional ``mcp``
dependency group (``pip install "upii[mcp]"``).
"""
from typing import List, Optional

from upii.mcp.config import MCPConfig
from upii.mcp.service import MCPService, ToolDisabledError


def build_server(service: Optional[MCPService] = None, mcp_config: Optional[MCPConfig] = None):
    """Construct a :class:`FastMCP` app with the enabled tools registered.

    ``service`` is injectable for tests; otherwise one is built from ``mcp_config``
    (or the on-disk config). Only tools allowed by the config are registered, so a
    disabled tool is simply absent from ``list_tools`` — and calling it by name
    still yields a proper MCP error rather than a crash.
    """
    try:
        from mcp.server.fastmcp import FastMCP
        from mcp.server.fastmcp.exceptions import ToolError
    except ImportError as e:  # pragma: no cover - exercised via CLI message
        raise ImportError(
            "The MCP server needs the optional 'mcp' dependency group. "
            'Install it with: pip install "upii[mcp]"'
        ) from e

    cfg = mcp_config if mcp_config is not None else (service.cfg if service else MCPConfig.load())
    svc = service if service is not None else MCPService(mcp_config=cfg)

    mcp = FastMCP(
        "upii",
        instructions=(
            "Local, cited memory of the user's own documents (UPII). All tools are "
            "read-only and run on-device. Use upii_search to retrieve ranked chunks "
            "with citations, upii_ask for a finished attributed answer, and "
            "upii_list_sources to see what memory is visible."
        ),
    )
    # Report UPII's version to clients rather than the SDK's default.
    try:
        import upii

        mcp._mcp_server.version = getattr(upii, "__version__", None)
    except Exception:
        pass

    def _mcp_error(e: ToolDisabledError):
        # A disabled/out-of-scope tool surfaces as a clean MCP error, never a crash.
        return ToolError(str(e))

    if cfg.tools.get("upii_search"):

        @mcp.tool(name="upii_search")
        def upii_search(
            query: str,
            k: int = 8,
            since: Optional[str] = None,
            source: Optional[str] = None,
        ) -> List[dict]:
            """Search local memory. Returns ranked chunks with text, chunk_id,
            doc_path, source, fused score and a semantic/temporal/relational
            breakdown. ``since`` accepts a time token (e.g. "last_week"); ``source``
            narrows to one source_type. Read-only."""
            try:
                return svc.search(query, k=k, since=since, source=source)
            except ToolDisabledError as e:
                raise _mcp_error(e)

    if cfg.tools.get("upii_ask"):

        @mcp.tool(name="upii_ask")
        def upii_ask(question: str) -> dict:
            """Answer a question from local memory using the on-device reasoning
            path (Ollama/mock). Returns an attributed answer plus the cited chunk
            list. Read-only."""
            try:
                return svc.ask(question)
            except ToolDisabledError as e:
                raise _mcp_error(e)

    if cfg.tools.get("upii_list_sources"):

        @mcp.tool(name="upii_list_sources")
        def upii_list_sources() -> List[dict]:
            """List the sources currently visible to MCP clients, each with its
            document/chunk counts and last-updated time. Read-only."""
            try:
                return svc.list_sources()
            except ToolDisabledError as e:
                raise _mcp_error(e)

    return mcp


def serve(mcp_config: Optional[MCPConfig] = None) -> None:
    """Blocking entry point for ``upii mcp serve`` (stdio transport)."""
    cfg = mcp_config if mcp_config is not None else MCPConfig.load()
    if not cfg.enabled:
        raise RuntimeError(
            "MCP server is disabled. Run 'upii mcp enable' first (it is off by default)."
        )
    server = build_server(mcp_config=cfg)
    server.run()  # stdio transport by default
