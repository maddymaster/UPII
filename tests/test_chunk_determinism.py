"""T1.2 — chunk hashes are a pure function of (file content, chunker config).

Ingesting the same corpus twice, and in shuffled file order, must yield identical
chunk hashes. (Pure loader + chunker; no DB / vector store needed.)
"""

import os
import random

from upii.ingestion.loader import LocalLoader
from upii.ingestion.chunker import RecursiveChunker
from upii.core.types import Document


def _write_corpus(root):
    """A small corpus whose every ~1KB window is distinct (so no hash collisions)."""
    files = {
        "a.md": "".join(f"[doc-a chunk {i:03d}] lorem ipsum dolor sit amet consectetur. " for i in range(60)),
        "b.txt": "".join(f"[doc-b chunk {i:03d}] the quick brown fox jumps over the lazy dog. " for i in range(60)),
        "sub/c.md": "".join(f"[doc-c chunk {i:03d}] sphinx of black quartz judge my vow. " for i in range(60)),
    }
    for rel, content in files.items():
        p = os.path.join(root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
    return [os.path.join(root, r) for r in files]


def _hashes_via_dir(root):
    loader, chunker = LocalLoader(), RecursiveChunker()
    out = {}
    for doc in loader.load(root):
        for c in chunker.chunk(doc):
            out[c.chunk_hash] = c.text
    return out


def _hashes_via_files(paths):
    """Chunk each file independently, unioning results — order-independent by design."""
    loader, chunker = LocalLoader(), RecursiveChunker()
    out = {}
    for p in paths:
        for doc in loader.load(p):
            for c in chunker.chunk(doc):
                out[c.chunk_hash] = c.text
    return out


def test_same_corpus_twice_identical_hashes(tmp_path):
    root = str(tmp_path)
    _write_corpus(root)
    first = _hashes_via_dir(root)
    second = _hashes_via_dir(root)
    assert first.keys() == second.keys()
    # And the text behind each hash is identical (no silent collisions).
    assert first == second
    assert len(first) > 0


def test_shuffled_file_order_identical_hashes(tmp_path):
    root = str(tmp_path)
    paths = _write_corpus(root)

    baseline = _hashes_via_dir(root)

    shuffled = list(paths)
    random.Random(1234).shuffle(shuffled)
    out_of_order = _hashes_via_files(shuffled)

    # The SET of chunk hashes is independent of traversal order.
    assert set(baseline.keys()) == set(out_of_order.keys())


def test_directory_walk_order_is_deterministic(tmp_path):
    """The loader yields files in a stable, sorted order regardless of FS ordering."""
    root = str(tmp_path)
    _write_corpus(root)
    loader = LocalLoader()
    order1 = [d.path for d in loader.load(root)]
    order2 = [d.path for d in loader.load(root)]
    assert order1 == order2
    assert order1 == sorted(order1)


def test_chunk_hash_is_pure_function_of_text_and_config():
    chunker = RecursiveChunker(chunk_size=50, overlap=10)
    doc = Document(path="/x", content_hash="anything", content="payload " * 40, created_at=None)

    h1 = [c.chunk_hash for c in chunker.chunk(doc)]
    # Same text, same config, but a DIFFERENT document content_hash => identical chunk ids.
    doc2 = Document(path="/y", content_hash="totally-different", content=doc.content, created_at=None)
    h2 = [c.chunk_hash for c in chunker.chunk(doc2)]
    assert h1 == h2

    # Different config (overlap) => different chunk ids.
    other = RecursiveChunker(chunk_size=50, overlap=25)
    h3 = [c.chunk_hash for c in other.chunk(doc)]
    assert h3 != h1
