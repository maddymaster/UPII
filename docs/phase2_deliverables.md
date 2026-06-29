# Phase 2 — Deliverables vs. Grant Milestones

**Phase:** ELEVATE NxT, Tranche-1 **Phase 2** — *Harden ingestion + deterministic chunking at scale.*
**Annexure-1 milestone:** **T1.2** — Deterministic, reproducible, content-addressed ingestion.
**Status date:** 29 June 2026

> **Grant demonstration (verbatim):** *"100% reproducible chunk hashes on a ≥ 1,000,000-chunk
> corpus; recorded CLI demo of re-ingestion to identical state; dedup + edit-diff +
> delete-handling validated."*

---

## 1. Deliverable scorecard

| # | Grant deliverable (Prompt 2.1–2.3) | Built | Artifact(s) | Status |
|---|---|---|---|---|
| 2.1a | Reproducibility audit of chunker + ingest path | ✅ | `docs/phase2_reproducibility_audit.md` (7 findings F1–F7, each with a resolution) | **Done** |
| 2.1b | Chunk boundaries + hashes a pure function of (content, config) | ✅ | `src/upii/ingestion/chunker.py`, `src/upii/ingestion/identity.py` | **Done** |
| 2.1c | `tests/test_chunk_determinism.py` (twice + shuffled order ⇒ identical hashes) | ✅ | 4 tests, all green | **Done** |
| 2.2a | Dedup: unchanged re-ingest is a no-op | ✅ | `src/upii/ingestion/pipeline.py` | **Done** |
| 2.2b | Edit: re-chunk changed only; untouched hashes stable; purge stale | ✅ | `pipeline.py` + `db.delete_document` + `vector.delete` | **Done** |
| 2.2c | Delete: clean removal of chunks / vectors / metadata | ✅ | `pipeline.remove_document` | **Done (capability)** ¹ |
| 2.2d | `tests/test_incremental.py` with count assertions in `upii.db` + vector store | ✅ | 4 tests, all green | **Done** |
| 2.2e | `scripts/bench/scale_check.py` → `bench/results/scale_REPORT.md` | ✅ | 12-check harness, scales to ~1M chunks | **Done** ² |
| 2.3 | `scripts/demo/repro_demo.sh` — recordable re-ingestion demo | ✅ | runs through the real `upii` CLI | **Done** |

¹ The delete **capability** is implemented and tested. It is intentionally **not yet wired** to a
user-facing trigger (the inbox "approve a deletion event" path stays a no-op `acknowledge`, per the
existing inbox contract in `tests/test_inbox.py`). A `upii forget <path>` command is the natural
trigger and is a small follow-up — see §5.

² The harness has been validated up to **3,000 chunks** locally. The ≥1,000,000-chunk run is the
hardware demonstration (`--docs 20000` on the procured Mac Studio); hash reproducibility is
independent of corpus size and embedder.

---

## 2. What was built (engineering detail)

### New modules
- **`src/upii/ingestion/identity.py`** — `doc_id_for(content_hash)`: the single deterministic source
  of document ids. Eliminates the random `uuid4()` that previously made the chunk→document linkage
  irreproducible (finding **F1**) and fixes the `--force` linkage bug (**F4**).
- **`src/upii/ingestion/pipeline.py`** — one ingest/remove code path shared by the `ingest` command,
  the `watch`-approve flow, and the demo seed. Encodes dedup (no-op), edit cleanup, and delete once,
  so the three callers can't drift.

### Changed behaviour
- **`chunker.py`** — `chunk_hash` is now `sha256(f"{chunk_size}:{overlap}:{chunk_text}")` — a pure
  function of (chunk text, chunker config). It no longer mixes in the whole-file content hash, so an
  edit elsewhere leaves an **unchanged chunk's hash stable** (the T1.2 "re-chunk only changed
  chunks" property). Same text + same config ⇒ same id, always.
- **`loader.py`** — directory traversal sorts dirs + files, so ingest order is a pure function of the
  tree, not of filesystem ordering (**F2**).
- **`db.py`** — added `get_documents_by_path`, `get_chunk_ids_for_doc`, `delete_document`
  (explicit cascade to chunks / entity_edges / tasks; returns chunk ids for vector cleanup).
