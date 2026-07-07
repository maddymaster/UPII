# Postmortem: Duplicate Vectors on Force Re-ingest

Root cause: a forced re-ingest re-added vector rows without first removing the old
ones, so the LanceDB table accumulated duplicate embeddings for the same chunk id.
This inflated the index and skewed similarity scores. Fix: delete-then-add the
vectors for a document on every store, making the write idempotent. Verified with
a reproducibility test.
