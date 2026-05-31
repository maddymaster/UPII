# v1.0 Memory Safety Test Strategy

**Goal**: Verify that the Sovereign Memory Engine (v1.0) is safe, reliable, and does not corrupt user data over long periods of passive operation.

## 1. Regression Testing (v0.5 Compatibility)
**Objective**: Ensure core explicit ingestion and search capabilities remain functional.

- **Suite**: Existing `tests/` folder.
- **Key Tests**:
    - `test_ingest.py`: Explicit ingestion correctness.
    - `test_search.py`: Vector retrieval accuracy.
    - `test_rag.py`: End-to-end question answering.
- **Success Criteria**: All existing tests must pass (Green).

## 2. Integrity Testing (v1.0 Passive Safety)
**Objective**: Ensure ambient monitoring does not introduce data corruption or duplicates.

### 2.1 Duplication Prevention
- **Scenario**:
    1. Watch a folder.
    2. Create a file `note.txt`.
    3. Modify `note.txt` 5 times rapidly (debounce check).
    4. Move `note.txt` to `note_moved.txt`.
- **Assertion**:
    - `staging.db` contains consolidated events, not infinite spam.
    - `upii.db` (LTM) is **untouched** (Validation of Isolation).
    - If ingested (approved), search returns exactly **one** version (the latest).

### 2.2 Metadata Corruption
- **Scenario**: Ingest a file with complex headers/metadata via passive stream.
- **Assertion**:
    - `doc_id` generation is UUIDv4 and unique.
    - `source_type` is correctly tagged as "passive".
    - Timestamps (`created_at`, `modified_at`) match file system.

## 3. Long-Running Stability (24-48h Simulation)
**Objective**: Verify daemon stability and memory leaks.

- **Tool**: `tests/perf/test_long_running.py` (Simulation).
- **Configuration**:
    - Accelerated Time: 1 second = 1 minute simulation.
    - Operations: Randomly create, edit, delete files in watched directory.
- **Metrics**:
    - **Memory Usage**: Python process must not grow linearly (Leak check).
    - **DB Size**: `staging.db` should be pruned or bounded if policies exist (or just grow audit log linearly).
    - **Crash Free**: Watcher thread must survive for the duration.

## 4. Manual Verification Checklist
- [ ] **Data Wiping**: Run `upii knowledge wipe` and ensure graph is clear but vectors remain.
- [ ] **Overlay Stability**: Open/Close overlay 50 times rapidly. Ensure no lag or crash.
- [ ] **Inbox Audit**: Verify `upii inbox` shows correct history of passive events.
