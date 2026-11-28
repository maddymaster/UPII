"""Full-history baseline: every stored turn, in conversation order, no retrieval.

Scores fall by a tiny step per turn so the harness's score sort keeps insertion
order; the answer prompt then re-sorts by ``created_at``, which also follows
insertion order (see ``iso_at``). The runner lifts the harness's 200-memory prompt
limit and uses a single unlimited cutoff for this backend, so the model sees the
whole conversation.
"""

from __future__ import annotations

from . import BaseBackend


class FullHistoryBackend(BaseBackend):
    name = "full_history"

    def _search(self, query: str, user_id: str, top_k: int) -> list[dict]:
        turns = self.turns.get(user_id, [])
        return [
            {"id": t["id"], "memory": t["text"], "score": 1.0 - i * 1e-6,
             "created_at": t["created_at"]}
            for i, t in enumerate(turns)
        ]
