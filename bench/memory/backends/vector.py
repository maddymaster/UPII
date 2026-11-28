"""Plain vector search: cosine similarity over raw turns, nothing else.

Uses upii's own embedder (all-MiniLM-L6-v2), so the difference between this and
the ``upii`` backend is what upii adds beyond embedding search (chunking, fusion,
threshold), not a different embedding model.
"""

from __future__ import annotations

import numpy as np

from . import BaseBackend


def _default_embed(texts: list[str]) -> np.ndarray:
    from upii.analysis.embeddings import Embedder
    return np.asarray(Embedder().embed(texts), dtype=np.float32)


class VectorBackend(BaseBackend):
    name = "vector"

    def __init__(self, embed=None) -> None:
        super().__init__()
        self._embed = embed or _default_embed
        self.vectors: dict[str, list[np.ndarray]] = {}

    def _add(self, user_id: str, new_turns: list[dict]) -> None:
        if not new_turns:
            return
        vecs = self._embed([t["text"] for t in new_turns])
        self.vectors.setdefault(user_id, []).extend(_unit(v) for v in vecs)

    def _search(self, query: str, user_id: str, top_k: int) -> list[dict]:
        turns = self.turns.get(user_id, [])
        if not turns:
            return []
        q = _unit(self._embed([query])[0])
        sims = np.stack(self.vectors[user_id]) @ q
        order = np.argsort(-sims, kind="stable")[:top_k]
        return [
            {"id": turns[i]["id"], "memory": turns[i]["text"], "score": float(sims[i]),
             "created_at": turns[i]["created_at"]}
            for i in order
        ]

    async def delete_user(self, user_id: str) -> bool:
        self.vectors.pop(user_id, None)
        return await super().delete_user(user_id)


def _unit(v) -> np.ndarray:
    v = np.asarray(v, dtype=np.float32)
    n = float(np.linalg.norm(v))
    return v / n if n else v
