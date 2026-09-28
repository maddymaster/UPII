# Evidence index

One row per milestone: what was demonstrated, the artifact that proves it, the
headline number, and the version it shipped in. Every artifact is regenerable
from a committed command — the commands are listed below the table.

| Phase | Milestone | Artifact | Headline number | Version |
|---|---|---|---|---|
| 1 | R&D infrastructure + performance baseline | [`bench/results/REPORT.md`](../bench/results/REPORT.md) | **1,971 docs/min** ingest (target ≥ 500) · **retrieval p50 115 ms** (target < 300) at 100,349 chunks | `v0.6.0` (re-measured at `0.8.1`) |
| 2 | Deterministic, reproducible, content-addressed ingestion | [`bench/results/scale_REPORT.md`](../bench/results/scale_REPORT.md), [`docs/phase2_reproducibility_audit.md`](phase2_reproducibility_audit.md) | **100% chunk-hash reproducibility** (dedup · edit · delete validated) | `v0.5.0` |
| 3 | Multi-signal retrieval (Context Rehydrator v2) | [`eval/results/REPORT.md`](../eval/results/REPORT.md) | **Recall@10 = 0.958** (target ≥ 0.85) — semantic + temporal; relational live but weight-0 by default | `v0.6.0` |
| 4 | Local knowledge graph — extraction (T1.4) + populated-on-ingest graph + viz | [`eval/results/entity_REPORT.md`](../eval/results/entity_REPORT.md) | **Entity precision = 1.000** (target ≥ 0.80) · recall 0.920 on a 500-doc labelled set; `upii knowledge --graph` renders the ingested graph | `v0.7.0` |
| MCP | UPII as a local MCP server — three read-only tools, consent-gated, in-process | [`tests/test_mcp_server.py`](../tests/test_mcp_server.py), [`docs/mcp_setup.md`](mcp_setup.md) | **MCP bridge live** — a standard MCP client → `upii mcp serve` (stdio) → cited chunks, **0 bytes egress**; consent off-by-default; 12 E2E tests (131 total) | `v0.8.0` |

## Regenerating each number

```bash
# Phase 1 — ingestion throughput + retrieval latency  (~5 min on an M5 Max; --docs 300 for a smoke run)
python scripts/bench/make_corpus.py --docs 7750 --paras 60 --out /tmp/upii-bench-corpus
python scripts/bench/benchmark.py --corpus /tmp/upii-bench-corpus --paras 60   # -> bench/results/REPORT.md

# Phase 2 — reproducibility + scale
python scripts/bench/scale_check.py --docs 500 --paras 60   # -> bench/results/scale_REPORT.md
pytest tests/test_chunk_determinism.py tests/test_incremental.py -q

# Phase 3 — retrieval quality
python eval/run_eval.py --rebuild                           # -> eval/results/REPORT.md (non-zero exit if below target)
upii ask "<query>" --debug --no-answer                      # per-signal fusion contributions for one ranking

# Phase 4 — knowledge graph
python eval/run_entity_eval.py --rebuild                    # -> eval/results/entity_REPORT.md (non-zero exit if precision < 0.80)
upii knowledge --graph --out graph.html                     # render the ingested graph, self-contained + offline

# MCP — local MCP server (needs Python >= 3.10 with the extra: pip install "upii[mcp]")
pytest tests/test_mcp_server.py -q                          # 12 E2E tests via the MCP client SDK (consent, determinism, scope, logging)
```

## Notes

- **Phase 1** was re-measured on an Apple **M5 Max MacBook Pro (18 cores, 48 GB),
  Python 3.12 — not the procured Mac Studio**. The run indexed **100,349 chunks**.
  The harness was run twice on the same machine and corpus: 2026-09-24 gave
  **2,032 docs/min / p50 117 ms**, and 2026-09-28 gave **1,971 docs/min / p50
  115 ms** — a ~3% spread that brackets the number in the table (the committed
  report holds the later run). Both numbers are scale-sensitive: throughput falls
  from ≈ 2,460 to ≈ 1,720 docs/min across the run (see the curve). The earlier
  baseline (2026-07-16, Apple M5 MacBook, 10 cores, 16 GB, Python 3.9, 99,702 chunks)
  measured **627 docs/min and p50 40 ms**; the cause of the higher median latency on
  the re-run has not been isolated. The same harness measured **145 docs/min** before
  per-document vector writes were batched. Re-run on the Studio for the
  hardware-target number.
- **Phase 2**'s `v0.5.0` tag was applied retroactively (2026-07-15) at commit
  `9b716ff`, the Phase 2 close. **It is intentionally never pushed** — an internal
  bookmark whose tree predates the packaging work; `v0.6.0` is the first (and only)
  tag that reaches the remote.
- **Phase 3** — Recall@10 = 0.958 is real, reproducible and deterministic, and it
  is **a semantic-search number**. Ingestion does not extract entities (T1.4), so
  the relational signal contributes 0 on every query, and the temporal signal is a
  uniform offset that cannot reorder. You can *demonstrate* this rather than take it
  on assertion — run the same query twice, once with the other two signals zeroed,
  and the ranking is identical:
  `upii ask "<query>" --debug --no-answer` then
  `upii ask "<query>" --w-temporal 0 --w-relational 0 --debug --no-answer`.
  **Do not cite 0.958 as evidence of multi-signal fusion.**
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
- **MCP** — "MCP bridge live" is not a benchmark number; it is a *capability* proven
  by an end-to-end run and an E2E test suite. `tests/test_mcp_server.py` spawns the
  real `upii mcp serve` as a subprocess and drives it with the official MCP client SDK
  over stdio; the client receives cited chunks from the seeded corpus, and every call
  is written to the on-device egress audit log (`mcp_call_log`). Excerpt from that log
  after one demo run (chunk ids truncated):

  ```
  2026-07-28 05:19:35  upii_search  n=3  q='Where does UPII store its vectors and docume…'  chunks=[8b2a3e84…, f580cc67…, e8292a0c…]
  2026-07-28 05:19:42  upii_ask     n=5  q='Where does UPII store its vectors and docume…'  chunks=[8b2a3e84…, f580cc67…, e8292a0c…]
  ```

  The server is **read-only** and **off by default**; exposure is gated by per-tool
  scopes and an `expose_sources` allowlist (distinct from local-CLI visibility), and a
  source disabled in `upii sources` is invisible to MCP. Consent invisibility,
  determinism (same corpus + query ⇒ identical chunk ids), and the disabled-tool error
  path are each covered by `tests/test_mcp_server.py`. No corpus byte leaves the device.
