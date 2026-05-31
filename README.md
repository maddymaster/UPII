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
Chunk boundaries are a pure function of content and configuration, not of
ingestion order or wall-clock time. The same document always produces the same
chunk hashes, enabling stable citations and cache-safe re-embedding.

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
| Storage | Metadata source of truth | SQLite |
| Vectors | Semantic index | LanceDB |
| Embeddings | Local vectorization | sentence-transformers (MiniLM) |
| Knowledge | Entity / relation extraction | rule-based extractor |
| Retrieval | Multi-signal rehydration | semantic + temporal + relational fusion |
| Reasoning | Attributed synthesis | Ollama (local) / Gemini (optional) |
| Observability | Health checks, metrics | `doctor`, `metrics` |

---

## Installation

```bash
pip install -r requirements.txt
# or, as a package:
pip install -e .
```

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

---

## Status & Roadmap

UPII is a **private research preview**. The current substrate (local capture,
deduplication, deterministic chunking, multi-signal rehydration, attributed
synthesis) is functional; ongoing work focuses on richer relational extraction,
broader ambient sources (mail, calendar connectors), and tighter answer
verification.

Technical deep-dives live in [`project_docs/`](project_docs/) and
[`docs/`](docs/) — start with the design blueprint and data model.

---

## License

MIT © 2026 Maddy
