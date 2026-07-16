# Changelog

All notable changes to UPII are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Versions remain `0.x` until signed installers ship as `v1.0.0`.

## [Unreleased]

### Added
- **Typed entity extraction** — `EntityExtractor` now emits `PERSON` / `ORG` /
  `PROJECT` (previously only `PROJECT` / `TOPIC`), with the full surface form as the
  name (`Project Omega`, not `Omega`; `Dr. Sivan` with the title). Precision-first,
  dependency-light rules: project triggers, title-cued and known-given-name people,
  corporate-suffix and acronym organisations (with a tech-acronym stop-list). This
  is the extractor half of local knowledge-graph work (T1.4).
- **Entity-extraction eval** (`eval/entities/`, `eval/run_entity_eval.py`) — a
  committed 500-document labelled fixture (deterministic generator + gold labels,
  fingerprint-guarded) scoring set-based precision / recall / F1 per type, written
  to `eval/results/entity_REPORT.md`. Current result: **overall precision 1.000**
  (target ≥ 0.80), recall 0.920, F1 0.959. The fixture is deliberately hard —
  acronyms, single/titled names, corporate suffixes, plus adversarial distractors
  (capitalised non-entities, tech acronyms) and a pool of uncommon names the
  rule-based extractor cannot recover, so recall is honestly below 1.0.
  Regenerate with `python eval/run_entity_eval.py --rebuild`.
- `upii ask --no-answer` — retrieval-only mode: runs fusion + `--debug` scoring and
  prints the cited chunks, but skips LLM generation. Output is fully deterministic,
  so `scripts/demo/phase3_demo.sh` is now byte-identical run to run (the generated
  answer was the one stochastic element). Covered by `tests/test_ask_no_answer.py`.

### Fixed
- Entity extractor: the org-suffix rule no longer swallows a preceding sentence's
  final word across a full stop (`...last Friday. Meridian Systems`), and a
  repeated entity now claims its text span so a bare-name rule cannot re-emit it as
  a separate false positive. Both were found by the new entity eval and are pinned
  by regression tests in `tests/test_entity_extraction.py`.

## [0.6.0] - 2026-07-16

Retrieval, knowledge-graph, benchmarking and packaging work on top of `v0.5.0`.
These are feature-level changes, so they release as `v0.6.0` — not as a patch.

### Added
- **Context Rehydrator v2** — multi-signal fusion ranking. Candidate chunks are
  scored on three complementary signals (semantic, temporal, relational) and
  fused into one ranked context window; the fused score and its per-signal
  breakdown are attached to each result rather than ranking on cosine distance
  alone, and surfaced by `upii ask --debug`. **In this release the semantic signal
  is the only one that moves the ranking:** the relational signal is implemented
  and weighted but has no data source — ingestion does not yet extract entities
  (T1.4) — so it contributes 0 on every query; the temporal signal is a per-chunk
  ingest-recency score, which is uniform on a bulk-ingested corpus and so acts as a
  constant offset. Ranking is therefore effectively semantic. See *Known
  limitations*.
- **Knowledge-graph visualization** — `upii knowledge --graph` renders whatever is
  in the local entity graph to a self-contained HTML file (`--out`, default
  `graph.html`). Ingestion does not currently populate the graph, so on a real
  corpus it renders **empty**; only `upii demo` seeds nodes. See *Known
  limitations*.
- **Retrieval evaluation harness** (`eval/`) — scores the live retrieval path
  (`SearchEngine` → `ContextRehydrator`) against a committed labelled dataset,
  reporting Recall@{1,5,10}, MRR and nDCG@10. Current result: **Recall@10 =
  0.958** against a target of ≥ 0.85 — a retrieval-quality number, in which
  ranking is effectively semantic (not fusion evidence). The report now carries a
  **config snapshot + fingerprint**, so a quoted number travels with the fusion
  weights and retrieval settings that produced it. Regenerate with
  `python eval/run_eval.py --rebuild`; exits non-zero below target, so it can gate
  CI.
- **Performance benchmark harness** (`scripts/bench/make_corpus.py`,
  `scripts/bench/benchmark.py`) → `bench/results/REPORT.md`. Deterministic corpus
  (fixed seed), real pipeline, real MiniLM, live `SearchEngine().search()`.
  Measured **627 docs/min** (target ≥ 500) and **retrieval p50 40 ms** (target
  < 300) at 99,702 chunks on an Apple M5 MacBook. Emits a throughput-vs-index-size
  curve. One command: `bash scripts/demo/phase1_demo.sh`.
- **Recordable phase demos** — `scripts/demo/phase1_demo.sh` (throughput +
  latency) and `scripts/demo/phase3_demo.sh` (ingest → `upii ask --debug` →
  eval → Recall@10, with a control run that shows the non-semantic signals do not
  affect ranking today).
- **PyPI packaging** — `pyproject.toml` metadata, `[dev]` and `[overlay]` extras,
  and `.github/workflows/pypi-publish.yml` publishing on `v*` tags via Trusted
  Publishing (OIDC, no stored token).
- **CI** (`.github/workflows/ci.yml`) — pytest on Python 3.10/3.11/3.12 across
  ubuntu/macos/windows, plus a wheel build that smoke-tests `upii --help`.
- `tests/test_version.py` — fails if `pyproject.toml` and `upii.__version__`
  drift apart.
- `tests/test_batch_ingest.py` — batch ingest matches the per-document path
  exactly, and a mid-batch edit cannot resurrect deleted vectors.
