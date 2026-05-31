# UPII v0.5 Technical Blueprint

## 1. Architecture Diagram

```mermaid
graph TD
    User[User via CLI] -->|ingest| IngestionEngine
    User -->|search/ask| SearchEngine

    subgraph "Core System (Local Only)"
        IngestionEngine -->|1. Load & Hash| FileProcessor
        FileProcessor -->|2. Deterministic Chunking| Chunker
        Chunker -->|3. Dedup Check| MetadataStore[(SQLite Metadata)]
        Chunker -->|4. Embed (Local)| Embedder
        Embedder -->|5. Store| VectorStore[(Vector Store)]
        
        SearchEngine -->|1. Query Embed| Embedder
        SearchEngine -->|2. Similarity Search| VectorStore
        SearchEngine -->|3. Filter/Attribution| MetadataStore
        SearchEngine -->|4. Answer Synthesis| LocalLLM[Local LLM (Optional)]
    end
    
    style User fill:#f9f,stroke:#333
    style IngestionEngine fill:#ccf,stroke:#333
    style SearchEngine fill:#ccf,stroke:#333
```

## 2. Repo Structure

```text
upii-v0.5/
├── README.md
├── requirements.txt
├── pyproject.toml
├── upii.db              # Default SQLite DB (runtime)
├── .upii_config.yaml    # Config file
├── src/
│   └── upii/
│       ├── __init__.py
│       ├── cli.py       # Entry point (Click/Typer)
│       ├── config.py    # Settings management
│       ├── core/
│       │   ├── __init__.py
│       │   ├── types.py # Pydantic models & interfaces
│       │   ├── utils.py # Hashing, logging setup
│       │   └── errors.py
│       ├── ingestion/
│       │   ├── __init__.py
│       │   ├── loader.py    # PDF/TXT readers
│       │   └── chunker.py   # Deterministic chunking logic
│       ├── storage/
│       │   ├── __init__.py
│       │   ├── db.py        # SQLite interactions
│       │   └── vector.py    # Vector store link (e.g., Chroma/FAISS)
│       └── analysis/
│           ├── __init__.py
│           ├── search.py    # Algorithm for retrieval
│           └── llm.py       # Local LLM wrapper (stub)
└── tests/
    ├── __init__.py
    ├── test_ingest.py
    └── test_storage.py
```

## 3. Module Interfaces

```python
from typing import List, Optional, Generator, Protocol
from datetime import datetime
from dataclasses import dataclass
import numpy as np

@dataclass
class Document:
    path: str
    content_hash: str
    content: str
    created_at: datetime
    metadata: dict

@dataclass
class Chunk:
    doc_hash: str
    chunk_hash: str
    text: str
    embedding: Optional[List[float]]
    start_char: int
    end_char: int

class ILoader(Protocol):
    def load(self, path: str) -> Generator[Document, None, None]: ...

class IChunker(Protocol):
    def chunk(self, doc: Document) -> List[Chunk]: ...

class IVectorStore(Protocol):
    def add(self, chunks: List[Chunk]) -> None: ...
    def search(self, query_vec: List[float], limit: int = 5) -> List[Chunk]: ...
    def delete(self, doc_hash: str) -> None: ...

class IMetadataStore(Protocol):
    def exists(self, doc_hash: str) -> bool: ...
    def add_doc(self, doc: Document) -> None: ...
    def add_chunks(self, chunks: List[Chunk]) -> None: ...
    def get_chunks_by_hash(self, chunk_hashes: List[str]) -> List[Chunk]: ...

class ILocalLLM(Protocol):
    def generate(self, prompt: str, context: str) -> str: ...
```

## 4. Data Schemas (SQLite)

### Table: `documents`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `hash` | TEXT | PRIMARY KEY | SHA-256 of file content |
| `path` | TEXT | NOT NULL | Original file path |
| `source_type` | TEXT | NOT NULL | 'pdf', 'txt', 'md', 'note' |
| `ingested_at` | DATETIME | DEFAULT CURRENT_TIMESTAMP | |
| `last_modified`| DATETIME | | File mtime at ingestion |
| `metadata` | JSON | | Flexible attrs |

### Table: `chunks`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `hash` | TEXT | PRIMARY KEY | SHA-256 of chunk text |
| `doc_hash` | TEXT | FOREIGN KEY | Link to parent document |
| `index` | INTEGER | | Ordering within doc |
| `text` | TEXT | NOT NULL | The actual content |
| `vector_id` | TEXT | | External ID for vector store |
| `char_start` | INTEGER | | |
| `char_end` | INTEGER | | |

*Note: Vector data is abstracted. Ideally, SQLite handles metadata, and a specialized index (like ChromaDB or local persistent FAISS) handles vectors, linked by `hash` or `vector_id`.*

## 5. Error & Logging Strategy

- **Strategy**: Fail-safe ingestion. One bad file should not crash the batch.
- **Logging**:
    - `activity.log`: User-facing actions (e.g., "Ingested 5 files", "Search query: 'foo'").
    - `system.log`: Debug traces, stack traces for failed parsers.
- **Handling**:
    - `IngestionError`: Log path and reason, skip to next file.
    - `IntegrityError`: Check hashes before insert (idempotency). If hash exists, check path; update if path changed (move), ignore if duplicate.

## 6. Minimal CLI Spec

- `upii ingest <path> [--recursive]`: Hashes content. If new, chunks -> embeds -> stores. If exists, updates metadata. 
- `upii search "<query>" [--limit 5]`: Vector search + Keyword search fallback. Returns text snippets + source path.
- `upii ask "<question>"`: Retrieval augmented generation using local LLM (e.g., Llama via Ollama/GGUF). STRICTLY LOCAL. Fails if no local model found.
- `upii status`: Stats (Total docs, Total chunks, DB size, Last ingestion).
- `upii tasks`: View pending processing queues (if async) or simple "Idle" state for v0.5 sync implementation.

## 7. Non-Goals & Guardrails

- **No Remote Sync**: Code specific to generic syncing logic is banned.
- **No API Keys**: Do not require OpenAI/Claude keys. Local logic only.
- **No Background Daemons**: Execution happens *only* when the CLI is invoked. No `upii-server` running in background.
- **Dependency Guardrail**: Heavy deps (torch/transformers) must be optional or strictly managed. Prefer `llama.cpp` or `onnx` for light footprint.
