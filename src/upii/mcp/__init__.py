"""UPII MCP server — expose local memory to MCP clients, read-only, on localhost.

The server is OFF by default and consent-gated (see :mod:`upii.mcp.config`). It
runs in-process against the existing retrieval stack over stdio; no corpus byte
leaves the machine. Requires the optional ``mcp`` dependency group::

    pip install "upii[mcp]"
"""
