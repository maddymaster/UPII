# UPII Retrieval Eval — REPORT

**✅ PASS** — Recall@10 = 0.958 (target ≥ 0.85)

Scored 12 / 12 queries against the current retrieval path (semantic + temporal + relational fusion).

## Aggregate metrics

| Metric | Value |
| --- | --- |
| Recall@1 | 0.833 |
| Recall@5 | 0.958 |
| Recall@10 | 0.958 |
| MRR | 0.903 |
| nDCG@10 | 0.911 |

## Configuration

These numbers are a function of the config below, not the corpus alone. Change a fusion weight and the metrics move — so any number quoted from this report should be quoted with this snapshot.

| Setting | Value |
| --- | --- |
| Fusion weight — semantic | 1 |
| Fusion weight — temporal | 0.25 |
| Fusion weight — relational | 0.5 |
| Embedding model | `all-MiniLM-L6-v2` |
| Chunk size / overlap | 1000 / 200 |
| RAG min similarity | 0.5 |
| RAG max chunks | 5 |
| Config fingerprint | `ace9bad0c7d9d354…` |

## Per-query

| Query | R@1 | R@5 | R@10 | RR | nDCG@10 | 1st hit |
| --- | --- | --- | --- | --- | --- | --- |
| Which embedding model did we choose for Project Omega and why? | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1 |
| What is the p95 latency target for context retrieval? | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1 |
| Who fixed the memory leak in the file watcher? | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1 |
| How much money is budgeted for the team offsite? | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1 |
| Which vector database do we use locally? | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1 |
| What caused the duplicate vectors bug on re-ingest and how was it fixed? | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1 |
| What are the top priorities on the Q3 roadmap? | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1 |
| Does UPII upload my documents to the cloud? | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1 |
| What are our retrieval performance targets and where did they break? | 0.00 | 0.50 | 0.50 | 0.33 | 0.31 | 3 |
| Who is the onboarding buddy for the new hire? | 0.00 | 1.00 | 1.00 | 0.50 | 0.63 | 2 |
| How large does the index get as the corpus grows? | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1 |
| How is UPII different from cloud-first note apps? | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1 |

_Corpus fingerprint: `871357277e24bce6…` — regenerate labels with `python eval/build_dataset.py build`._
