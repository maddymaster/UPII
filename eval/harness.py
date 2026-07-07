"""Shared plumbing for the retrieval eval harness.

Everything that both ``build_dataset.py`` and ``run_eval.py`` need lives here:

* **index isolation** — the eval ingests into its own SQLite + LanceDB under
  ``eval/.index/`` so it never touches the user's real ``upii.db`` / ``upii_vectors``.
* **deterministic corpus ingest** — reuses the exact production ingest path
  (``LocalLoader`` -> ``ingest_document``), so we measure the real retrieval stack.
* **label resolution** — turns the human-authored ``queries.yaml`` relevance rules
  into concrete, content-addressed chunk ids.
* **retrieval** — runs a query through the current retrieval path and returns the
  ranked chunk ids.

The chunk id used throughout is ``Chunk.chunk_hash`` (a sha256 of the chunk text +
chunker config). It is a pure function of the corpus, so labels are stable across
machines and re-runs.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional

import yaml

# --- Make the repo importable whether run as `python eval/xxx.py` or `-m eval.xxx`.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, os.path.join(_ROOT, "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# --- Paths (all eval artifacts live under eval/). -----------------------------
EVAL_DIR = _HERE
DATASET_DIR = os.path.join(EVAL_DIR, "dataset")
CORPUS_DIR = os.path.join(DATASET_DIR, "corpus")
QUERIES_PATH = os.path.join(DATASET_DIR, "queries.yaml")
LABELS_PATH = os.path.join(DATASET_DIR, "labels.json")
RESULTS_DIR = os.path.join(EVAL_DIR, "results")
INDEX_DIR = os.path.join(EVAL_DIR, ".index")  # gitignored; rebuilt from corpus
INDEX_DB_PATH = os.path.join(INDEX_DIR, "eval.db")
INDEX_VECTOR_PATH = os.path.join(INDEX_DIR, "eval_vectors")


def use_isolated_index() -> None:
    """Repoint the global config at the eval-only index.

    Must be called before any DB / vector store / retrieval object is constructed,
    because those read ``config.db_path`` / ``config.vector_store_path`` at init.
    Idempotent.
    """
    from upii.core.config import config

    os.makedirs(INDEX_DIR, exist_ok=True)
    config.db_path = INDEX_DB_PATH
    config.vector_store_path = INDEX_VECTOR_PATH


# --- Corpus fingerprint -------------------------------------------------------
def corpus_files() -> List[str]:
    """Corpus filenames (basenames), sorted for determinism."""
    return sorted(
        f
        for f in os.listdir(CORPUS_DIR)
        if os.path.splitext(f)[1].lower() in (".md", ".txt")
    )


def corpus_fingerprint() -> str:
    """Stable hash of the corpus (names + bytes).

    Stored in labels.json so run_eval can detect that the corpus drifted from the
    one the labels were built against.
    """
    h = hashlib.sha256()
    for name in corpus_files():
        with open(os.path.join(CORPUS_DIR, name), "rb") as fh:
            data = fh.read()
        h.update(name.encode("utf-8"))
        h.update(b"\0")
        h.update(data)
        h.update(b"\0")
    return h.hexdigest()


# --- Ingestion ----------------------------------------------------------------
def reset_index() -> None:
    """Delete the eval index so ingestion starts from a clean, reproducible state."""
    if os.path.isdir(INDEX_DIR):
        shutil.rmtree(INDEX_DIR)
    os.makedirs(INDEX_DIR, exist_ok=True)


def ingest_corpus(reset: bool = True) -> int:
    """Ingest the fixed corpus into the isolated index via the production path.

    Returns the number of documents ingested. Deterministic: same corpus + same
    chunker config -> identical chunk ids and vectors every run.
    """
    use_isolated_index()
    if reset:
        reset_index()

    from upii.analysis.embeddings import Embedder
    from upii.ingestion.chunker import RecursiveChunker
    from upii.ingestion.loader import LocalLoader
    from upii.ingestion.pipeline import ingest_document
    from upii.storage.db import DB
    from upii.storage.vector import LocalVectorStore

    db = DB()
    db.init_db()
    vector_store = LocalVectorStore()
    loader = LocalLoader()
    chunker = RecursiveChunker()
    embedder = Embedder()

    n_docs = 0
    # Load the corpus directory (LocalLoader walks it deterministically, sorted).
    for doc in loader.load(CORPUS_DIR):
        ingest_document(doc, db, vector_store, embedder, chunker, force=True)
        n_docs += 1
    return n_docs


# --- Chunk introspection ------------------------------------------------------
@dataclass
class ChunkRow:
    chunk_id: str
    doc_id: str
    source: str  # corpus basename
    index: int
    text: str


def list_chunks() -> List[ChunkRow]:
    """Return every chunk in the isolated index, joined to its corpus filename."""
    use_isolated_index()
    conn = sqlite3.connect(INDEX_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT c.chunk_id, c.doc_id, c.chunk_index, c.text, d.source_path
            FROM chunks c
            JOIN documents d ON c.doc_id = d.doc_id
            ORDER BY d.source_path, c.chunk_index
            """
        ).fetchall()
    finally:
        conn.close()
    return [
        ChunkRow(
            chunk_id=r["chunk_id"],
            doc_id=r["doc_id"],
            source=os.path.basename(r["source_path"]),
            index=r["chunk_index"],
            text=r["text"],
        )
        for r in rows
    ]


# --- Queries + label resolution ----------------------------------------------
def load_queries() -> List[dict]:
    """Load the authored queries (list of {id, query, relevant:[...]})"""
    with open(QUERIES_PATH, "r") as fh:
        data = yaml.safe_load(fh) or {}
    queries = data.get("queries", [])
    if not queries:
        raise ValueError(f"No queries found in {QUERIES_PATH}")
    return queries


def resolve_relevant_ids(rules: List[dict], chunks: List[ChunkRow]) -> List[str]:
    """Resolve a query's relevance rules to concrete chunk ids.

    Each rule is ``{source: <basename>, contains?: <substring>}``. A chunk matches
    when its source file equals ``source`` and (if given) its text contains
    ``contains``. Raises if a rule matches nothing — that means the corpus/query
    drifted and the label would silently be empty.
    """
    resolved: List[str] = []
    for rule in rules:
        source = rule.get("source")
        needle = rule.get("contains")
        if not source:
            raise ValueError(f"relevance rule missing 'source': {rule}")
        matched = [
            c
            for c in chunks
            if c.source == source and (needle is None or needle in c.text)
        ]
        if not matched:
            raise ValueError(
                f"relevance rule matched no chunk: {rule} "
                f"(source not ingested, or 'contains' substring not present)"
            )
        for c in matched:
            if c.chunk_id not in resolved:
                resolved.append(c.chunk_id)
    return resolved


# --- Retrieval ----------------------------------------------------------------
def retrieve(query: str, limit: int = 10) -> List[str]:
    """Run ``query`` through the current retrieval path; return ranked chunk ids.

    This is exactly what ``upii ask`` / ``upii search`` call, so the eval measures
    the live stack (semantic + temporal + relational fusion in the rehydrator).
    """
    use_isolated_index()
    from upii.analysis.search import SearchEngine

    results = SearchEngine().search(query, limit=limit)
    from eval.metrics import dedup_preserve_order

    return dedup_preserve_order(r.chunk_hash for r in results)
