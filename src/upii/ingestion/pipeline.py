"""Single, deterministic ingest/remove code path.

Every place that promotes content into long-term memory (the `ingest` command, the
`watch`-approve flow, the demo seed) goes through here, so the dedup / edit / delete
semantics are defined once:

- **dedup**   — re-ingesting unchanged bytes is a no-op (same ``content_hash`` present).
- **edit**    — a changed file keeps its path but gets a new ``content_hash``; the prior
                version at that path (chunks + vectors + metadata) is removed first.
- **delete**  — removing a file purges its chunks, vectors and metadata.

Identity is content-addressed throughout: ``doc_id = doc_id_for(content_hash)`` and the
chunk id is a pure function of (chunk text, chunker config). Storage is therefore a pure
function of the corpus + config — re-ingesting converges to an identical state.
"""

from dataclasses import dataclass
from typing import List, Optional

from upii.core.types import Document, Chunk
from upii.ingestion.identity import doc_id_for


@dataclass
class IngestResult:
    status: str          # "skipped" (unchanged) | "ingested" (new) | "updated" (edit)
    doc_id: str
    content_hash: str
    n_chunks: int = 0    # chunks written for this document
    removed_chunks: int = 0  # stale chunks purged (prior version of an edited file)
    chunks: Optional[List[Chunk]] = None  # populated when (re)stored, else None


def _purge_prior_versions(doc: Document, db, vector_store) -> int:
    """Remove any document previously stored at ``doc.path`` whose content differs.

    Returns the number of stale chunks purged. This is the edit path: same source
    path, new content hash.
    """
    removed = 0
    for prior in db.get_documents_by_path(doc.path):
        if prior["content_hash"] == doc.content_hash:
            continue
        res = db.delete_document(prior["content_hash"])
        if res:
            vector_store.delete(res["doc_id"])
            removed += len(res["chunk_ids"])
    return removed


def ingest_document(doc, db, vector_store, embedder, chunker, *, force: bool = False) -> IngestResult:
    """Ingest one document deterministically.

    ``db``/``vector_store``/``embedder``/``chunker`` are injected so this is unit
    testable and shared by every caller. Returns an :class:`IngestResult`.
    """
    doc_id = doc_id_for(doc.content_hash)
    doc.doc_id = doc_id

    # 1. Dedup: identical bytes already stored -> no-op.
    if not force and db.get_document_by_hash(doc.content_hash) is not None:
        return IngestResult(status="skipped", doc_id=doc_id, content_hash=doc.content_hash)

    # 2. Edit: drop any prior version of this file before writing the new one.
    removed = _purge_prior_versions(doc, db, vector_store)

    # 3. Chunk + embed.
    chunks = chunker.chunk(doc)
    texts = [c.text for c in chunks]
    embeddings = embedder.embed(texts) if texts else []
    for i, chunk in enumerate(chunks):
        chunk.embedding = embeddings[i]

    # 4. Store. Delete-then-add the vectors for this doc so a forced re-ingest can't
    #    accumulate duplicate vector rows (the metadata stores are upsert/replace).
    db.upsert_document(doc, doc_id)
    db.add_chunks(chunks)
    vector_store.delete(doc_id)
    vector_store.add(chunks)

    status = "updated" if removed else "ingested"
    return IngestResult(
        status=status,
        doc_id=doc_id,
        content_hash=doc.content_hash,
        n_chunks=len(chunks),
        removed_chunks=removed,
        chunks=chunks,
    )


def remove_document(db, vector_store, *, path: Optional[str] = None, content_hash: Optional[str] = None) -> int:
    """Remove document(s) and their chunks/vectors/metadata.

    Provide ``path`` (removes every version stored at that path — the delete-a-file
    case) or ``content_hash`` (removes one specific version). Returns the number of
    chunks purged.
    """
    if path is None and content_hash is None:
        raise ValueError("remove_document requires path or content_hash")

    hashes: List[str]
    if content_hash is not None:
        hashes = [content_hash]
    else:
        hashes = [d["content_hash"] for d in db.get_documents_by_path(path)]

    removed = 0
    for h in hashes:
        res = db.delete_document(h)
        if res:
            vector_store.delete(res["doc_id"])
            removed += len(res["chunk_ids"])
    return removed
