"""Pure retrieval-ranking metrics.

Dependency-free on purpose: these functions take a ranked list of retrieved item
ids and the set of relevant ids, and return a number. No embeddings, no I/O — so
they are trivially unit-testable (see tests/test_eval_harness.py) and reusable.

Conventions
-----------
* ``ranked`` is an ordered list of retrieved ids, best first, no duplicates
  expected (call :func:`dedup_preserve_order` first if the retriever can repeat).
* ``relevant`` is the set of ids that count as correct for the query.
* ``k`` cutoffs count positions 1..k, i.e. ``ranked[:k]``.
* Every function assumes ``relevant`` is non-empty; a query with no relevant items
  is not scorable and should be filtered out by the caller.
"""

from __future__ import annotations

import math
from typing import Iterable, List, Sequence, Set


def dedup_preserve_order(ids: Iterable[str]) -> List[str]:
    """Return ``ids`` with later duplicates removed, order preserved."""
    seen: Set[str] = set()
    out: List[str] = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            out.append(i)
    return out


def _as_set(relevant: Iterable[str]) -> Set[str]:
    rel = set(relevant)
    if not rel:
        raise ValueError("relevant set is empty; query is not scorable")
    return rel


def recall_at_k(ranked: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """Fraction of relevant items that appear in the top ``k`` results.

    ``|relevant ∩ ranked[:k]| / |relevant|``. Ranges 0.0–1.0.
    """
    rel = _as_set(relevant)
    topk = set(ranked[:k])
    return len(topk & rel) / len(rel)


def precision_at_k(ranked: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """Fraction of the top ``k`` results that are relevant.

    Denominator is ``k`` (not ``len(ranked[:k])``) so short result lists are
    penalised the same way a scorer would expect at that cutoff.
    """
    rel = _as_set(relevant)
    if k <= 0:
        return 0.0
    hits = sum(1 for i in ranked[:k] if i in rel)
    return hits / k


def hit_rate_at_k(ranked: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """1.0 if any relevant item is in the top ``k``, else 0.0."""
    rel = _as_set(relevant)
    return 1.0 if any(i in rel for i in ranked[:k]) else 0.0


def reciprocal_rank(ranked: Sequence[str], relevant: Iterable[str]) -> float:
    """Reciprocal of the 1-based rank of the first relevant item (0.0 if none).

    The per-query term of MRR.
    """
    rel = _as_set(relevant)
    for idx, item in enumerate(ranked):
        if item in rel:
            return 1.0 / (idx + 1)
    return 0.0


def dcg_at_k(ranked: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """Discounted cumulative gain with binary relevance over the top ``k``.

    Gain of 1 for a relevant item at position ``i`` (1-based) discounted by
    ``1 / log2(i + 1)``.
    """
    rel = _as_set(relevant)
    dcg = 0.0
    for idx, item in enumerate(ranked[:k]):
        if item in rel:
            dcg += 1.0 / math.log2(idx + 2)  # idx is 0-based -> position idx+1
    return dcg


def ndcg_at_k(ranked: Sequence[str], relevant: Iterable[str], k: int) -> float:
    """Normalised DCG at ``k`` with binary relevance. Ranges 0.0–1.0.

    Ideal DCG places as many relevant items as fit (``min(|relevant|, k)``) in the
    top positions.
    """
    rel = _as_set(relevant)
    ideal_hits = min(len(rel), k)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(ideal_hits))
    if idcg == 0.0:
        return 0.0
    return dcg_at_k(ranked, rel, k) / idcg


def mean(values: Iterable[float]) -> float:
    """Arithmetic mean; 0.0 for an empty sequence."""
    vals = list(values)
    return sum(vals) / len(vals) if vals else 0.0
