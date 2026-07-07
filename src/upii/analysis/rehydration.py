
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import math
import json

from upii.core.types import RankedChunk
from upii.core.config import config
from upii.analysis.entity_extractor import EntityExtractor
from upii.storage.db import DB
from upii.storage.vector import LocalVectorStore
from upii.analysis.embeddings import Embedder

# The three fusion signals, in a fixed order for stable reporting.
SIGNALS = ("semantic", "temporal", "relational")


@dataclass
class _Candidate:
    """A chunk under consideration, accumulating raw per-signal scores.

    ``raw`` holds the un-normalised score each signal assigned this chunk (0.0 if a
    signal never touched it). Several signals can contribute to the *same* chunk —
    that is the whole point of fusion — e.g. a chunk found by vector search that is
    also linked to a query entity gets both a semantic and a relational score.
    """
    doc_hash: str
    chunk_hash: str
    text: str
    category: str = "note"
    start_char: int = 0
    end_char: int = 0
    index: int = 0
    raw: Dict[str, float] = field(default_factory=lambda: {s: 0.0 for s in SIGNALS})
    sources: set = field(default_factory=set)

    def bump(self, signal: str, value: float, source: str) -> None:
        """Record ``value`` for ``signal`` (keeping the max) and note the source."""
        if value > self.raw.get(signal, 0.0):
            self.raw[signal] = value
        self.sources.add(source)


