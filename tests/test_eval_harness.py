"""Verify the eval harness metric math on a tiny, hand-checkable dataset.

These tests exercise only the pure functions in ``eval/metrics.py`` — no
embeddings, no index, no I/O — so they are fast and deterministic. The expected
values are derived directly from each metric's definition.
"""

import math
import os
import sys

import pytest

# ``eval`` lives at the repo root, not under the installed ``upii`` package.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eval.metrics import (  # noqa: E402
    dcg_at_k,
    dedup_preserve_order,
    hit_rate_at_k,
    mean,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)

# A tiny fixed "ranking": relevant items sit at positions 2 and 5 (1-based).
RANKED = ["a", "b", "c", "d", "e"]
RELEVANT = {"b", "e"}


def test_recall_at_k():
    assert recall_at_k(RANKED, RELEVANT, 1) == 0.0          # top-1 = {a}
    assert recall_at_k(RANKED, RELEVANT, 2) == 0.5          # {a,b} -> found b
    assert recall_at_k(RANKED, RELEVANT, 4) == 0.5          # e still not in top-4
    assert recall_at_k(RANKED, RELEVANT, 5) == 1.0          # both found
    assert recall_at_k(RANKED, RELEVANT, 10) == 1.0         # k past list length


def test_precision_at_k():
    assert precision_at_k(RANKED, RELEVANT, 1) == 0.0       # 0/1
    assert precision_at_k(RANKED, RELEVANT, 2) == 0.5       # 1 hit / 2
    assert precision_at_k(RANKED, RELEVANT, 5) == pytest.approx(2 / 5)


def test_hit_rate_at_k():
    assert hit_rate_at_k(RANKED, RELEVANT, 1) == 0.0
    assert hit_rate_at_k(RANKED, RELEVANT, 2) == 1.0
    assert hit_rate_at_k(RANKED, {"z"}, 5) == 0.0


def test_reciprocal_rank():
    # First relevant ("b") is at 1-based rank 2 -> 1/2.
    assert reciprocal_rank(RANKED, RELEVANT) == 0.5
    # Perfect: relevant item first -> 1.0.
    assert reciprocal_rank(["b", "a"], RELEVANT) == 1.0
    # No relevant item retrieved -> 0.0.
    assert reciprocal_rank(RANKED, {"z"}) == 0.0


def test_dcg_matches_definition():
    # Relevant at 1-based positions 2 and 5 -> discounts 1/log2(3) and 1/log2(6).
    expected = 1 / math.log2(3) + 1 / math.log2(6)
    assert dcg_at_k(RANKED, RELEVANT, 5) == pytest.approx(expected)
    # Cutoff excludes position 5.
    assert dcg_at_k(RANKED, RELEVANT, 4) == pytest.approx(1 / math.log2(3))


def test_ndcg_at_k():
    # Ideal DCG puts both relevant items in positions 1 and 2.
    idcg = 1 / math.log2(2) + 1 / math.log2(3)
    dcg = 1 / math.log2(3) + 1 / math.log2(6)
    assert ndcg_at_k(RANKED, RELEVANT, 5) == pytest.approx(dcg / idcg)

    # Perfect ranking -> nDCG 1.0.
    assert ndcg_at_k(["b", "e", "a", "c", "d"], RELEVANT, 5) == pytest.approx(1.0)

    # No hits -> 0.0.
    assert ndcg_at_k(RANKED, {"z"}, 5) == 0.0

    # nDCG is bounded in [0, 1].
    val = ndcg_at_k(RANKED, RELEVANT, 5)
    assert 0.0 <= val <= 1.0


def test_ndcg_single_relevant_first_is_one():
    assert ndcg_at_k(["x"], {"x"}, 10) == pytest.approx(1.0)


def test_empty_relevant_raises():
    # A query with no relevant items is not scorable.
    with pytest.raises(ValueError):
        recall_at_k(RANKED, set(), 5)
    with pytest.raises(ValueError):
        ndcg_at_k(RANKED, [], 5)


def test_dedup_preserve_order():
    assert dedup_preserve_order(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]
    assert dedup_preserve_order([]) == []


def test_mean():
    assert mean([1.0, 0.0, 0.5]) == pytest.approx(0.5)
    assert mean([]) == 0.0


def test_config_snapshot_reflects_live_config(monkeypatch):
    """The snapshot must read the live config, not a hardcoded copy.

    If it ever drifts from what retrieval actually uses, every report silently
    misattributes its numbers to the wrong weights — the exact failure the snapshot
    exists to prevent.
    """
    from eval.run_eval import config_snapshot

    before = config_snapshot()
    assert before["fusion_weights"] == {
        "semantic": 1.0,
        "temporal": 0.25,
        "relational": 0.5,
    }, "defaults changed — update this pin and re-run the eval so REPORT.md matches"

    # A changed weight must show up in the snapshot AND move the fingerprint.
    monkeypatch.setattr("upii.core.config.config.fusion_weight_temporal", 0.9)
    after = config_snapshot()
    assert after["fusion_weights"]["temporal"] == 0.9
    assert after["fingerprint"] != before["fingerprint"]


def test_metrics_on_perfect_and_worst_rankings():
    rel = {"a", "b"}
    perfect = ["a", "b", "c", "d"]
    worst = ["c", "d", "a", "b"]

    assert recall_at_k(perfect, rel, 2) == 1.0
    assert recall_at_k(worst, rel, 2) == 0.0
    assert reciprocal_rank(perfect, rel) == 1.0
    assert reciprocal_rank(worst, rel) == pytest.approx(1 / 3)
    assert ndcg_at_k(perfect, rel, 4) == pytest.approx(1.0)
