"""MCP server configuration and consent state.

Persisted to a dedicated ``mcp.yaml`` next to the UPII database (mirroring how the
ambient :class:`~upii.ambient.sources.SourceRegistry` persists ``sources.yaml``), so
``upii mcp enable`` / ``disable`` never rewrite the user's hand-edited
``.upii_config.yaml``. The schema matches ``docs/mcp_server_scope.md``::

    enabled: false
    tools:
      upii_search: true
      upii_ask: true
      upii_list_sources: true
    expose_sources: all        # or an explicit list of source_types
    max_chunks_per_call: 12

Everything is off/closed by default: the server won't start unless ``enabled`` is
true, and a tool absent from ``tools`` is treated as disabled.
"""
import os
from dataclasses import dataclass, field
from typing import Dict, List, Union

import yaml

from upii.core.config import config as _core_config

# The three v1 tools. A tool is exposed only if enabled here AND in the config's
# ``tools`` map; unknown tool names are always disabled.
TOOL_NAMES = ("upii_search", "upii_ask", "upii_list_sources")

# ``expose_sources: all`` sentinel — every (consented) source_type is visible.
EXPOSE_ALL = "all"


def _default_tools() -> Dict[str, bool]:
    return {name: True for name in TOOL_NAMES}


@dataclass
class MCPConfig:
    """Resolved MCP settings. Off by default; safe to construct with no file."""

    enabled: bool = False
    tools: Dict[str, bool] = field(default_factory=_default_tools)
    # ``"all"`` (default) or an explicit list of source_types to expose to agents.
    expose_sources: Union[str, List[str]] = EXPOSE_ALL
    max_chunks_per_call: int = 12

    # -- persistence -----------------------------------------------------------
    @staticmethod
    def default_path() -> str:
        """``mcp.yaml`` in the same directory as the configured database."""
        return os.path.join(os.path.dirname(_core_config.db_path) or ".", "mcp.yaml")

    @classmethod
    def load(cls, path: str = None) -> "MCPConfig":
        path = path or cls.default_path()
        if not os.path.exists(path):
            return cls()
        try:
            with open(path, "r") as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            return cls()
        cfg = cls()
        if isinstance(data.get("enabled"), bool):
            cfg.enabled = data["enabled"]
        # Merge tool flags onto the defaults so a partial file still yields all keys.
        tools = _default_tools()
        for k, v in (data.get("tools") or {}).items():
            if k in tools and isinstance(v, bool):
                tools[k] = v
        cfg.tools = tools
        exp = data.get("expose_sources", EXPOSE_ALL)
        cfg.expose_sources = exp if (exp == EXPOSE_ALL or isinstance(exp, list)) else EXPOSE_ALL
        mcpc = data.get("max_chunks_per_call")
        if isinstance(mcpc, int) and mcpc > 0:
            cfg.max_chunks_per_call = mcpc
        return cfg

    def save(self, path: str = None) -> str:
        path = path or self.default_path()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            yaml.safe_dump(
                {
                    "enabled": self.enabled,
                    "tools": self.tools,
                    "expose_sources": self.expose_sources,
                    "max_chunks_per_call": self.max_chunks_per_call,
                },
                f,
                sort_keys=False,
            )
        return path

    # -- scope helpers ---------------------------------------------------------
    def tool_enabled(self, name: str) -> bool:
        """A tool is callable only if the server is on and the tool is allowed."""
        return bool(self.enabled and self.tools.get(name, False))

    def source_allowed_by_allowlist(self, source_type: str) -> bool:
        """Whether ``expose_sources`` permits this source_type (allowlist only).

        This is the MCP-exposure allowlist, distinct from ambient consent; the
        service intersects both (see :mod:`upii.mcp.service`).
        """
        if self.expose_sources == EXPOSE_ALL:
            return True
        return source_type in (self.expose_sources or [])
