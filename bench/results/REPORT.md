# Phase 1 Benchmark — ingestion throughput & retrieval latency

**Run:** 2026-07-16 05:45 UTC

## Headline

| Metric | Measured | Target | Result |
|---|---|---|---|
| Ingestion throughput | **627 docs/min** | ≥ 500 docs/min | ✅ PASS |
| Retrieval latency (p50) | **40 ms** | < 300 ms | ✅ PASS |

> ⚠️ **Scale caveat — read before citing these numbers.** This run indexed **99,702 chunks**, below the **100,000-chunk** corpus the retrieval target is defined against. Retrieval latency grows with index size, so the p50 above is **not** the number the target asks for. Ingestion throughput is scale-sensitive too (see the curve below).

> **Note:** Baseline on an Apple M5 MacBook (10 cores, 16 GB) — NOT the procured Mac Studio. Run after batching vector writes (one LanceDB append per batch instead of per document).

## Machine

| | |
|---|---|
| CPU | Apple M5 (Mac17,2) |
| Cores | 10 |
| RAM | 16 GB |
| OS | macOS 26.2 (arm64) |
| Python | 3.9.6 |
| Embedding model | all-MiniLM-L6-v2 |

## Corpus

- Documents: **7,700**  |  Chunks: **99,702**  |  Paragraphs/doc: 60
- Corpus: `/Users/maddy/Documents/UPII-master/.phase1_demo/corpus` (deterministic, seed fixed by `make_corpus.py`)
- Ingest wall time: 736.7s  (135 chunks/s)

## Ingestion throughput vs. index size

`now` is the rate over the window since the previous checkpoint; `avg` is
cumulative. A falling `now` column means throughput degrades as the index
grows — which is the engineering finding, not the endpoint average.

| Docs ingested | Elapsed | Rate now (docs/min) | Rate avg (docs/min) | RSS |
|---|---|---|---|---|
| 250 | 19s | 801 | 801 | 206 MB |
| 500 | 41s | 682 | 737 | 129 MB |
| 750 | 62s | 692 | 721 | 203 MB |
| 1,000 | 95s | 457 | 630 | 102 MB |
| 1,250 | 123s | 546 | 611 | 254 MB |
| 1,500 | 147s | 615 | 612 | 210 MB |
| 1,750 | 170s | 659 | 618 | 184 MB |
| 2,000 | 197s | 555 | 610 | 182 MB |
| 2,250 | 223s | 569 | 605 | 165 MB |
| 2,500 | 243s | 757 | 617 | 267 MB |
| 2,750 | 260s | 893 | 635 | 444 MB |
| 3,000 | 276s | 902 | 651 | 237 MB |
| 3,250 | 293s | 903 | 665 | 210 MB |
| 3,500 | 314s | 720 | 669 | 278 MB |
| 3,750 | 336s | 674 | 669 | 242 MB |
| 4,000 | 359s | 659 | 669 | 249 MB |
| 4,250 | 377s | 842 | 677 | 276 MB |
| 4,500 | 395s | 817 | 683 | 261 MB |
| 4,750 | 420s | 607 | 679 | 112 MB |
| 5,000 | 444s | 627 | 676 | 188 MB |
| 5,250 | 466s | 689 | 677 | 232 MB |
| 5,500 | 487s | 711 | 678 | 127 MB |
| 5,750 | 520s | 444 | 663 | 254 MB |
| 6,000 | 540s | 761 | 667 | 150 MB |
| 6,250 | 560s | 751 | 670 | 181 MB |
| 6,500 | 602s | 358 | 648 | 71 MB |
| 6,750 | 637s | 433 | 636 | 184 MB |
| 7,000 | 660s | 652 | 637 | 253 MB |
| 7,250 | 681s | 689 | 638 | 146 MB |
| 7,500 | 715s | 446 | 629 | 132 MB |

## Retrieval

- Queries: **50** (one warm-up query excluded)  |  limit=10
- Path: `SearchEngine().search()` — the same call `upii ask` / `upii search` use

| Percentile | Latency |
|---|---|
| p50 (median) | **40 ms** |
| p95 | 68 ms |
| p99 | 228 ms |
| mean | 47 ms |
| min / max | 32 / 228 ms |

## Method

- Real stack throughout: the production ingest pipeline with the real
  SentenceTransformer (`all-MiniLM-L6-v2`), and the live fusion
  retrieval path — no mocks, no fake embedder.
- The embedding model is loaded before any timer starts, so the one-time
  model-load cost is excluded from throughput (it is a startup cost, not a
  per-document one).
- Ingestion writes vectors **once per document**   (`LocalVectorStore.add` -> `open_table` + `table.add` per doc), so each
  document appends a new LanceDB version. Both the per-append cost and
  resident memory grow with the number of documents already indexed; that is
  the mechanism behind any decay in the curve above.
- Reproduce with one command: `bash scripts/demo/phase1_demo.sh`
