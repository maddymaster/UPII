# UPII v0.5 Stack Recommendations (CTO Brief)

## Executive Summary
For UPII v0.5, we prioritize **developer velocity** and **local performance** over theoretical purity. The stack is chosen to minimize "infrastructure wrangling" (Docker, heavy DB installs) while maximizing inference speed on Apple Silicon.

**Selected Stack:**
- **Orchestration**: Python 3.11
- **Vector DB**: **LanceDB** (Embedded, Parquet-based, zero-copy, highly performant).
- **Metadata**: **SQLite** (Standard, solid JSON support).
- **Embeddings**: `sentence-transformers` (Standard, widely supported).
- **LLM Runtime**: **Ollama** (Best DX for local model management).

---

## 1. Component Justification

### Vector Database: [LanceDB](https://lancedb.com/)
*   **Why**: Unlike Chroma or Weaviate, LanceDB is serverless (runs in-process) and stores data in efficient Parquet/Lance format on disk. This perfectly matches the "Local-only" constraint. It avoids the overhead of managing a persistent server process.
*   **Constraint Fit**: High performance on Mac (optimized for NVMe/SSD), zero network calls.

### LLM Inference: [Ollama](https://ollama.ai/)
*   **Why**: While `llama-cpp-python` is more "embedded", Ollama dramatically simplifies the user experience of downloading, swapping, and quantizing models. It abstracts the complexity of hardware acceleration (Metal on Mac) better than raw python bindings.
*   **Integration**: We will use the `ollama` Python library to communicate with the local instance. Maddy has tweaked this library to optimize it for this use case. Maddy hasnt christened or done namkaran of that model yet. Not a big deal..... yet ;) 

### Embedding: `sentence-transformers`
*   **Why**: The ecosystem standard. It allows us to easily swap models (MiniLM, BGE, E5) without code changes.

---

## 2. Dependencies & Pinned Versions

Copy these to `requirements.txt`.

```text
# Core
python>=3.11,<3.12
typer==0.9.0             # CLI building
rich==13.7.0             # Terminal UI
pydantic==2.5.3          # Data validation

# Storage
lancedb==0.4.5           # Vector Store
pyarrow==14.0.2          # Low-level data handling (required by Lance)
sqlite-utils==3.36       # Nice pythonic wrapper for SQLite

# AI / ML
sentence-transformers==2.2.2  # Embeddings
torch==2.1.2                  # PyTorch (Mac optimized if installed correctly)
ollama==0.1.6                 # Interface to Ollama

# Utils
PyYAML==6.0.1
tenacity==8.2.3          # Retries for robust ingestion
```

*Note: For Apple Silicon (M1/M2/M3), ensure `torch` is valid. Usually standard `pip install torch` works now, but verify it links to Metal.*

---

## 3. Local LLM Setup Strategy

### Installation
User must have Ollama installed globally.
1.  **Download**: [ollama.ai/download](https://ollama.ai/download)
2.  **Verify**: `ollama --version`

### Models
We define two tiers of models.

**Default (Speed First)**
*   **Model**: `llama3.2:3b` (or `phi3:mini`)
*   **Size**: ~2GB
*   **Justification**: Incredible speed on M-series chips. Good enough for summarization and basic Q&A.
*   **Command**: `ollama pull llama3.2:3b`

**Power User (Quality First)**
*   **Model**: `mistral:7b-instruct-v0.2` or `llama3.1:8b`
*   **Size**: ~4-5GB
*   **Command**: `ollama pull mistral`

---

## 4. Hardware Assumptions & Performance Targets

**Target Hardware**: MacBook Air M1 (8GB RAM) or better.

**Performance Targets**:
*   **Ingestion**: < 200ms per text file (chunk + embed + save).
*   **Search**: < 100ms latency (P99).
*   **RAG Response**: < 5 seconds to first token (using Llama 3 8B).

**Guardrails**:
*   **Memory**: Vector store should not load entirely into RAM. LanceDB handles this via memory mapping.
*   **Disk**: Embeddings are stored on disk, not RAM.
