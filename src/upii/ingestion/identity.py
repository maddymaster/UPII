"""Deterministic identity for documents.

Reproducibility (Annexure-1 T1.2) requires that re-ingesting the identical corpus
converges to an identical store. The chunk hash is already content-addressed, but
the *document* id used to be a random ``uuid.uuid4()`` — so the chunk -> document
linkage (``chunks.doc_id`` / ``Chunk.doc_hash``) differed run to run.

``doc_id_for`` makes the document id a pure function of the content hash, so every
ingest of the same bytes produces the same ``doc_id`` and the same linkage. It also
removes the ``--force`` re-ingest bug where ``documents.doc_id`` and ``chunks.doc_id``
could diverge.
"""

import hashlib


def doc_id_for(content_hash: str) -> str:
    """Return a deterministic document id derived from the content hash.

    Pure function: identical ``content_hash`` always yields the same ``doc_id``.
    Namespaced so a document id is never accidentally equal to a chunk id even if
    a future chunk hash collided with a content hash.
    """
    return hashlib.sha256(f"doc:{content_hash}".encode("utf-8")).hexdigest()
