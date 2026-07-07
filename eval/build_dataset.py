#!/usr/bin/env python3
"""Build (and optionally hand-annotate) the labelled retrieval eval dataset.

The dataset is ``(query -> relevant chunk ids)`` over the fixed corpus in
``eval/dataset/corpus/``. Because chunk ids are content-addressed, the labels are
deterministic: re-running ``build`` on the same corpus reproduces byte-identical
``labels.json``.

Subcommands
-----------
  build       Ingest the corpus deterministically, resolve the relevance rules in
              queries.yaml to concrete chunk ids, and write dataset/labels.json.
  list-chunks Print every corpus chunk (id, source, preview) — handy for authoring
              or eyeballing labels.
  annotate    Interactively relevance-label: for each query, run the current
              retriever, show the candidate chunks, and let you mark which are
              relevant. Writes the result into labels.json.

Typical use:
    python eval/build_dataset.py build          # regenerate the committed labels
    python eval/build_dataset.py annotate        # hand-label / refine
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# Ensure `import eval.*` works when invoked as a plain script.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eval import harness  # noqa: E402


def _preview(text: str, width: int = 90) -> str:
    flat = " ".join(text.split())
    return flat[:width] + ("…" if len(flat) > width else "")


def _write_labels(payload: dict) -> None:
    os.makedirs(harness.DATASET_DIR, exist_ok=True)
    with open(harness.LABELS_PATH, "w") as fh:
        json.dump(payload, fh, indent=2, sort_keys=False)
        fh.write("\n")


def cmd_build(args: argparse.Namespace) -> int:
    print(f"[build] ingesting corpus from {harness.CORPUS_DIR} into isolated index …")
    n_docs = harness.ingest_corpus(reset=True)
    chunks = harness.list_chunks()
    print(f"[build] ingested {n_docs} docs -> {len(chunks)} chunks")

    queries = harness.load_queries()
    labelled = []
    total_labels = 0
    for q in queries:
        rel_ids = harness.resolve_relevant_ids(q["relevant"], chunks)
        total_labels += len(rel_ids)
        labelled.append(
            {"id": q["id"], "query": q["query"], "relevant_chunk_ids": rel_ids}
        )
        print(f"  {q['id']}: {len(rel_ids)} relevant chunk(s)")

    payload = {
        "corpus_fingerprint": harness.corpus_fingerprint(),
        "n_docs": n_docs,
        "n_chunks": len(chunks),
        "chunker": {
            "size": _chunker_size(),
            "overlap": _chunker_overlap(),
        },
        "queries": labelled,
    }
    _write_labels(payload)
    print(
        f"[build] wrote {len(labelled)} labelled queries "
        f"({total_labels} query→chunk labels) to {harness.LABELS_PATH}"
    )
    return 0


def _chunker_size() -> int:
    from upii.core.config import config

    return config.chunk_size


def _chunker_overlap() -> int:
    from upii.core.config import config

    return config.chunk_overlap


def cmd_list_chunks(args: argparse.Namespace) -> int:
    harness.ingest_corpus(reset=True)
    chunks = harness.list_chunks()
    print(f"{len(chunks)} chunks in corpus:\n")
    for c in chunks:
        print(f"  {c.chunk_id[:12]}  {c.source:<28} [{c.index}]  {_preview(c.text, 60)}")
    return 0


def cmd_annotate(args: argparse.Namespace) -> int:
    """Interactive relevance labelling on top of the current retriever's candidates."""
    print("[annotate] ingesting corpus …")
    harness.ingest_corpus(reset=True)
    chunks = harness.list_chunks()
    by_id = {c.chunk_id: c for c in chunks}

    # Seed from existing labels (rules or a prior annotation) so this refines.
    existing = {}
    if os.path.exists(harness.LABELS_PATH):
        with open(harness.LABELS_PATH) as fh:
            for q in json.load(fh).get("queries", []):
                existing[q["id"]] = set(q.get("relevant_chunk_ids", []))

    queries = harness.load_queries()
    labelled = []
    print(
        "\nFor each query, the retriever's top candidates are shown.\n"
        "Enter the numbers of the RELEVANT ones (comma-separated), blank to keep the\n"
        "current labels, or 'q' to stop and save what you have.\n"
    )
    stopped = False
    for q in queries:
        if stopped:
            labelled.append(
                {"id": q["id"], "query": q["query"],
                 "relevant_chunk_ids": sorted(existing.get(q["id"], []))}
            )
            continue

        cands = harness.retrieve(q["query"], limit=args.candidates)
        current = existing.get(q["id"], set())
        print(f"\n── {q['id']}: {q['query']}")
        for i, cid in enumerate(cands):
            c = by_id.get(cid)
            mark = "*" if cid in current else " "
            src = c.source if c else "?"
            print(f"  [{i}]{mark} {src:<26} {_preview(c.text if c else '', 60)}")
        raw = input("relevant #s > ").strip()

        if raw.lower() == "q":
            stopped = True
            chosen = current
        elif raw == "":
            chosen = current
        else:
            chosen = set()
            for tok in raw.split(","):
                tok = tok.strip()
                if tok.isdigit() and int(tok) < len(cands):
                    chosen.add(cands[int(tok)])
        labelled.append(
            {"id": q["id"], "query": q["query"], "relevant_chunk_ids": sorted(chosen)}
        )

    payload = {
        "corpus_fingerprint": harness.corpus_fingerprint(),
        "n_docs": len({c.doc_id for c in chunks}),
        "n_chunks": len(chunks),
        "chunker": {"size": _chunker_size(), "overlap": _chunker_overlap()},
        "queries": labelled,
    }
    _write_labels(payload)
    print(f"\n[annotate] saved {len(labelled)} labelled queries to {harness.LABELS_PATH}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("build", help="ingest corpus + resolve rules -> labels.json")
    sub.add_parser("list-chunks", help="print all corpus chunks")
    ann = sub.add_parser("annotate", help="interactively relevance-label")
    ann.add_argument("--candidates", type=int, default=10, help="candidates to show per query")

    args = p.parse_args(argv)
    cmd = args.cmd or "build"  # default action is a deterministic build
    return {"build": cmd_build, "list-chunks": cmd_list_chunks, "annotate": cmd_annotate}[cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
