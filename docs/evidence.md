# Evidence index

One row per milestone: what was demonstrated, the artifact that proves it, the
headline number, and the version it shipped in. Every artifact is regenerable
from a committed command — the commands are listed below the table.

| Phase | Milestone | Artifact | Headline number | Version |
|---|---|---|---|---|
| 1 | R&D infrastructure + performance baseline | [`bench/results/REPORT.md`](../bench/results/REPORT.md) | **627 docs/min** ingest (target ≥ 500) · **retrieval p50 40 ms** (target < 300) | `v0.6.0` |
| 2 | Deterministic, reproducible, content-addressed ingestion | [`bench/results/scale_REPORT.md`](../bench/results/scale_REPORT.md), [`docs/phase2_reproducibility_audit.md`](phase2_reproducibility_audit.md) | **100% chunk-hash reproducibility** (dedup · edit · delete validated) | `v0.5.0` |
| 3 | Multi-signal retrieval (Context Rehydrator v2) | [`eval/results/REPORT.md`](../eval/results/REPORT.md) | **Recall@10 = 0.958** (target ≥ 0.85) — semantic + temporal; relational live but weight-0 by default | `v0.6.0` |
| 4 | Local knowledge graph — extraction (T1.4) + populated-on-ingest graph + viz | [`eval/results/entity_REPORT.md`](../eval/results/entity_REPORT.md) | **Entity precision = 1.000** (target ≥ 0.80) · recall 0.920 on a 500-doc labelled set; `upii knowledge --graph` renders the ingested graph | `v0.7.0` |

## Regenerating each number

```bash
# Phase 1 — ingestion throughput + retrieval latency  (~15-30 min; DOCS=100 for a smoke run)
bash scripts/demo/phase1_demo.sh                            # -> bench/results/REPORT.md

# Phase 2 — reproducibility + scale
python scripts/bench/scale_check.py --docs 500 --paras 60   # -> bench/results/scale_REPORT.md
bash scripts/demo/repro_demo.sh                             # recordable: ingest -> re-ingest -> identical
pytest tests/test_chunk_determinism.py tests/test_incremental.py -q

# Phase 3 — retrieval quality
bash scripts/demo/phase3_demo.sh                            # recordable: ingest -> ask --debug -> eval -> Recall@10
python eval/run_eval.py --rebuild                           # -> eval/results/REPORT.md (non-zero exit if below target)

# Phase 4 — knowledge graph
bash scripts/demo/phase4_demo.sh                            # recordable: ingest -> entity eval -> render graph.html
python eval/run_entity_eval.py --rebuild                    # -> eval/results/entity_REPORT.md (non-zero exit if precision < 0.80)
```

## Notes

- **Phase 1** was measured on an Apple **M5 MacBook (10 cores, 16 GB) — not the
  procured Mac Studio**. The run indexed **99,702 chunks**, just under the
  100,000-chunk corpus the retrieval target is defined against; both numbers are
  scale-sensitive (see the throughput-vs-index-size curve in the report). The
  **627 docs/min** figure is *post-batching-fix* — the same harness measured
  **145 docs/min** before per-document vector writes were batched. Re-run on the
  Studio for the hardware-target number.
- **Phase 2**'s `v0.5.0` tag was applied retroactively (2026-07-15) at commit
  `9b716ff`, the Phase 2 close. **It is intentionally never pushed** — an internal
  bookmark whose tree predates the packaging work; `v0.6.0` is the first (and only)
  tag that reaches the remote.
- **Phase 3** — Recall@10 = 0.958 is real, reproducible and deterministic, and it
  is **a semantic-search number**. Ingestion does not extract entities (T1.4), so
  the relational signal contributes 0 on every query, and the temporal signal is a
  uniform offset that cannot reorder. `scripts/demo/phase3_demo.sh` STEP 3b
  *demonstrates* this (identical ranking with temporal + relational zeroed) rather
  than asserting it. **Do not cite 0.958 as evidence of multi-signal fusion.**
- **Phase 4** — entity precision 1.000 is measured on a deliberately hard 500-doc
  fixture: precision is *earned* against adversarial distractors (multi-word
  capitalised non-entities, tech acronyms), not handed over by an easy set. Recall
  0.920 is honestly below 1.0 — the fixture includes uncommon names the rule-based
  extractor cannot recover without a title cue, and it does not pretend to. T1.4 is
  now **complete**: `upii ingest` populates the knowledge graph (deterministically,
  idempotently), and `upii knowledge --graph` renders it offline. The relational
  retrieval signal is therefore *live* — but wiring it revealed it is **not yet
  net-positive** on the retrieval eval (it can boost a chunk that merely mentions a
  query entity over a better semantic match: Recall@1 0.833 → 0.750, Recall@10 holds
  at 0.958). So its fusion weight ships at **0** (available via `upii ask
  --w-relational`); the Phase 3 retrieval number above is unchanged. Making it help
  is the honest next step, not a closed claim.
