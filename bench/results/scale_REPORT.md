# Scale & Reproducibility Report (T1.2)

**Result:** ✅ ALL CHECKS PASSED

## Run parameters

- Documents: **500**  |  Chunks: **3000**  |  Paragraphs/doc: 60
- Embedder: FakeEmbedder (deterministic, hash-only validation)
- Edited: 50 docs  |  Deleted: 50 docs
- Ingest wall time: 32.5s  (~92 chunks/s)

## Checks

| Check | Result | Detail |
|---|---|---|
| vectors match chunks after ingest | ✅ PASS | (3000 == 3000) |
| docs ingested == corpus size | ✅ PASS | (500 == 500) |
| re-ingest is all no-ops | ✅ PASS | (skipped 500/500) |
| counts unchanged after re-ingest | ✅ PASS |  |
| edited files reported as updates | ✅ PASS | (updated 50/50) |
| vectors still match chunks after edits | ✅ PASS | (3050 == 3050) |
| edits introduced new chunk hashes | ✅ PASS |  |
| edits purged stale chunk hashes | ✅ PASS |  |
| delete removed the right number of docs | ✅ PASS | (450 == 450) |
| vectors match chunks after delete | ✅ PASS | (2750 == 2750) |
| delete purged > 0 chunks | ✅ PASS | (300 chunks) |
| independent re-ingest reproduces 100% of chunk hashes | ✅ PASS | (3000/3000 match) |

## What this proves

- **Deterministic chunking:** an independent re-ingest of the regenerated corpus
  reproduced **3000/3000** chunk hashes — 100% reproducible.
- **Dedup:** re-ingesting unchanged files was a complete no-op.
- **Edit:** changed files re-chunked and purged their stale chunks; vector store stayed in sync.
- **Delete:** removed files purged chunks, vectors and metadata cleanly.

> For the grant demonstration on the procured Mac Studio, run with `--docs 20000`
> (~1,000,000 chunks). Hash reproducibility is independent of the embedder.
