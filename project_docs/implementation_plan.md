# v1.0 Passive Ingestion Framework Plan

**Goal**: Build a safe, user-controlled system for ambient data capture.

## 1. Core Abstractions (`src/upii/ambient/sources.py`)
... (Existing Content)

## 6. Temporal Memory Reinforcement (Calendar)
**Goal**: Use structured calendar data to anchor memory recall.

### A. Connector: `CalendarConnector` (`src/upii/ambient/calendar_connector.py`)
- **Strategy**: Local-first parsing of `.ics` (iCalendar) files. 
- **Reasoning**: `.ics` is a universal export format supported by all major calendars (Apple, Google, Outlook) and requires no cloud API keys.
- **Functionality**:
    - Watch a directory (e.g., `~/CalendarExports`) for `.ics` files.
    - Parse events: `SUMMARY`, `DTSTART`, `DTEND`, `ATTENDEE`.
    - Drop sensitive fields: `DESCRIPTION`, `ATTACH`.

### B. Storage: `calendar_events` Table (`upii.db`)
- Unlike staging, approved calendar data anchors LTM.
- Schema:
    - `event_id` (UUID)
    - `title` (Text)
    - `start_time` (Timestamp, Indexed)
    - `end_time` (Timestamp)
    - `participants` (JSON List of Emails/Names)
    - `source_file` (Text)

### C. Retrieval Integration
- **Hybrid Search**: When `SearchEngine` detects a temporal query (e.g., "last week", "yesterday"):
    1.  Perform standard Vector Search.
    2.  Perform SQL Query on `calendar_events` for the time range.
    3.  Inject matching events into the Context Window as a styled list:
        - `[Calendar Event] 2023-10-24: Meeting with Alice & Bob (Topic: Project Omega)`
    4.  LLM uses this structured context to ground the answer.

## 7. Knowledge Graph Engineering
**Goal**: Lightweight entity extraction to find connections missed by vector search.

### A. Schema (`upii.db`)
- Implement `entities` and `entity_edges` tables as defined in `data_model_v1.md`.
- **Constraint**: No graph database dependency (NetworkX or simple SQL joins).

### B. Extraction Logic (`src/upii/analysis/entity_extractor.py`)
- **Strategy**: Hybrid Rule-Based + Heuristic.
- **Components**:
    - `EntityExtractor` class.
    - **Rules**:
        - **Projects**: Capitalized words following "Project", "Operation", "Code" (e.g., "Project Omega").
        - **People**: Named Entity Recognition (NER) via `spacy` (small model) OR strict capitalization chaining if staying dependency-light. *Decision: Regex first for "Project X", "Team Y".*
        - **Topics**: Frequent capitalized terms (TF-IDF style heuristic).
- **Output**: List of `(Entity, Confidence, Context)`.

### C. Retrieval Integration (`src/upii/analysis/search.py`)
- **Query Processing**: Extract entities from the user's *query*.
- **Expansion**:
    - If Query contains "Project Omega":
    - Look up "Project Omega" in (`entities` table).
    - JOIN `entity_edges` to find related Chunks.
    - Boost scores of these chunks in the vector search or specifically include them if confidence is high.

### D. Reversibility
- Add CLI command `upii entities wipe` to clear the `entities` and `entity_edges` tables without affecting the vectors.

## 8. Context Rehydration Pipeline (Core v1 Experience)
**Goal**: Unified ranking logic that combines Vector Search, Temporal Memory, and Knowledge Graph into a single coherent context stream, with explainability.

### A. Data Structure (`src/upii/core/types.py`)
- **`RankedChunk`**:
    - Extends `Chunk`.
    - `score` (float): Final relevance score.
    - `boost_reason` (str): e.g., "vector:0.85", "entity:ProjectOmega", "temporal:last_week".
    - `source_signal` (str): "vector", "calendar", "entity".

### B. Logic (`src/upii/analysis/rehydration.py`)
- **`ContextRehydrator`**:
    - **Step 1: Parallel Retrieval** (simulated via sequential calls):
        - Get standard vector search results.
        - Get calendar events if temporal keywords exist.
        - Get entity-linked chunks if entities exist.
    - **Step 2: Scoring & Deduplication**:
        - Base Score = Vector Similarity (0.0 - 1.0).
        - **Boosts**:
            - Entity Link: +0.2 (Soft boost).
            - Temporal Anchor: +0.5 (Strong boost for explicit questions like "last week").
        - Deduplicate by `chunk_hash`, keeping the highest score.
    - **Step 3: Selection**:
        - Sort by Score.
        - Take top K (e.g., 5-7).
        - Limit total context window (e.g., max 2000 tokens).

### C. Debug Integration
- Update `SearchEngine.search()` to return `List[RankedChunk]`.
- Update `upii ask` to print `boost_reason` if `--debug` flag is passed.

## 9. Global Access Layer (Overlay)
**Goal**: Instant "Spotlight-like" experience.

### A. Overlay App (`src/upii/overlay/app.py`)
- **Library**: `pywebview`.
- **Logic**:
    - `OverlayAPI` class exposes Python methods to JS: `query(text)`, `get_recent()`.
    - `create_window` starts the webview with a transparent background url (glassmorphism via CSS).
- **Frontend**:
    - HTML/CSS injected directly or minimal file.
    - Input field auto-focused.
    - Results fade in.

### B. Daemon (`src/upii/overlay/daemon.py`)
- **Library**: `pynput` (Global Hotkey).
- **Logic**:
    - Listen for `Cmd+Shift+K` (safer collision-wise than Cmd+K which is browser search).
    - When triggered:
        - If window hidden -> Show & Focus.
        - If window visible -> Hide.
    - **Optimization**: Keep Python process running. Do not cold-boot.

## 10. Evaluation & Metrics (Local Telemetry)
**Goal**: Provide privacy-preserving insights into system usage and health.

### A. Core Logic (`src/upii/analysis/metrics.py`)
- **Class**: `MetricsCollector` (Singleton).
- **Functionality**:
    - `track_query()`: Increment `queries_count` for today.
    - `track_ingest(source_type, count)`: Increment `explicit` or `passive` counters.
    - `snapshot(db_size)`: Update `db_size_mb`.
- **Storage**: Updates `daily_metrics` table in `upii.db` (Upsert logic).

### B. CLI (`upii metrics`)
- `upii metrics show`: Display table of last 7 days + Totals.
- `upii metrics export`: Dump full history to JSON (user consent artifact).

## 11. Founder Demo Mode
**Goal**: Visual aids for demonstrating the system's "Sovereignty" and "Health".

### A. CLI (`upii demo`)
- **`investor`**:
    - **Architecture**: Print ASCII art of System V1 (Watcher -> Staging -> Rehydrator).
    - **Memory Graph**: ASCII Tree/Graph using `rich.tree` showing Top 5 Entities + Linked Chunks.
    - **Live Pulse**: Query `staging.db` for the last 5 audit logs to show it's "alive".
- **`compare`**:
    - Print a side-by-side table of v0.5 vs v1.0 features (Latency, Safety, etc).




