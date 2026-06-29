# UPII — Unified Personal Intelligence Interface

**A local-first, privacy-preserving memory substrate for the human knowledge worker.**

UPII is a research effort toward *sovereign memory*: a system that captures the
fragments of your digital life — documents, notes, calendar, mail — and turns
them into an addressable, queryable, reasoning-capable extension of your own
recall. The scientific premise is simple to state and hard to deliver:
**personal AI should not require surrendering personal data.** UPII keeps the
entire memory loop — capture, embedding, retrieval, and reasoning — on your
machine, treating the cloud LLM as an optional, swappable accelerator rather
than a dependency.

---

## The Research Thesis

Mainstream "second brain" and RAG products externalize your corpus to a
provider, embed it remotely, and rent the reasoning back to you. UPII inverts
this. It asks: *what is the minimum architecture that delivers cloud-grade
recall and synthesis while the substrate never leaves the edge?*

Three properties define the answer we are pursuing:

1. **Sovereignty by construction.** Embeddings are computed locally
   (`sentence-transformers`, MiniLM-class models); vectors live in an on-disk
   store (LanceDB); metadata is a local SQLite source of truth. No corpus byte
   is required to leave the device for the system to function.
2. **Verifiable memory.** Every answer is traceable to its source chunks via
   content-addressed identifiers. Retrieval is *attributed*, not just
   plausible — the system cites where a fact came from.
3. **Graceful degradation.** Reasoning is pluggable: a local model (Ollama) or
   an optional remote model (Gemini). If inference is unavailable, the
   retrieval substrate still answers; the system never hard-fails on a missing
   GPU or an expired API key.

---

## Innovation Highlights

### Content-addressed, deduplicating ingestion
Documents are hashed on content, not path. Re-ingesting an unchanged file is a
no-op; an edited file is diffed at the chunk level. This makes the corpus
**idempotent and reproducible** — the same inputs always yield the same memory
state — which is a precondition for trustworthy personal recall.

### Deterministic chunking
Chunk boundaries **and chunk hashes** are a pure function of `(chunk text,
chunker config)` — not of ingestion order, document path, or wall-clock time.
The same content always produces the same chunk id, so an edit elsewhere in a
file leaves an untouched chunk's hash stable, and an independent re-ingest of
the same corpus reproduces **100% of chunk hashes**. This is what makes
citations stable and re-embedding cache-safe. (See
[`docs/phase2_reproducibility_audit.md`](docs/phase2_reproducibility_audit.md)
and [`docs/phase2_deliverables.md`](docs/phase2_deliverables.md).)

### Multi-signal context rehydration
The core retrieval innovation is the **Context Rehydrator**, which fuses three
orthogonal signals into a single ranked context window:

