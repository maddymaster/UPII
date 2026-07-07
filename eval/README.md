# UPII Retrieval Eval Harness

Internal, committed harness that measures the **current retrieval path**
(`SearchEngine` → `ContextRehydrator`, i.e. what `upii ask` uses) against a fixed,
labelled dataset. Built for the Phase 3 grant demonstration target:
**Recall@10 ≥ 0.85**.

## One command

```bash
./eval/run.sh
```

That rebuilds the labelled dataset from the corpus and runs the eval, writing
[`results/REPORT.md`](results/REPORT.md) and `results/results.json`. It exits
non-zero if Recall@10 is below the target, so it can gate CI.

Equivalently:

```bash
python eval/run_eval.py --rebuild
```

## Layout

```
eval/
  dataset/
    corpus/         fixed sample corpus (committed .md notes)
    queries.yaml    authored queries + human-editable relevance rules
    labels.json     generated, committed: query -> relevant chunk ids
  metrics.py        pure ranking metrics (Recall@k, MRR, nDCG@k) — dependency-free
  harness.py        index isolation, corpus ingest, label resolution, retrieval
  build_dataset.py  build / list-chunks / annotate
  run_eval.py       score labels -> results/REPORT.md
  run.sh            one-command entry point
  .index/           isolated SQLite+LanceDB (gitignored, rebuilt from corpus)
```

## How labels work

The unit of relevance is the **content-addressed chunk id** (`Chunk.chunk_hash`), a
pure function of the chunk text and chunker config — so labels are stable across
machines and re-runs.

You author queries in `dataset/queries.yaml` with a rule per relevant chunk:

```yaml
- id: q03_memory_leak_fix
  query: "Who fixed the memory leak in the file watcher?"
  relevant:
    - source: team_sync.md      # any chunk of this doc …
      contains: "memory leak"    # … whose text contains this substring
```

`build_dataset.py build` ingests the corpus deterministically, resolves those rules
to concrete chunk ids, and writes `dataset/labels.json`.

## Relevance-labelling by hand

To label interactively instead of by rules (review the retriever's candidates and
mark the relevant ones):

```bash
python eval/build_dataset.py annotate
```

Or dump every chunk id + preview to label manually:

```bash
python eval/build_dataset.py list-chunks
```

## Isolation

The harness ingests into `eval/.index/` (its own SQLite + LanceDB) and **never**
touches your real `upii.db` / `upii_vectors`.

## Metrics

`metrics.py` is import-safe and unit-tested in
[`tests/test_eval_harness.py`](../tests/test_eval_harness.py):

- **Recall@k** — fraction of relevant chunks retrieved in the top _k_ (k = 1, 5, 10)
- **MRR** — mean reciprocal rank of the first relevant chunk
- **nDCG@10** — rank-discounted, normalised gain (binary relevance)
