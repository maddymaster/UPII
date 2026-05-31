# UPII v0.5: Explicit Memory Substrate - Walkthrough

**Goal**: A local-first, privacy-focused personal memory storage engine.
**Core Philosophy**: Explicit, user-triggered ingestion. Zero ambient data collection.

## 1. Documentation Links
- **Architecture**: [design_blueprint.md](file:///Users/maddy/.gemini/antigravity/brain/f30adf6f-987c-4e2f-955a-422dfeaa805a/design_blueprint.md)
- **QA Strategy**: [qa_plan.md](file:///Users/maddy/.gemini/antigravity/brain/f30adf6f-987c-4e2f-955a-422dfeaa805a/qa_plan.md)
- **Demo Script**: [demo_script.md](file:///Users/maddy/.gemini/antigravity/brain/f30adf6f-987c-4e2f-955a-422dfeaa805a/demo_script.md)

## 2. Product Demo

````carousel
### 1. Ingestion
First, we explicitly ingest a directory of notes.
```bash
$ python -m upii.cli ingest ./demo_dataset
Ingesting from demo_dataset (Recursive: False)
Processing ./demo_dataset/project_omega.md
Extracted 5 tasks
Processing ./demo_dataset/financials.txt
Ingested 2 documents.
```
<!-- slide -->
### 2. Semantic Search
Retrieve knowledge using natural language queries, filtered by time.
```bash
$ python -m upii.cli search "Omega risks" --time last_month
Searching for: 'Omega risks' (Time: last_month)

1. project_omega.md (Score: 0.82)
...dependency on legacy GPU drivers is a critical risk...
```
<!-- slide -->
### 3. RAG (Ask)
Ask complex questions. The local LLM synthesizes an answer from retrieved chunks.
```bash
$ python -m upii.cli ask "What is the budget status?"
Thinking...

Answer:
The budget is currently under review due to Q3 overruns.
Sources used:
[1] financials.txt
[2] team_sync.md
```
````

## 3. System Health (Doctor)
Run the `doctor` command to verify system integrity, including DB connection, Vector Store status, and LLM availability.

```bash
$ python -m upii.cli doctor
Running UPII Doctor...
sqlite         : OK
vector_db      : OK (12 vectors)
disk           : OK (820 GB free)
model          : OK (Found llama3.2)
ingestion      : OK (Last: 2026-01-10 16:15:00)
```

> [!NOTE]
> If Ollama is offline or the GPU fails, `doctor` will report a WARN, and the system will gracefully degrade to **Mock Mode**.

## 4. Developer Notes: Getting Started

### Prerequisites
- Python 3.9+
- [Ollama](https://ollama.ai) (for local inference)

### Installation
Clone the repository and install in editable mode to enable development.
```bash
# 1. Create venv
python -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Install UPII in editable mode
pip install -e .
```

### Running Tests
We use `pytest` for unit and integration testing.
```bash
pytest tests/
```

### Key Commands for Devs
- **Debug Mode**: Add `--debug` to any command for verbose logs.
  ```bash
  python -m upii.cli ingest . --debug
  ```
- **Reset State**: To clear all memory and start fresh:
  ```bash
  rm upii.db upii.log
  rm -rf upii_vectors
  ```