- **Semantic** — dense vector similarity over local embeddings.
- **Temporal** — calendar- and recency-aware weighting ("what was I working on
  last week").
- **Relational** — a lightweight personal **knowledge graph** built from
  rule-based entity extraction (projects, people, organizations).

Rather than ranking on cosine distance alone, UPII treats recall as a
*sensor-fusion* problem — combining what is semantically close, what is
temporally relevant, and what is relationally connected.

### Ambient capture
A robust filesystem watcher continuously ingests approved directories with
debouncing, deduplication, and delete-handling, so the memory substrate stays
current without manual re-indexing. Capture is **consent-gated**: sources are
explicitly enabled, and ambient events route through an approval inbox before
entering durable memory.

### Attributed synthesis
The RAG layer answers in the user's own voice and **cites its sources** by
chunk ID, keeping generated answers anchored to verifiable memory instead of
free-floating model output.

---

## Architecture

```mermaid
graph TD
    User[User / Ambient Sources] -->|ingest| IngestionEngine
    User -->|ask / search| Rehydrator

    subgraph "Core System — Local Only"
        IngestionEngine -->|hash + dedup| MetadataStore[(SQLite — source of truth)]
        IngestionEngine -->|deterministic chunking| Chunker
        Chunker -->|local embeddings| Embedder
        Embedder -->|store vectors| VectorStore[(LanceDB)]

        Rehydrator -->|semantic| VectorStore
        Rehydrator -->|temporal + relational| MetadataStore
        Rehydrator -->|fused context| LLM[LLM — local Ollama or optional Gemini]
        LLM -->|attributed answer| User
    end
```

| Layer | Responsibility | Technology |
|-------|----------------|------------|
| Capture | Ingest, dedup, ambient watch | content hashing, FS watcher |
| **Ingestion pipeline** | **One deterministic ingest/remove path: dedup · edit cleanup · delete** | **`ingestion/pipeline.py` + `ingestion/identity.py`** |
| Storage | Metadata source of truth | SQLite |
| Vectors | Semantic index | LanceDB |
| Embeddings | Local vectorization | sentence-transformers (MiniLM) |
| Knowledge | Entity / relation extraction | rule-based extractor |
| Retrieval | Multi-signal rehydration | semantic + temporal + relational fusion |
| Reasoning | Attributed synthesis | Ollama (local) / Gemini (optional) |
| Observability | Health checks, metrics | `doctor`, `metrics` |

### The ingestion pipeline (Phase 2 / T1.2)

Every path that writes to long-term memory — the `ingest` command, the
`watch`-approve flow, and the demo seed — now flows through a **single
deterministic pipeline** (`src/upii/ingestion/pipeline.py`), so the dedup / edit
/ delete semantics are defined once and cannot drift:

- **Identity is content-addressed.** `doc_id = doc_id_for(content_hash)` and
  `chunk_id = hash(chunk_text, config)` — both pure functions, no random UUIDs.
- **Dedup** — re-ingesting unchanged bytes is a no-op.
- **Edit** — a changed file keeps its path but gets a new content hash; the prior
  version's chunks + vectors + metadata are purged before the new one is written.
- **Delete** — `remove_document` cleans chunks, vectors and metadata together.

```
file ──► loader (sorted walk) ──► ingest_document(doc)
                                     │  doc_id = doc_id_for(content_hash)
                                     ├─ already stored & unchanged?  ─► no-op (dedup)
                                     ├─ prior version at this path?  ─► purge it (edit)
                                     └─ chunk ─► embed ─► upsert(SQLite) + (re)add(LanceDB)
```

---

## Setup

UPII targets **Python 3.9+**. A virtual environment named `venv/` is the
expected workflow in this repo.

```bash
# 1. Create and activate the environment
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 2. Install dependencies (+ the upii CLI entry point)
pip install -r requirements.txt
pip install -e .                  # exposes the `upii` command

# 3. Verify the local stack
upii doctor                       # checks db, vectors, embedding model, disk
```

First run downloads the local embedding model (`all-MiniLM-L6-v2`, ~90 MB) and,
if you use local reasoning, requires [Ollama](https://ollama.com) with a pulled
model (e.g. `ollama pull llama3.2`). Neither the corpus nor embeddings ever
leave the machine.

### Run the tests

```bash
source venv/bin/activate
pytest tests/ -q                  # full suite
pytest tests/test_chunk_determinism.py tests/test_incremental.py -q   # Phase 2 / T1.2 evidence
```

> Note: there is no `Makefile` in this repo — run the commands and scripts
> directly as shown.

### Optional: remote reasoning
By default UPII runs fully locally. To use Gemini as the reasoning engine,
provide a key via environment variable (never commit it):

```bash
export GEMINI_API_KEY="your-key"   # renew at https://aistudio.google.com/apikey
```

With no key set, UPII uses a local model (Ollama) and falls back to a
deterministic mock if no model is reachable — so the system always responds.

---

## Usage

```bash
upii doctor                       # verify the local stack (db, vectors, model, disk)
upii ingest ./notes --recursive   # build memory from a directory
upii search "satellite latency"   # semantic + attributed retrieval
upii ask "What did we agree with ICEYE on resolution and latency?"
upii write "follow-up" --target email   # synthesize in your voice
upii watch ./inbox                # ambient capture
upii sources list                 # manage consent-gated sources
upii metrics show                 # observability
```

Run `upii --help` (or `python -m upii.cli --help`) for the full command set.

### Reproducibility & benchmarks

```bash
# Recordable demo: ingest, then re-ingest to an identical state (deterministic)
bash scripts/demo/repro_demo.sh

# Scale + 100%-hash-reproducibility report -> bench/results/scale_REPORT.md
python scripts/bench/scale_check.py --docs 500 --paras 60
#   grant/hardware run (~1,000,000 chunks):
#   python scripts/bench/scale_check.py --docs 20000
```

---

## Repository layout

```
src/upii/
├── cli.py                 # Typer CLI: ingest, search, ask, write, watch, inbox, doctor, …
├── core/                  # config, types, logging, feature flags, errors
├── ingestion/
│   ├── loader.py          # file loading + hashing, deterministic sorted walk
│   ├── chunker.py         # content-addressed deterministic chunking
│   ├── identity.py        # doc_id_for() — deterministic document ids   (Phase 2)
│   └── pipeline.py        # single ingest/remove path: dedup·edit·delete (Phase 2)
├── storage/
│   ├── db.py              # SQLite metadata store (source of truth)
│   └── vector.py          # LanceDB vector store
├── analysis/              # embeddings, search, rehydration, entity extraction, llm, metrics
├── ambient/               # filesystem watcher, staging DB, approval inbox, connectors
└── overlay/               # Cmd+Shift+K capture overlay daemon

tests/                     # pytest suite (incl. test_chunk_determinism, test_incremental)
scripts/
├── bench/scale_check.py   # scale + reproducibility harness  -> bench/results/
└── demo/repro_demo.sh     # recordable re-ingestion demo
docs/                      # design blueprint, data model, audits, deliverables
project_docs/              # extended internal design / QA / release docs
ELEVATE_Nxt_Grant/         # grant milestone build plan
```

Key documents:
- [`docs/phase2_reproducibility_audit.md`](docs/phase2_reproducibility_audit.md) — non-determinism audit + fixes (T1.2).
- [`docs/phase2_deliverables.md`](docs/phase2_deliverables.md) — Phase 2 deliverables, features and metrics vs. grant.
- [`docs/design_blueprint_v1.md`](docs/design_blueprint_v1.md) · [`docs/data_model.md`](docs/data_model.md) — architecture & schema.

---

## Status & Roadmap

UPII is a **private research preview**, developed against the ELEVATE NxT grant
milestones (Annexure-1).

- **Phase 1 / T1.1** — R&D infra + performance baseline *(benchmark harness; hardware run pending)*.
- **Phase 2 / T1.2** — Deterministic, reproducible, content-addressed ingestion: **delivered**
  (dedup · edit · delete validated; 100% hash reproducibility). See
  [`docs/phase2_deliverables.md`](docs/phase2_deliverables.md).
- **Next** — Context Rehydrator v2 retrieval eval (T1.3), local KG extraction + viz (T1.4),
  attributed synthesis + abstention (T2.2), and a user-facing `upii forget` to expose the
  Phase 2 delete capability.

Technical deep-dives live in [`project_docs/`](project_docs/) and
[`docs/`](docs/) — start with the design blueprint and data model.

---

## License

MIT © 2026 Maddy
