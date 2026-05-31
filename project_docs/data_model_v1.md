# UPII v1.0 Data Model: Staging Area

## 1. Staging Database (`staging.db`)
A separate SQLite database designated for "Ambient" data. It is ephemeral-tolerant but persistent.

### Tables

#### `events`
Raw file system events captured by the Watcher.
```sql
CREATE TABLE events (
    event_id TEXT PRIMARY KEY,       -- UUID
    event_type TEXT NOT NULL,        -- 'created', 'modified', 'deleted'
    file_path TEXT NOT NULL,         -- Absolute path
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'pending'    -- 'pending', 'processed', 'ignored'
);
```

#### `staging_docs`
Documents parsed from events, waiting for approval.
```sql
CREATE TABLE staging_docs (
    staging_id TEXT PRIMARY KEY,     -- UUID
    source_event_id TEXT,            -- FK to events
    file_path TEXT NOT NULL,
    content_hash TEXT,               -- SHA256
    parsed_content TEXT,             -- Extracted text
    metadata JSON,                   -- {size, mtime, extension}
    status TEXT DEFAULT 'review',    -- 'review', 'approved', 'rejected'
    FOREIGN KEY(source_event_id) REFERENCES events(event_id)
);
```

## 2. Core Extension (LTM)
The main `upii.db` is extended to support structured temporal data.

#### `calendar_events`
Anchors memory in time. Populated via Calendar Connector.
```sql
CREATE TABLE calendar_events (
    event_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    participants JSON,               -- ["alice@example.com", "Bob"]
    source_file TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_calendar_start ON calendar_events(start_time);
```

#### `daily_metrics`
Local-only telemetry aggregation.
```sql
CREATE TABLE daily_metrics (
    date DATE PRIMARY KEY,           -- YYYY-MM-DD
    queries_count INTEGER DEFAULT 0,
    explicit_ingest_count INTEGER DEFAULT 0,
    passive_ingest_count INTEGER DEFAULT 0,
    total_docs_count INTEGER DEFAULT 0,
    db_size_mb REAL DEFAULT 0.0
);
```

## 4. Knowledge Graph Extension
Lightweight entity extraction to enhance recall.

#### `entities`
Stores unique entities extracted from text.
```sql
CREATE TABLE entities (
    entity_id TEXT PRIMARY KEY,      -- UUID
    name TEXT NOT NULL,              -- Normalized name (e.g., "Google")
    category TEXT NOT NULL,          -- 'PERSON', 'ORG', 'PROJECT', 'TOPIC'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, category)
);
```

#### `entity_edges`
Links entities to specific chunks of text.
```sql
CREATE TABLE entity_edges (
    edge_id TEXT PRIMARY KEY,        -- UUID
    entity_id TEXT NOT NULL,         -- FK to entities
    chunk_hash TEXT NOT NULL,        -- FK to chunks (in vector store/upii.db)
    source_doc_id TEXT NOT NULL,     -- FK to documents (easier reversible deletion)
    confidence REAL,                 -- 0.0 to 1.0 (heuristic score)
    context TEXT,                    -- Snippet/Sentence where entity appeared
    FOREIGN KEY(entity_id) REFERENCES entities(entity_id)
);
CREATE INDEX idx_edges_entity ON entity_edges(entity_id);
CREATE INDEX idx_edges_chunk ON entity_edges(chunk_hash);
```

## 3. Invariants
1.  **Append-Only Events**: The Watcher only appends to `events`.
2.  **No Vector Writes**: Staging data is **never** vectorized. It remains purely textual until promoted.
3.  **Isolation**: There are NO foreign keys linking `staging.db` tables to `upii.db` tables.

## 3. Migration Strategy
Since `staging.db` is a new file, no migration of `upii.db` is required. The v0.5 schema remains strictly for "Gold Standard" memory.
