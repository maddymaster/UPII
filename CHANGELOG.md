# Changelog

All notable changes to UPII are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Versions remain `0.x` until signed installers ship as `v1.0.0`.

## [Unreleased]

Retrieval, knowledge-graph and packaging work sitting on `main` after `v0.5.0`.
These are feature-level changes, so they release as `v0.6.0` — not as a patch.

### Added
- **Context Rehydrator v2** — multi-signal fusion ranking. Candidate chunks are
  scored on three complementary signals (semantic, temporal, relational) and
  fused into one ranked context window; the fused score and its per-signal
  breakdown are attached to each result rather than ranking on cosine distance
  alone.
- **Knowledge-graph visualization** — `upii knowledge --graph` renders the local
  entity graph to a self-contained HTML file (`--out`, default `graph.html`).
- **Retrieval evaluation harness** (`eval/`) — scores the live retrieval path
  (`SearchEngine` → `ContextRehydrator`) against a committed labelled dataset,
  reporting Recall@{1,5,10}, MRR and nDCG@10. Current result: **Recall@10 =
  0.958** against a target of ≥ 0.85. Regenerate with
  `python eval/run_eval.py --rebuild`; exits non-zero below target, so it can
  gate CI.
- **PyPI packaging** — `pyproject.toml` metadata, `[dev]` and `[overlay]` extras,
  and `.github/workflows/pypi-publish.yml` publishing on `v*` tags via Trusted
  Publishing (OIDC, no stored token).
- **CI** (`.github/workflows/ci.yml`) — pytest on Python 3.10/3.11/3.12 across
  ubuntu/macos/windows, plus a wheel build that smoke-tests `upii --help`.
- `tests/test_version.py` — fails if `pyproject.toml` and `upii.__version__`
  drift apart.
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

### Fixed
- `psutil` is declared as a dev dependency. `tests/perf/test_long_running.py`
  imported it without declaring it, so `pytest` failed at collection on a fresh
  clone.
- `tests/test_rag.py` asserted a contract `LocalLLM` no longer implements
  (raising `ModelError` on backend failure, and an "I don't know" answer with no
  context). Updated to the current mock-fallback contract — the system always
  responds — and pinned to the local path, so a developer with `GEMINI_API_KEY`
  exported no longer sends test prompts to the real API.

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

[Unreleased]: https://github.com/datafrontier/upii/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/datafrontier/upii/releases/tag/v0.5.0
