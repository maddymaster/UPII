"""Memory backends for the pinned memory-benchmarks harness.

The harness's LoCoMo and LongMemEval runners talk to a memory client with
``add(messages, user_id, timestamp=...)``, ``search(query, user_id, top_k=...)``,
``delete_user(user_id)``, ``get_user_profile(user_id)`` and ``close()``, and use it
as an async context manager. Every backend here provides exactly that, so the
harness's prompts, judge and metrics run unchanged on top of it.

``search`` returns dicts with ``memory``, ``score``, ``id`` and ``created_at``
(ISO 8601, no timezone), which is what the harness's ``format_search_results``
and answer prompts read.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

BACKENDS = ("full_history", "vector", "mem0_oss", "upii")


def iso_at(timestamp: int | float | None, offset_s: int = 0) -> str:
    """ISO timestamp the harness prompts can parse; ``offset_s`` keeps turn order."""
    if timestamp is None:
        return ""
    dt = datetime.fromtimestamp(float(timestamp) + offset_s, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


class BaseBackend:
    """Shared plumbing; subclasses implement ``_add`` and ``_search``."""

    name = "base"

    def __init__(self) -> None:
        # user_id -> list of turns: {"id", "text", "created_at"}
        self.turns: dict[str, list[dict[str, Any]]] = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    async def close(self) -> None:
        return None

    async def get_user_profile(self, user_id: str) -> None:
        return None

    def _record(self, messages: list[dict], user_id: str, timestamp) -> list[dict]:
        stored = self.turns.setdefault(user_id, [])
        new = []
        for msg in messages:
            text = (msg.get("content") or "").strip()
            if not text:
                continue
            n = len(stored)
            turn = {"id": f"{user_id}:{n}", "text": text,
                    "created_at": iso_at(timestamp, offset_s=n), "timestamp": timestamp}
            stored.append(turn)
            new.append(turn)
        return new

    async def add(self, messages: list[dict], user_id: str, timestamp=None, **_: Any) -> dict:
        new = self._record(messages, user_id, timestamp)
        self._add(user_id, new)
        return {"results": [{"memory": t["text"], "event": "ADD"} for t in new]}

    async def search(self, query: str, user_id: str, top_k: int = 200, **_: Any) -> list[dict]:
        return self._search(query, user_id, top_k)

    async def delete_user(self, user_id: str) -> bool:
        self.turns.pop(user_id, None)
        return True

    def _add(self, user_id: str, new_turns: list[dict]) -> None:  # pragma: no cover
        pass

    def _search(self, query: str, user_id: str, top_k: int) -> list[dict]:  # pragma: no cover
        raise NotImplementedError


def make_backend(name: str, **kwargs: Any) -> BaseBackend:
    if name == "full_history":
        from .full_history import FullHistoryBackend
        return FullHistoryBackend()
    if name == "vector":
        from .vector import VectorBackend
        return VectorBackend()
    if name == "mem0_oss":
        from .mem0_oss import Mem0OSSBackend
        return Mem0OSSBackend(**kwargs)
    if name == "upii":
        from .upii import UpiiBackend
        return UpiiBackend(**kwargs)
    raise ValueError(f"unknown backend {name!r}; choose from {', '.join(BACKENDS)}")