class ContextRehydrator:
    """
    v2 multi-signal fusion for assembling and ranking context.

    Every candidate chunk is scored on three complementary signals, each
    normalised to [0,1] within the candidate set, then combined as a weighted sum
    (weights from :data:`config` or overridden per call):

    - **semantic**   — dense vector similarity to the query (LanceDB).
    - **temporal**   — recency of the chunk plus proximity of related calendar
                       events (``calendar_events``), decayed by a configurable
                       half-life.
    - **relational** — knowledge-graph overlap: chunks linked (via
                       ``entity_edges``) to entities mentioned in the query.

    The fused score and its per-signal breakdown are attached to each
    :class:`RankedChunk` (``.signals`` / ``.contributions``) so ``upii ask --debug``
    can show exactly why a chunk ranked where it did.
    """

    def __init__(self):
        self.db = DB()
        try:
            self.db.init_db()
        except Exception:
            pass
        self.vector_store = LocalVectorStore()
        self.embedder = Embedder.get_instance()
        self.entity_extractor = EntityExtractor()

    # -- public API ------------------------------------------------------------
    def rehydrate(
        self,
        query: str,
        time_filter: Optional[str] = None,
        limit: int = 5,
        weights: Optional[Dict[str, float]] = None,
    ) -> List[RankedChunk]:
        """Retrieve, fuse-rank and deduplicate context for ``query``.

        ``weights`` optionally overrides the configured fusion weights (any subset
        of ``semantic`` / ``temporal`` / ``relational``).
        """
        w = self._resolve_weights(weights)

        candidates: Dict[str, _Candidate] = {}
        # Retrieve a wider pool than `limit` so fusion has room to re-rank.
        pool = max(limit * 4, 20)
        self._collect_semantic(query, time_filter, pool, candidates)
        self._collect_temporal(query, candidates)
        self._collect_relational(query, candidates)

        return self._fuse(candidates, w, limit)

    # -- signal collection -----------------------------------------------------
    def _collect_semantic(
        self, query: str, time_filter: Optional[str], pool: int, candidates: Dict[str, _Candidate]
    ) -> None:
        """Dense vector search -> semantic score (+ per-chunk recency for temporal)."""
        try:
            query_vec = self.embedder.encode(query).tolist()
        except Exception:
            return
        where_clause = self._build_time_filter(time_filter)
        try:
            hits = self.vector_store.search_scored(query_vec, limit=pool, where_clause=where_clause)
        except Exception:
            hits = []

        now = datetime.now()
        for hit in hits:
            chk = hit["chunk"]
            cand = candidates.get(chk.chunk_hash)
            if cand is None:
                cand = _Candidate(
                    doc_hash=chk.doc_hash,
                    chunk_hash=chk.chunk_hash,
                    text=chk.text,
                    category="note",
                )
                candidates[chk.chunk_hash] = cand

            cand.bump("semantic", self._distance_to_similarity(hit.get("distance")), "vector")
            # A retrieved chunk also carries a temporal (recency) signal from when
            # it was ingested — recent memories are gently preferred.
            recency = self._recency_score(hit.get("timestamp"), now)
            if recency > 0:
                cand.bump("temporal", recency, "recency")

    def _collect_temporal(self, query: str, candidates: Dict[str, _Candidate]) -> None:
        """Calendar-event proximity -> temporal score (only for time-flavoured queries)."""
        temporal_keywords = ["last week", "yesterday", "today", "meeting", "met", "who", "talk"]
        if not any(k in query.lower() for k in temporal_keywords):
            return

        now = datetime.now()
        for event in self._get_calendar_events(query):
            parts = event.get("participants")
            if isinstance(parts, str):
                try:
                    parts = json.loads(parts)
                except Exception:
                    parts = [parts]
            parts_str = ", ".join(parts) if parts else "Unknown"
            text = f"[Calendar Event] {event['start_time']}: {event['title']} (Participants: {parts_str})"

            chunk_hash = f"cal_{event['event_id']}"
            cand = candidates.get(chunk_hash)
            if cand is None:
                cand = _Candidate(
                    doc_hash="calendar",
                    chunk_hash=chunk_hash,
                    text=text,
                    category="calendar",
                    end_char=len(text),
                )
                candidates[chunk_hash] = cand
            cand.bump("temporal", self._recency_score(event.get("start_time"), now), "calendar")

    def _collect_relational(self, query: str, candidates: Dict[str, _Candidate]) -> None:
        """Knowledge-graph entity overlap -> relational score.

        Entities mentioned in the query are looked up in the entity graph; every
        chunk linked to them gets a relational score. When that chunk is already a
        semantic candidate this *fuses* onto the existing entry (boosting it);
        otherwise the related chunk is introduced as a new candidate.
        """
        entities = self.entity_extractor.extract(query)
        for entity in entities:
            try:
                edges = self.db.get_entity_edges(entity.name)
            except Exception:
                edges = []
            for edge in edges:
                chunk_hash = edge["chunk_hash"]
                rel_score = float(edge.get("confidence") or 1.0)
                cand = candidates.get(chunk_hash)
                if cand is None:
                    cand = _Candidate(
                        doc_hash=edge.get("doc_id", "entity"),
                        chunk_hash=chunk_hash,
                        text=f"[Related to {entity.name}] {edge.get('text', '')}",
                        category="entity_recall",
                    )
                    candidates[chunk_hash] = cand
                cand.bump("relational", rel_score, f"entity:{entity.name}")

    # -- fusion ----------------------------------------------------------------
    def _fuse(
        self, candidates: Dict[str, _Candidate], weights: Dict[str, float], limit: int
    ) -> List[RankedChunk]:
        """Normalise each signal to [0,1], combine with weights, rank, truncate."""
        if not candidates:
            return []

        cands = list(candidates.values())
        # Max-normalise each signal across the candidate set so the strongest
        # candidate on a signal scores 1.0 and signals are comparable before
        # weighting. Max-norm (not min-max) keeps an absent signal at exactly 0.
        maxes = {s: max((c.raw.get(s, 0.0) for c in cands), default=0.0) for s in SIGNALS}

        ranked: List[RankedChunk] = []
        for c in cands:
            signals = {
                s: (c.raw.get(s, 0.0) / maxes[s]) if maxes[s] > 0 else 0.0 for s in SIGNALS
            }
            contributions = {s: weights.get(s, 0.0) * signals[s] for s in SIGNALS}
            fused = sum(contributions.values())

            dominant = max(SIGNALS, key=lambda s: contributions[s])
            reason = "+".join(
                f"{s}:{contributions[s]:.2f}" for s in SIGNALS if contributions[s] > 0
            ) or "none"

            ranked.append(
                RankedChunk(
                    doc_hash=c.doc_hash,
                    chunk_hash=c.chunk_hash,
                    text=c.text,
                    start_char=c.start_char,
                    end_char=c.end_char,
                    index=c.index,
                    embedding=None,
                    category=c.category,
                    score=fused,
                    boost_reason=reason,
                    source_signal=dominant,
                    signals=signals,
                    contributions=contributions,
                )
            )

        # Deterministic ordering: fused score desc, chunk_hash asc as tie-break.
        ranked.sort(key=lambda r: (-r.score, r.chunk_hash))
        return ranked[:limit]

    # -- helpers ---------------------------------------------------------------
    def _resolve_weights(self, override: Optional[Dict[str, float]]) -> Dict[str, float]:
        w = config.fusion_weights()
        if override:
            for k, v in override.items():
                if v is not None and k in w:
                    w[k] = float(v)
        return w

    @staticmethod
    def _distance_to_similarity(distance: Optional[float]) -> float:
        """Map a LanceDB distance (>=0, smaller = closer) to a similarity in (0,1].

        ``1 / (1 + distance)`` — monotonic, bounded, and gives 1.0 at distance 0.
        A missing distance falls back to a neutral non-zero similarity so the chunk
        still participates.
        """
        if distance is None:
            return 0.5
        return 1.0 / (1.0 + max(0.0, distance))

    def _recency_score(self, when, now: datetime) -> float:
        """Exponential-decay recency in [0,1] from a timestamp to ``now``.

        Half-life is ``config.temporal_halflife_days``. Future timestamps are
        clamped to a full score of 1.0; unparseable input scores 0.0.
        """
        dt = self._parse_dt(when)
        if dt is None:
            return 0.0
        age_days = (now - dt).total_seconds() / 86400.0
        if age_days <= 0:
            return 1.0
        halflife = max(0.1, config.temporal_halflife_days)
        return math.pow(0.5, age_days / halflife)

    @staticmethod
    def _parse_dt(when) -> Optional[datetime]:
        if when is None:
            return None
        if isinstance(when, datetime):
            return when
        try:
            return datetime.fromisoformat(str(when))
        except Exception:
            return None

    def _build_time_filter(self, time_filter: Optional[str]) -> Optional[str]:
        if not time_filter:
            return None
        now = datetime.now()
        if time_filter == "last_week":
            cutoff = now - timedelta(days=7)
            return f"timestamp >= '{cutoff.isoformat()}'"
        return None

    def _get_calendar_events(self, query: str) -> List[Dict]:
        start_date = None
        end_date = datetime.now()
        q = query.lower()
        if "last week" in q:
            start_date = end_date - timedelta(days=7)
        elif "yesterday" in q:
            start_date = end_date - timedelta(days=1)
            end_date = start_date + timedelta(days=1)
        elif "today" in q:
            start_date = end_date.replace(hour=0, minute=0)
        else:
            start_date = end_date - timedelta(days=30)

        return self.db.get_calendar_events(
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            limit=5,
        )

    # Kept for backward compatibility (unit-tested directly elsewhere).
    def _deduplicate_and_rank(self, candidates: List[RankedChunk], limit: int) -> List[RankedChunk]:
        """Merge duplicate chunk_hashes keeping the highest-scoring, then rank."""
        merged: Dict[str, RankedChunk] = {}
        for c in candidates:
            if c.chunk_hash not in merged or c.score > merged[c.chunk_hash].score:
                merged[c.chunk_hash] = c
        return sorted(merged.values(), key=lambda x: x.score, reverse=True)[:limit]
