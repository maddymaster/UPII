# Phase 2 — Reproducibility Audit (deterministic chunking + incremental ingest)

**Milestone:** ELEVATE NxT Annexure-1 **T1.2** — *100% reproducible chunk hashes at scale; re-ingestion to identical state; dedup + edit-diff + delete validated.*

**Scope of audit:** `src/upii/ingestion/chunker.py`, `src/upii/ingestion/loader.py`, and the ingest path in `src/upii/cli.py` (`ingest`, plus the `watch`-approve and `demo seed` paths that duplicate it), `src/upii/storage/db.py`, `src/upii/storage/vector.py`.

The goal: chunk boundaries and chunk hashes must be a **pure function of `(file content, chunker config)`** only, and re-ingesting must converge to an identical store (dedup), with edits re-chunking only what changed and deletes cleaning up completely.

---

## Findings

| # | Source of non-determinism / gap | Where | Impact | Resolution |
|---|---|---|---|---|
| **F1** | `doc_id = uuid.uuid4()` is random per run; it is written to `documents.doc_id` **and** copied into every `chunks.doc_id` (`Chunk.doc_hash`). | `cli.py` ingest/watch/seed | `chunk_id` (PK) is reproducible, but the chunk→document linkage column is **not** — two ingests of the identical corpus produce different `chunks.doc_id` values. Breaks "identical state". | **Make `doc_id` content-addressed**: `doc_id = doc_id_for(content_hash)` (new `ingestion/identity.py`). Pure function of content. |
| **F2** | `os.walk` yields directories/files in arbitrary, filesystem-dependent order. | `loader.py` `LocalLoader.load` | Does not change chunk **hashes** (hash ignores order), but makes ingest order — and any order-sensitive scale check — irreproducible/flaky. | **Sort** dir + file names in the walk so traversal is deterministic. |
| **F3** | Editing a file produces a new `content_hash` → a brand-new `documents` row; the **old** row + its chunks + vectors are never removed. | ingest path | Orphaned stale chunks accumulate; an edited file is represented twice. Violates "edit re-chunks only changed chunks / leaves untouched hashes stable". | **Edit cleanup**: before inserting a new version, remove any prior document for the **same `source_path`** with a different `content_hash` (chunks + vectors + doc row). |
| **F4** | `upsert_document` `ON CONFLICT(content_hash)` keeps the existing PK `doc_id`, but `add_chunks` writes chunks with a **freshly-generated** `doc_id` on `--force`. | `db.py` + `cli.py` | On forced re-ingest, `documents.doc_id` and `chunks.doc_id` diverge → broken foreign-key linkage. | Resolved for free by **F1**: a content-addressed `doc_id` is identical every run, so upsert and chunks always agree. |
| **F5** | No delete support: `LocalVectorStore` never implements the `IVectorStore.delete` it declares; `DB` has no `delete_document`. | `vector.py`, `db.py` | A deleted/removed file's chunks, vectors and metadata cannot be cleaned. | **Implement** `LocalVectorStore.delete(doc_hash)` (LanceDB `table.delete`) and `DB.delete_document(content_hash)` (cascades to chunks); expose `remove_document()` in the pipeline and wire it to the watcher's deletion-approval. |
| **F6** | `vector.add` stamps each row with `datetime.now().isoformat()`. | `vector.py` | A wall-clock field in the vector store; not part of any hash or identity, but it makes vector rows non-byte-reproducible. | **Documented, out of scope for hashes.** Identity/dedup keys on `id` (= `chunk_hash`), which is deterministic. Left as ingest-time metadata. |
| **F7** | `created_at = datetime.fromtimestamp(st_ctime)` is filesystem/clock dependent. | `loader.py` | Stored on `documents.created_at`; **never** feeds a chunk hash. | **Acceptable.** Document provenance, not content identity. No change. |

### Already deterministic (verified, no change needed)

- `chunk_hash = sha256("{content_hash}-{idx}-{chunk_text}")` — a pure function of file content (`content_hash` = sha256 of file bytes) and chunker config (`chunk_size`/`overlap` drive `idx`/boundaries). This is the headline reproducibility property and it already holds.
- `compute_file_hash` streams raw bytes — encoding-independent, stable.

---

## Fixes applied

1. **`src/upii/ingestion/identity.py`** — `doc_id_for(content_hash)`: the single, deterministic source of document ids. Used by every ingest path.
2. **`src/upii/ingestion/pipeline.py`** — `ingest_document(...)` (dedup no-op + edit cleanup + chunk/embed/store) and `remove_document(...)` (delete cleanup). One code path, three callers (`ingest`, `watch`-approve, `demo seed`) converge on it.
3. **`loader.py`** — deterministic walk order (sorted dirs + files).
4. **`db.py`** — `get_documents_by_path`, `delete_document` (cascade chunks via explicit delete), used by edit + delete handling.
5. **`vector.py`** — `delete(doc_hash)`.

## Verification

- `tests/test_chunk_determinism.py` — ingest a fixed fixture twice **and** in shuffled file order; assert identical chunk hashes both times.
- `tests/test_incremental.py` — unchanged re-ingest is a no-op; edit re-chunks only changed chunks (untouched hashes stable); delete removes chunks/vectors/metadata. Asserts counts in `upii.db` and the vector store.
- `scripts/bench/scale_check.py` → `bench/results/scale_REPORT.md` — drives a large corpus through ingest → re-ingest (no-ops) → batch edits → deletes, proving 100% hash reproducibility and correct dedup/edit/delete counts.
- `scripts/demo/repro_demo.sh` — recordable terminal demo of re-ingestion to an identical state.
