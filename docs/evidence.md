# Evidence index

One row per milestone: what was demonstrated, the artifact that proves it, the
headline number, and the version it shipped in. Every artifact is regenerable
from a committed command — the commands are listed below the table.

| Phase | Milestone | Artifact | Headline number | Version |
|---|---|---|---|---|
| 1 | R&D infrastructure + performance baseline | `scripts/bench/scale_check.py` → `bench/results/scale_REPORT.md` | *pending hardware run* | — |
| 2 | Deterministic, reproducible, content-addressed ingestion | [`bench/results/scale_REPORT.md`](../bench/results/scale_REPORT.md), [`docs/phase2_reproducibility_audit.md`](phase2_reproducibility_audit.md) | **100% chunk-hash reproducibility** (dedup · edit · delete validated) | `v0.5.0` |
| 3 | Multi-signal retrieval (Context Rehydrator v2) + local knowledge graph | [`eval/results/REPORT.md`](../eval/results/REPORT.md) | **Recall@10 = 0.958** (target ≥ 0.85) | *unreleased — on `main`* |

## Regenerating each number

```bash
# Phase 2 — reproducibility + scale
python scripts/bench/scale_check.py --docs 500 --paras 60   # -> bench/results/scale_REPORT.md
bash scripts/demo/repro_demo.sh                             # recordable: ingest -> re-ingest -> identical
pytest tests/test_chunk_determinism.py tests/test_incremental.py -q

# Phase 3 — retrieval quality
python eval/run_eval.py --rebuild                           # -> eval/results/REPORT.md (non-zero exit if below target)
upii knowledge --graph --out graph.html                     # local knowledge-graph render
```

## Notes

- **Phase 1** is harness-complete; the headline number awaits the hardware run.
  The scale harness is validated locally to ~3,000 chunks. Hash reproducibility
  is independent of corpus size and of the embedder, so the ~1M-chunk run
  (`--docs 20000`) confirms scale, not correctness.
- **Phase 2**'s `v0.5.0` tag was applied retroactively (2026-07-15) at commit
  `9b716ff`, the Phase 2 close — the last commit before Phase 3 work began.
- **Phase 3** is delivered on `main` but not formally closed: it still needs a
  `scripts/demo/phase3_demo.sh` and a `v0.6.0` tag. Until then its features are
  unreleased, which is why no version is cited.
