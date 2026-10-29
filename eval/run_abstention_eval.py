#!/usr/bin/env python3
"""Calibrate and check ``rag_min_similarity`` (answer abstention).

Two corpora, absolute cosine similarity of the best match per question:

1. The eval corpus: every labelled retrieval query (has an answer) should pass the
   threshold; every question in UNRELATED (has none) should fall below it.
2. The demo corpora (``demo_dataset/`` + ``demo_data_v2/``): every question the demo
   scripts and runbooks ask must pass, so the threshold can never make a live demo
   answer "not found". Unrelated questions on this corpus are reported, not gated:
   relevant and unrelated scores overlap here, and that grey zone is left to the
   model's NOT_FOUND flag.

Also checks that the rehydrator's ``cos = 1 - d/2`` conversion of LanceDB's
squared-L2 distance matches numpy cosine.

Writes ``results/abstention_REPORT.md`` and ``results/abstention_results.json``.
Exit code is non-zero if a gated check fails.

Usage:
    python eval/run_abstention_eval.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eval import harness  # noqa: E402

# Questions with no answer anywhere in the corpus: general knowledge and chit-chat.
UNRELATED = [
    "What is the capital of France?",
    "How do I bake sourdough bread?",
    "Who won the 1998 football world cup?",
    "What is the boiling point of mercury?",
    "Recommend a good sci-fi novel",
    "How tall is Mount Everest?",
    "What's the weather in Mumbai tomorrow?",
    "Translate hello into Japanese",
]

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO_DIRS = [os.path.join(REPO, "demo_dataset"), os.path.join(REPO, "demo_data_v2")]
# Questions the demo scripts and runbooks ask (scripts/demo, docs).
DEMO_QUESTIONS = [
    "What is blocking Project Firewatch?",
    "What did we agree with ICEYE on latency and image resolution?",
    "What did we agree with ICEYE on resolution and latency?",
    "What did we agree with ICEYE on?",
    "What is the Q3 budget?",
    "What is the budget?",
    "What is the status of Project Omega?",
    "Project Omega blocker",
]
DEMO_UNRELATED = UNRELATED + [
    "Who is the prime minister of India?",
    "What is photosynthesis?",
    "What is 17 times 23?",
]


def demo_scores(to_cos):
    """Best-match cosine for demo questions over a throwaway index of the demo data."""
    import tempfile

    from upii.analysis.embeddings import Embedder
    from upii.core.config import config
    from upii.ingestion.chunker import RecursiveChunker
    from upii.ingestion.loader import LocalLoader
    from upii.ingestion.pipeline import ingest_documents
    from upii.storage.db import DB
    from upii.storage.vector import LocalVectorStore

    saved = (config.db_path, config.vector_store_path)
    with tempfile.TemporaryDirectory() as tmp:
        config.db_path = os.path.join(tmp, "demo.db")
        config.vector_store_path = os.path.join(tmp, "demo_vectors")
        try:
            db, store = DB(), LocalVectorStore()
            db.init_db()
            for d in DEMO_DIRS:
                ingest_documents(LocalLoader().load(d), db, store, Embedder(), RecursiveChunker(),
                                 on_error=lambda doc, exc: None)
            model = Embedder.get_instance()

            def best(q):
                return round(to_cos(store.search_scored(model.encode(q).tolist(), limit=1)[0]["distance"]), 4)

            return ([{"question": q, "top_cosine": best(q)} for q in DEMO_QUESTIONS],
                    [{"question": q, "top_cosine": best(q)} for q in DEMO_UNRELATED])
        finally:
            config.db_path, config.vector_store_path = saved


def main() -> int:
    harness.use_isolated_index()
    harness.ingest_corpus(reset=True)

    import numpy as np

    from upii.analysis.embeddings import Embedder
    from upii.analysis.rehydration import ContextRehydrator
    from upii.core.config import config
    from upii.storage.vector import LocalVectorStore

    model, store = Embedder.get_instance(), LocalVectorStore()
    threshold = float(config.rag_min_similarity)
    to_cos = ContextRehydrator._distance_to_cosine

    def hits(question):
        qv = model.encode(question)
        return qv, store.search_scored(qv.tolist(), limit=200)

    # 1. The distance -> cosine conversion the threshold relies on.
    qv, top = hits(UNRELATED[0])
    cv = model.encode(top[0]["chunk"].text)
    numpy_cos = float(np.dot(qv, cv) / (np.linalg.norm(qv) * np.linalg.norm(cv)))
    conversion_error = abs(to_cos(top[0]["distance"]) - numpy_cos)

    # 2. Labelled queries (should answer) and unrelated questions (should abstain).
    labels = json.load(open(harness.LABELS_PATH))["queries"]
    answerable = []
    for q in labels:
        _, h = hits(q["query"])
        relevant = set(q["relevant_chunk_ids"])
        answerable.append({
            "id": q["id"],
            "top_cosine": round(to_cos(h[0]["distance"]), 4),
            "best_relevant_cosine": round(max(to_cos(x["distance"]) for x in h
                                              if x["chunk"].chunk_hash in relevant), 4),
        })
    unrelated = [{"question": q, "top_cosine": round(to_cos(hits(q)[1][0]["distance"]), 4)}
                 for q in UNRELATED]

    demo, demo_unrelated = demo_scores(to_cos)
    demo_passed = sum(d["top_cosine"] >= threshold for d in demo)
    demo_abstained = sum(u["top_cosine"] < threshold for u in demo_unrelated)

    answered = sum(a["best_relevant_cosine"] >= threshold for a in answerable)
    abstained = sum(u["top_cosine"] < threshold for u in unrelated)
    lowest_relevant = min(a["best_relevant_cosine"] for a in answerable)
    highest_unrelated = max(u["top_cosine"] for u in unrelated)

    results = {
        "rag_min_similarity": threshold,
        "embedding_model": config.embedding_model,
        "corpus_fingerprint": harness.corpus_fingerprint(),
        "conversion_abs_error": conversion_error,
        "answerable": answerable,
        "unrelated": unrelated,
        "answered": answered,
        "abstained": abstained,
        "lowest_relevant_cosine": lowest_relevant,
        "highest_unrelated_cosine": highest_unrelated,
        "demo": demo,
        "demo_unrelated": demo_unrelated,
        "demo_passed": demo_passed,
        "demo_unrelated_abstained": demo_abstained,
    }

    lines = [
        "# Abstention calibration — `rag_min_similarity`",
        "",
        "Generated by `python eval/run_abstention_eval.py`. Absolute cosine similarity",
        "of the best match per question, against the threshold answer paths apply.",
        "",
        f"- Threshold (`rag_min_similarity`): **{threshold:.2f}** (cosine)",
        f"- Embedding model: `{config.embedding_model}`; corpus fingerprint `{results['corpus_fingerprint'][:16]}`",
        f"- Labelled queries whose relevant passage passes: **{answered}/{len(answerable)}**",
        f"- Unrelated questions that abstain: **{abstained}/{len(unrelated)}**",
        f"- Lowest relevant passage: {lowest_relevant:.3f}; highest unrelated top match: {highest_unrelated:.3f}",
        f"- Demo-script questions that pass (gated): **{demo_passed}/{len(demo)}** "
        f"(lowest {min(d['top_cosine'] for d in demo):.3f})",
        f"- Unrelated questions on the demo corpus that abstain at retrieval (reported, not gated): "
        f"{demo_abstained}/{len(demo_unrelated)}; the rest reach the model, which can reply NOT_FOUND",
        f"- `cos = 1 - d/2` vs numpy cosine, absolute error: {conversion_error:.2e}",
        "",
        "## Labelled queries (should answer)",
        "",
        "| Query | Top match | Best relevant passage | Passes |",
        "|---|---|---|---|",
    ]
    lines += [f"| `{a['id']}` | {a['top_cosine']:.3f} | {a['best_relevant_cosine']:.3f} | "
              f"{'yes' if a['best_relevant_cosine'] >= threshold else '**no**'} |" for a in answerable]
    lines += ["", "## Unrelated questions (should abstain)", "",
              "| Question | Top match | Abstains |", "|---|---|---|"]
    lines += [f"| {u['question']} | {u['top_cosine']:.3f} | "
              f"{'yes' if u['top_cosine'] < threshold else '**no**'} |" for u in unrelated]
    lines += ["", "## Demo-script questions on demo data (must pass)", "",
              "| Question | Top match | Passes |", "|---|---|---|"]
    lines += [f"| {d['question']} | {d['top_cosine']:.3f} | "
              f"{'yes' if d['top_cosine'] >= threshold else '**no**'} |" for d in demo]
    lines += ["", "## Unrelated questions on demo data (reported)", "",
              "| Question | Top match | Abstains at retrieval |", "|---|---|---|"]
    lines += [f"| {u['question']} | {u['top_cosine']:.3f} | "
              f"{'yes' if u['top_cosine'] < threshold else 'no (model decides)'} |" for u in demo_unrelated]

    os.makedirs(harness.RESULTS_DIR, exist_ok=True)
    with open(os.path.join(harness.RESULTS_DIR, "abstention_REPORT.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    with open(os.path.join(harness.RESULTS_DIR, "abstention_results.json"), "w") as f:
        json.dump(results, f, indent=2, sort_keys=True)
        f.write("\n")

    print(f"threshold {threshold:.2f}: answered {answered}/{len(answerable)}, "
          f"abstained {abstained}/{len(unrelated)} "
          f"(lowest relevant {lowest_relevant:.3f}, highest unrelated {highest_unrelated:.3f}); "
          f"demo questions pass {demo_passed}/{len(demo)}, demo unrelated abstain {demo_abstained}/{len(demo_unrelated)}")
    ok = (answered == len(answerable) and abstained == len(unrelated) and demo_passed == len(demo)
          and conversion_error < 1e-4)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
