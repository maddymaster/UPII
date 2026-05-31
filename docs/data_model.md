# UPII v0.5 Data Model & Contracts

This document defines the durable data contracts for UPII v0.5, using SQLite as the single source of truth for metadata and LanceDB for vectors.

## 1. Schema Overview

The database uses `integers` for internal primary keys where possible for performance, but UUIDs (text) are acceptable if distributed generation is needed later. For v0.5 Local, we stick to standard SQLite `INTEGER PRIMARY KEY` for rowids or `TEXT` UUIDs if explicit IDs are preferred. Given the "content addressing" requirement, we use hashes as logical keys often.

We will use `TEXT` (UUID v4) for IDs to allow easier decoupled generation in Python.

### Tables
1.  `documents`
2.  `chunks`
3.  `tasks`
4.  `query_logs`
5.  `schema_migrations`

---

## 2. DDL Statements

```sql
PRAGMA foreign_keys = ON;

-- 1. Migration/Version Tracking
CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    description TEXT NOT NULL
);

-- 2. Documents
-- Invariant: content_hash is unique per file content. deduplication happens here.
CREATE TABLE IF NOT EXISTS documents (
    doc_id TEXT PRIMARY KEY,                  -- UUID v4
    source_path TEXT NOT NULL,                -- Absolute path on disk
    source_type TEXT NOT NULL,                -- 'pdf', 'txt', 'md', 'note'
    created_at DATETIME,                      -- File creation time (OS)
    modified_at DATETIME,                     -- File modification time (OS)
    ingestion_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    content_hash TEXT NOT NULL UNIQUE,       -- SHA-256 of full content. Integrity check.
    metadata JSON                             -- Flexible extra fields
);

CREATE INDEX idx_docs_hash ON documents(content_hash);
CREATE INDEX idx_docs_path ON documents(source_path);

-- 3. Chunks
-- Invariant: chunk_id maps 1:1 to a record in the Vector Store (LanceDB)
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,                -- UUID v4, used as 'id' in LanceDB
    doc_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,             -- Ordering 0..N within doc
    text TEXT NOT NULL,                       -- Explicit content storage
    token_count INTEGER,                      -- For context window calculations
    start_offset INTEGER,                     -- Byte/Char offset start
    end_offset INTEGER,                       -- Byte/Char offset end
    FOREIGN KEY(doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
);

CREATE INDEX idx_chunks_doc ON chunks(doc_id);

-- 4. Tasks
-- Extracted actionable items from memory
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,                 -- UUID v4
    chunk_id TEXT,                            -- Provenance
    description TEXT NOT NULL,
    status TEXT DEFAULT 'pending',            -- 'pending', 'done', 'archived'
    due_date DATETIME,                        -- Nullable
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(chunk_id) REFERENCES chunks(chunk_id) ON DELETE SET NULL
);

-- 5. Query Logs
-- Local auditing and improvement
CREATE TABLE IF NOT EXISTS query_logs (
    query_id TEXT PRIMARY KEY,                -- UUID v4
    query_text TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    latency_ms INTEGER,
    result_count INTEGER
);
```

---

## 3. Interfaces & Invariants

### Document Invariants
1.  **Content Uniqueness**: `content_hash` MUST be unique. If a user ingests `note_A.txt` and `note_B.txt` containing identical text, only ONE `documents` row exists (the first one). The second file is effectively a "pointer" to the existing content, or usage logic must decide to update the `source_path` to the most recent one.
    *   *Decision for v0.5*: If hash exists, specific logic (e.g. "update path") is triggered, but no new row is created.
2.  **Immutability**: Once ingested, `documents.text` (implied via chunks) does not change. If a file changes, it is a NEW ingestion event (new hash). Old version might be pruned or kept as history (pruning preferred for v0.5).

### Chunk & Embedding Linkage
*   **Linkage Rule**: `chunks.chunk_id` == `VectorDB.id`.
*   **Consistency**: A transaction must ensure that if a row is added to `chunks`, the corresponding vector is added to LanceDB. If one fails, both roll back.
*   **Deletion**: Deleting a `document` cascades to `chunks` (SQL). Application logic must explicitly delete corresponding IDs from LanceDB using the list of deleted `chunk_id`s.

---

## 4. Migration Strategy

We use a simple integer-based migration system stored in `schema_migrations`.

**Workflow:**
1.  App startup checks `SELECT MAX(version) FROM schema_migrations`.
2.  Python code contains a registry of migration functions: `migrations = {1: apply_v1, 2: apply_v2}`.
3.  Execute all `ver > current_ver` in order locally.
4.  Update `schema_migrations`.

**Example (Python):**
```python
MIGRATIONS = [
    (1, "Initial Schema", "CREATE TABLE ..."),
    (2, "Add Task Due Date", "ALTER TABLE tasks ADD COLUMN ...")
]

def migrate(db):
    current = db.execute("SELECT MAX(version)...").fetchone()[0] or 0
    for ver, desc, sql in MIGRATIONS:
        if ver > current:
            db.execute(sql)
            db.execute("INSERT INTO schema_migrations ...", (ver, desc))
```