- **`vector.py`** — added `delete(doc_hash)` and `delete_chunks(ids)` (LanceDB `table.delete`), and
  the pipeline now delete-then-adds vectors per doc so a forced re-ingest can't accumulate duplicates
  (finding **F5/F4**).
- **`cli.py`** — `ingest`, `watch`-approve and `demo seed` all route through the pipeline; the ingest
  summary now reports updated-vs-new counts.

---

## 3. Features delivered, mapped to the grant

| Grant property | How it is delivered now |
|---|---|
| **Content-addressed identity** | `doc_id` and `chunk_id` are both pure hash functions — no UUIDs, no wall-clock, no path dependence. |
| **Idempotent ingestion (dedup)** | Re-ingesting unchanged bytes is a complete no-op (verified: 0 new docs/chunks/vectors). |
| **Incremental edit (chunk-level diff)** | An edited file re-chunks; byte-identical regions keep stable hashes; stale chunks + vectors are purged; one document row per path. |
| **Clean delete** | `remove_document` removes chunks, vectors and metadata, leaving zero residue. |
| **Reproducibility at scale** | An independent re-ingest of the regenerated corpus reproduces 100% of chunk hashes. |
| **Demonstrability** | A recordable terminal demo + a one-command scale/repro harness producing a report artifact. |

---

## 4. Metrics

### 4.1 Correctness / reproducibility (the T1.2 metrics)
From `bench/results/scale_REPORT.md`, latest local run (`--docs 500 --paras 60`):

| Metric | Value |
|---|---|
| Documents ingested | 500 |
| Chunks produced | 3,000 |
| **Chunk-hash reproducibility (independent re-ingest)** | **3,000 / 3,000 = 100%** |
| Dedup on unchanged re-ingest | 500 / 500 files no-op (0 new chunks) |
| Edit: files updated | 50 / 50 reported as `updated`; stale chunks purged, new chunks added |
| Delete: docs removed | 450 → store holds exactly 450; 300 chunks purged |
| Vector ↔ chunk count parity | Maintained through ingest → edit → delete (3000→3050→2750) |
| **Checks passed** | **12 / 12** |

> The headline metric for T1.2 is **100% hash reproducibility** + correct dedup/edit/delete counts —
> all confirmed. (The ingest *throughput* metric belongs to **Phase 1 / T1.1** and is measured with
> the real embedder on the procured hardware; the figure in the scale harness uses a deterministic
> fake embedder and is not a throughput claim.)

### 4.2 Test coverage added in Phase 2

| Suite | Tests | Result |
|---|---|---|
| `tests/test_chunk_determinism.py` | 4 | ✅ pass |
| `tests/test_incremental.py` | 4 | ✅ pass |
| **Total new** | **8** | **8 pass** |

Full suite after Phase 2: **53 passed, 11 failed**. All 11 failures pre-exist this work and are out
of T1.2 scope (RAG requires a live LLM; entity/search/rehydration/watcher are separate in-flight
work), confirmed against a clean `HEAD` worktree.

---

## 5. Not yet done / follow-ups

- **`upii forget <path>` command** — expose the implemented delete capability behind a user-facing
  command (and/or wire the watcher's deletion events to it) without disturbing the inbox contract.
- **≥1,000,000-chunk hardware run** — execute `scripts/bench/scale_check.py --docs 20000` on the
  procured Mac Studio and archive the resulting `scale_REPORT.md` + a screen recording as the formal
  T1.2 demonstration artifact.
- **Real-embedder scale pass** — optional `--real-embed` run to co-validate the embedding path under
  the same harness.

---

## 6. How to reproduce

```bash
source venv/bin/activate

# Unit evidence (offline, fast)
python -m pytest tests/test_chunk_determinism.py tests/test_incremental.py -q

# Scale + 100% reproducibility report  ->  bench/results/scale_REPORT.md
python scripts/bench/scale_check.py --docs 500 --paras 60
#   grant/hardware run: python scripts/bench/scale_check.py --docs 20000

# Recordable re-ingestion demo
bash scripts/demo/repro_demo.sh
```

Audit detail: [`docs/phase2_reproducibility_audit.md`](phase2_reproducibility_audit.md).
