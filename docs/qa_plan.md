# UPII v0.5 QA Strategy Plan

> [!IMPORTANT]
> **Goal**: Ensure UPII v0.5 remains a reliable, private, and performant local memory substrate.
> **Philosophy**: "Test Locally, Trust Verifiably". No data leaves the machine.

## 1. Testing Pyramid Strategy

### 1.1 Unit Tests (Foundational)
- **Scope**: Individual classes (`Chunker`, `LocalLoader`, `Embedder`, `TaskExtractor`).
- **Mocking**: Mock external IO (`fs`, `Ollama`, `LanceDB`, `SQLite`).
- **Target Coverage**: 80% line coverage.
- **Tools**: `pytest`, `pytest-mock`.

### 1.2 Integration Tests (Component Interop)
- **Scope**: 
    - `IngestionPipeline` (Loader -> Chunker -> Embedder -> DB).
    - `SearchEngine` (Query -> Embed -> VectorSearch -> Rank).
    - `RAG` (Query -> Search -> Prompt -> LLM response).
- **Test Doubles**: Use temporary directories (`tempfile`) and in-memory databases where possible, but use REAL `LanceDB` on disk (in temp dir) to catch ABI issues.
- **Latency**: Must run in < 10s total.

### 1.3 End-to-End (E2E) Tests (User Journeys)
- **Scope**: Full CLI commands.
- **Scenarios**:
    1. **"The Day One"**: Init -> Ingest Folder -> Status check (stats match).
    2. **"The Retrieval"**: Search specific term -> Verify document present.
    3. **"The Oracle"**: Ask question -> Verify answer + Citation.
    4. **"The Taskmaster"**: Ingest note with "TODO" -> `tasks list` shows it -> `tasks done` updates it.

## 2. Test Data Strategy

| Data Type | Description | Purpose |
| :--- | :--- | :--- |
| **Synthetic Golden Set** | 50 handcrafted MD/TXT files with known facts, tasks, and weird formatting. | Regression correctness. Source of truth. |
| **"Chaos" Corpus** | 1GB of generated random text, lorem ipsum, and binary garbage named `.pdf`. | Robustness & Crash testing. |
| **User Mirror** | (Manual) A copy of the developer's actual logic logs or obsidian vault. | Reality check (not in CI). |

## 3. Performance Benchmarks
*Hardware Benchmark Reference: Apple M1 Air, 8GB RAM.*

> [!WARNING]
> Performance regressions block merge.

- **Ingestion Throughput**: > 5 MB/sec (Text only).
- **Scale Target**: 1GB Corpus ingestion < 10 mins.
- **Search Latency**: < 200ms (P95) for top-5 chunks.
- **RAG End-to-End**: < 3.0s (P50) using `llama3.2` or equivalent quantization.
- **Startup Time**: CLI `upii status` < 100ms.

## 4. Reliability & Security

### 4.1 Reliability
- **Crash Recovery**: Kill process during ingestion -> Restart -> DB must be consistent (WAL mode).
- **Idempotency**: Running ingest twice on same folder results in 0 duplicates.
- **Migration**: Schema changes must be additive or versioned.

### 4.2 Security & Privacy
- **Network Gapping**: 
    - Test: Run `upii` with `unshare -n` (Linux) or monitor `Little Snitch` (Mac).
    - Assert: 0 bytes sent outbound.
- **Dependencies**: 
    - Weekly `pip-audit`.
    - Pin hashes in `requirements.txt`.

## 5. QA Checklist per Sprint (8 Sprints)

| Sprint | Focus | QA Deliverable |
| :--- | :--- | :--- |
| **1** | **Ingestion Core** | Unit tests for Loader/Chunker. Verify PDF parsing edge cases. |
| **2** | **Storage Layer** | DB Schema verification. Vector Store CRUD tests. 1GB Scale test (mock vectors). |
| **3** | **Embeddings** | Batch size tuning tests. Verify determinism of embeddings. |
| **4** | **Basic Search** | Precision/Recall on "Golden Set". Time-filter correctness. |
| **5** | **RAG V1** | "I don't know" assertion tests. Citation format verification. |
| **6** | **NLP/Tasks** | Task regex false positive tuning. |
| **7** | **Performance** | Full 1GB End-to-End benchmark. memory leak search (`memray`). |
| **8** | **Release** | Final regression. Install from fresh venv. CLI usability walkthrough. |

## 6. CI Pipeline Suggestion (GitHub Actions)

File: `.github/workflows/ci.yml`

```yaml
name: UPII CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11"]

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install Dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest pytest-cov

    - name: Lint
      run: |
        # Optional: ruff or flake8
        # pip install ruff && ruff check .

    - name: Run Unit & Integration Tests
      run: |
        # Exclude slow performance tests in CI for cost/speed
        pytest tests/ --ignore=tests/perf --cov=src/upii

    - name: Security Scan
      run: |
        pip install pip-audit
        pip-audit -r requirements.txt

  # Separate job or local-only script for performance due to hardware variance
```
