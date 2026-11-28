"""Mem0 open source, in process, on local models only.

The harness's own Mem0 mode talks to a Mem0 server in Docker; this machine has no
Docker, so this backend runs the ``mem0ai`` library directly: fact extraction with
a local Ollama model, all-MiniLM-L6-v2 embeddings (same as upii), and an on-disk
Qdrant store in a temporary folder. Nothing goes to a hosted service.

This is Mem0 OSS with our model choices, not Mem0's hosted platform; METHOD.md
says so wherever its numbers appear.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import tempfile
from typing import Any

from . import iso_at

# mem0 sends usage telemetry to PostHog unless this is off. It is read once, when
# mem0 is first imported, so it is set here, before any import of mem0.
os.environ["MEM0_TELEMETRY"] = "False"


def mem0_config(path: str, llm_model: str, ollama_url: str) -> dict:
    return {
        "llm": {"provider": "ollama",
                "config": {"model": llm_model, "ollama_base_url": ollama_url, "temperature": 0}},
        "embedder": {"provider": "huggingface",
                     "config": {"model": "sentence-transformers/all-MiniLM-L6-v2"}},
        "vector_store": {"provider": "qdrant",
                         "config": {"path": path, "collection_name": "bench",
                                    "embedding_model_dims": 384, "on_disk": True}},
        "history_db_path": f"{path}/history.db",
    }


class Mem0OSSBackend:
    name = "mem0_oss"

    def __init__(self, llm_model: str = "qwen3.8:27b", ollama_url: str = "http://127.0.0.1:11434",
                 memory: Any = None, **_: Any) -> None:
        self.root = tempfile.mkdtemp(prefix="mem0-bench-")
        if memory is None:
            try:  # use the cached MiniLM model without asking the HF Hub (as upii does)
                from upii.analysis.embeddings import prefer_offline_if_cached
                prefer_offline_if_cached("sentence-transformers/all-MiniLM-L6-v2")
            except ImportError:
                pass
            from mem0 import Memory
            memory = Memory.from_config(mem0_config(self.root, llm_model, ollama_url))
        self.m = memory

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    async def close(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    async def get_user_profile(self, user_id: str) -> None:
        return None

    async def add(self, messages: list[dict], user_id: str, timestamp=None, **_: Any) -> dict | None:
        # The OSS SDK rejects ``timestamp``; the session date goes into the text (so
        # extracted facts can carry it) and into metadata (so search can return it).
        created = iso_at(timestamp)
        if created:
            day = created[:10]
            messages = [{**m, "content": f"({day}) {m.get('content', '')}"} for m in messages]
        try:
            return await asyncio.to_thread(self.m.add, messages, user_id=user_id,
                                           metadata={"session_date": created})
        except Exception:  # the harness counts None as a failed chunk
            return None

    async def search(self, query: str, user_id: str, top_k: int = 200, **_: Any) -> list[dict]:
        res = await asyncio.to_thread(self.m.search, query, top_k=top_k,
                                      filters={"user_id": user_id}, threshold=0.0)
        rows = res.get("results", res) if isinstance(res, dict) else res
        return [{"id": r.get("id", ""), "memory": r.get("memory", ""), "score": r.get("score", 0.0),
                 "created_at": (r.get("metadata") or {}).get("session_date") or r.get("created_at", "")}
                for r in rows]

    async def delete_user(self, user_id: str) -> bool:
        await asyncio.to_thread(self.m.delete_all, user_id=user_id)
        return True