- `docs/evidence.md` — running index of milestone → artifact → headline number.
- `docs/mcp_server_scope.md` — scope for exposing `upii_search` / `upii_ask` as
  local MCP tools.
- This changelog.

### Changed
- README rewritten for a public developer audience: cited-answer example,
  quickstart, comparison table and roadmap, replacing the previous internal
  framing.
- Repository prepared for public release — internal strategy, product-requirement
  and programme material is no longer tracked (retained locally via
  `.gitignore`); remaining docs, source comments and benchmark scripts reworded
  to neutral technical language.
- `requires-python` narrowed to `>=3.10,<3.13`, matching the tested matrix.
- Eval baseline regenerated. Rewording an eval **fixture**
  (`eval/dataset/corpus/performance_slo.md`) changed its chunk hashes and the
  corpus fingerprint, moving one query's first hit from rank 2 to 3: MRR
  0.917 → 0.903 and nDCG@10 0.918 → 0.911. Recall@10 — the target metric — is
  unchanged at 0.958. Two consecutive runs are byte-identical, so the harness
  itself is deterministic; `eval/results/` now matches what
  `python eval/run_eval.py --rebuild` produces.
- `release.yml` builds on Python 3.11; it previously built on 3.9, which
  `requires-python` now excludes.
- README documents the knowledge-graph gap in an explicit **Known gaps** block;
  the previous text listed KG visualization and tri-signal fusion as working.
- Project URLs in `pyproject.toml` (and this changelog's compare links) point at
  the actual repository, `github.com/maddymaster/UPII`.

### Fixed
- **Ingestion throughput — 145 → 627 docs/min (4.3×).** `LocalVectorStore.add()`
  ran **once per document** (`open_table` + `table.add`), so every document
  appended a new LanceDB version and per-append cost grew with the index —
  throughput decayed from 486 to 88 docs/min as the corpus grew. New
  `ingest_documents()` in `src/upii/ingestion/pipeline.py` batches vector writes
  (one append per N documents) and skips the delete-before-add on non-forced
  ingests; `upii ingest` is wired to it. This was algorithmic, not hardware: it is
  what moved the Phase 1 ingestion metric from MISS to PASS. Phase 2's dedup / edit
  / delete semantics and 100% hash reproducibility are unchanged (both paths share
  one core; `scripts/bench/scale_check.py` still passes all 12 invariants).
- `upii ask --debug` fusion table no longer truncates its signal columns to
  ellipses on a normal-width terminal; the free-text chunk column yields width
  instead.
- `psutil` is declared as a dev dependency. `tests/perf/test_long_running.py`
  imported it without declaring it, so `pytest` failed at collection on a fresh
  clone.
- `tests/test_rag.py` asserted a contract `LocalLLM` no longer implements
  (raising `ModelError` on backend failure, and an "I don't know" answer with no
  context). Updated to the current mock-fallback contract — the system always
  responds — and pinned to the local path, so a developer with `GEMINI_API_KEY`
  exported no longer sends test prompts to the real API.

### Known limitations
- **The knowledge graph is not populated by ingestion.** Entity extraction runs on
  your *query*, but no ingest path writes entities or edges, so:
  - the **relational fusion signal contributes 0** on every query — retrieval is
    effectively semantic in this release;
  - **`upii knowledge --graph` renders empty** on a real corpus (only `upii demo`
    seeds nodes).

  The temporal signal is likewise a uniform recency offset on a bulk-ingested
  corpus, so it cannot reorder results. `bash scripts/demo/phase3_demo.sh`
  demonstrates exactly this (STEP 3b: zeroing the temporal and relational weights
  leaves the ranking unchanged). Wiring entity extraction into the ingestion
  pipeline is targeted for the next release (T1.4); it also requires replacing the
  regex entity extractor, which cannot recover most entity names from a query.

## [0.5.0] - 2026-06-30

Deterministic, reproducible, content-addressed ingestion.

**Headline:** an independent re-ingest reproduces **100% of chunk hashes**.

### Added
- **Content-addressed identity** — documents and chunks are identified by a hash
  of their content. No random UUIDs, no wall-clock, no path dependence: the same
  input yields the same memory state.
- **A single deterministic ingestion pipeline** (`src/upii/ingestion/pipeline.py`)
  shared by `ingest`, the `watch`-approve flow and the demo seed, so dedup / edit
  / delete semantics are defined once and cannot drift:
  - *dedup* — re-ingesting unchanged bytes is a no-op;
  - *edit* — a changed file re-chunks only what changed, untouched chunk hashes
    stay stable, and the prior version's chunks, vectors and metadata are purged;
  - *delete* — `remove_document` cleans chunks, vectors and metadata together.
- **Reproducibility harness** — `scripts/bench/scale_check.py` writes
  `bench/results/scale_REPORT.md`; validated locally to ~3,000 chunks.
- **Recordable demo** — `scripts/demo/repro_demo.sh` ingests, then re-ingests to
  an identical state.
- Determinism tests: `tests/test_chunk_determinism.py` (same corpus twice, and in
  shuffled order, yields identical hashes) and `tests/test_incremental.py`
  (dedup / edit / delete count assertions against SQLite and the vector store).

### Fixed
- Deterministic audit-log ordering in the ambient watcher.
- Cross-platform build scripts and release CI (`upload/download-artifact@v4`).

### Docs
- `docs/phase2_reproducibility_audit.md` — non-determinism audit of the chunker
  and ingest path: seven findings, each with its resolution.

[Unreleased]: https://github.com/maddymaster/UPII/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/maddymaster/UPII/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/maddymaster/UPII/releases/tag/v0.5.0
