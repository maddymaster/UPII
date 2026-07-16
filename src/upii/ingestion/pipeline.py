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
    doc_path: Optional[str] = None  # source path, so batch callers can report per-doc


def _purge_prior_versions(doc: Document, db, vector_store, before_delete=None) -> int:
    """Remove any document previously stored at ``doc.path`` whose content differs.

    Returns the number of stale chunks purged. This is the edit path: same source
    path, new content hash.

    ``before_delete`` is called at most once, immediately before the first deletion.
    A batch caller uses it to flush buffered vector writes first: a pending write for
    a document we are about to delete would otherwise land *after* the delete and
    resurrect its vectors.
    """
    removed = 0
    for prior in db.get_documents_by_path(doc.path):
        if prior["content_hash"] == doc.content_hash:
            continue
        if before_delete is not None:
            before_delete()
            before_delete = None
        res = db.delete_document(prior["content_hash"])
        if res:
            vector_store.delete(res["doc_id"])
            removed += len(res["chunk_ids"])
    return removed


def _ingest_core(doc, db, vector_store, embedder, chunker, force, flush=None):
    """Dedup, purge, chunk, embed and write metadata for one document.

    Returns ``(result, chunks_to_index)``. Writing those chunks to the vector store is
    the caller's job, which is what lets a batch caller amortise vector writes while
    keeping the dedup / edit / delete semantics defined exactly once, here.

    ``flush`` (batch callers only) writes out any buffered vectors; it is invoked
    before anything is deleted, so a buffered write can never resurrect deleted rows.
    """
    doc_id = doc_id_for(doc.content_hash)
    doc.doc_id = doc_id

    # 1. Dedup: identical bytes already stored -> no-op.
    if not force and db.get_document_by_hash(doc.content_hash) is not None:
        return IngestResult(status="skipped", doc_id=doc_id, content_hash=doc.content_hash,
                            doc_path=doc.path), []

    # 2. Edit: drop any prior version of this file before writing the new one.
    removed = _purge_prior_versions(doc, db, vector_store, before_delete=flush)

    # 3. Chunk + embed.
    chunks = chunker.chunk(doc)
    texts = [c.text for c in chunks]
    embeddings = embedder.embed(texts) if texts else []
    for i, chunk in enumerate(chunks):
        chunk.embedding = embeddings[i]

    # 4. Store metadata.
    db.upsert_document(doc, doc_id)
    db.add_chunks(chunks)

    # 5. Only a *forced* re-ingest can reach here with vectors already present for this
    #    doc_id: doc_id is a pure function of content_hash, and step 1 returns early
    #    otherwise, so a new or edited document always has a doc_id nobody has indexed.
    #    Deleting unconditionally cost ~44% of ingest wall time at 1,200 docs and grew
    #    with index size, because a LanceDB delete rewrites fragments.
    if force:
        if flush is not None:
            flush()  # never let a buffered write land after this delete
        vector_store.delete(doc_id)

    status = "updated" if removed else "ingested"
    return (
        IngestResult(
            status=status,
            doc_id=doc_id,
            content_hash=doc.content_hash,
            n_chunks=len(chunks),
            removed_chunks=removed,
            chunks=chunks,
            doc_path=doc.path,
        ),
        chunks,
    )


def ingest_document(doc, db, vector_store, embedder, chunker, *, force: bool = False) -> IngestResult:
    """Ingest one document deterministically.

    ``db``/``vector_store``/``embedder``/``chunker`` are injected so this is unit
    testable and shared by every caller. Returns an :class:`IngestResult`.

    Writes this document's vectors immediately. To ingest many documents, prefer
    :func:`ingest_documents`, which is materially faster at scale.
    """
    result, chunks = _ingest_core(doc, db, vector_store, embedder, chunker, force)
    if chunks:
        vector_store.add(chunks)
    return result


def ingest_documents(docs, db, vector_store, embedder, chunker, *, force: bool = False,
                     batch_chunks: int = 2000, on_result=None, on_error=None):
    """Ingest many documents, amortising vector writes across a batch.

    Identical semantics to :func:`ingest_document` — both share :func:`_ingest_core` —
    but vectors are written once per ``batch_chunks`` accumulated chunks instead of
    once per document. Each LanceDB append creates a new dataset version and its cost
    grows with the number already indexed, so per-document appends make ingestion
    degrade super-linearly; batching collapses that term.

    Vectors are always flushed before returning, including on error, so the store is
    never left behind the metadata.

    ``on_result`` is called with each :class:`IngestResult` as it completes, so callers
    can report progress without waiting for the whole batch.

    ``on_error``, if given, receives ``(doc, exception)`` and the run continues with the
    next document — one unreadable file should not abandon a directory. Without it,
    exceptions propagate.
    """
    pending: List[Chunk] = []

    def flush():
        if pending:
            vector_store.add(list(pending))
            pending.clear()

    results = []
    try:
        for doc in docs:
            try:
                result, chunks = _ingest_core(doc, db, vector_store, embedder, chunker, force,
                                              flush=flush)
            except Exception as exc:  # noqa: BLE001 - caller decides the policy
                if on_error is None:
                    raise
                on_error(doc, exc)
                continue
            pending.extend(chunks)
            results.append(result)
            if on_result is not None:
                on_result(result)
            if len(pending) >= batch_chunks:
                flush()
    finally:
        flush()
    return results


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
