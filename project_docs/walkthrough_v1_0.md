# UPII v1.0: Sovereign Memory Engine - Walkthrough

**Goal**: Upgrade to Ambient Memory capabilities without compromising trust.
**Core Philosophy**: Passive observation, Explicit commitment.

## 1. Documentation Links
- **v1.0 Blueprint**: [design_blueprint_v1.md](file:///Users/maddy/.gemini/antigravity/brain/f30adf6f-987c-4e2f-955a-422dfeaa805a/design_blueprint_v1.md)
- **Staging Schema**: [data_model_v1.md](file:///Users/maddy/.gemini/antigravity/brain/f30adf6f-987c-4e2f-955a-422dfeaa805a/data_model_v1.md)

## 2. v1.0 New Features

###  Passive Sources Registry
Manage diverse ambient inputs with granular control.
- **FileSystem**: Watches folders for changes.
- **Browser** (Simulated): Captures "high-dwell" mock pages.
- **Calendar** (Simulated): Captures mock events.

###  Ambient Ingestion
- **Safeguards**:
    - **Opt-In**: Requires explicit enablement per source.
    - **Isolation**: Each source runs in its own thread.
    - **Audit Log**: Every capture, enable, or disable action is persistently logged.
    - **Staging DB**: Writes to `staging.db`, protecting the main memory from noise.

###  Inbox & Review
- **Inbox**: A holding area for passively captured events.
- **Trust**: You must explicitly `approve` it to promote to LTM.

## 3. How to Run (v1.0 Workflow)

### Step 1: Manage Sources
List available passive sources and enable the FileWatcher.
```bash
$ python -m upii.cli sources list
Name         Enabled   Running   Description
filesystem   No        No        Monitors selected folders...
browser      No        No        Captures metadata...
calendar     No        No        Ingests event titles...

$ python -m upii.cli sources enable filesystem
Path to watch?: ./demo_dataset
Enabled filesystem
```

### Step 2: Generate Passive Events
Modify a file in the watched directory.
```bash
echo "Passive thought" >> demo_dataset/notes.md
```

### Step 3: Audit & Inspect
Verify the capture in the audit log and check the inbox.
```bash
$ python -m upii.cli sources audit
Time                 Source      Action    Details
2026-01-10 16:20:00  filesystem  capture   {'path': '.../notes.md', 'type': 'modified'}

$ python -m upii.cli inbox
ID        Type      File            Time
a1b2c3d4  modified  .../notes.md    ...
```

### Step 4: Promote to Memory
Approve the event to move it from Staging to Permanent Memory.
```bash
python -m upii.cli inbox --approve <EVENT_ID>
```

### Step 5: Verify Temporal Memory
Check that calendar events are correctly integrated into search.
1. Run the temporal recall test:
   ```bash
   pytest tests/test_temporal_recall.py
   ```
2. This verifies:
   - Calendar events are indexed (in SQL).
   - "Last week" queries trigger hybrid search.
   - Future events are correctly filtered/ranked.

### Step 6: Verify Knowledge Graph (Entity Extraction)
1. Ingest content with proper names (e.g., "Project Omega is launching").
2. Entities are automatically extracted and linked.
3. Search for the entity:
   ```bash
   python -m upii.cli ask "What is the status of Project Omega?"
   ```
4. Verification: The answer should cite context linked via the Knowledge Graph (e.g. `[Related to Project Omega]`).
5. To wipe entities (Reversibility):
   ```bash
   python -m upii.cli knowledge wipe
   ```

### Step 7: Debugging Context Rehydration
To see *why* specific memories were retrieved (Ranking Logic):
1. Run a query with the debug flag:
   ```bash
   python -m upii.cli ask "Did I have a meeting yesterday?" --debug
   ```
2. The output will show:
   - **Score**: The final relevance score.
   - **Boost Reason**: Why it scored that way (e.g., `temporal:explicit_match` or `entity:ProjectOmega`).
   - **Source**: `vector`, `calendar`, or `entity`.

### Step 8: Global Access (Overlay)
**Goal**: Instant search via `Cmd+Shift+K`.
1. Install dependencies:
   ```bash
   pip install pywebview pynput
   ```
2. Start the daemon (in a background terminal):
   ```bash
   python -m upii.overlay.daemon
   ```
3. **Trigger**: Press `Cmd+Shift+K`. The UPII search bar should appear instantly (Glassmorphism UI).
4. **Use**: Type a query and press Enter. Results will render with source tags.
5. **Hide**: Press `Esc` or the hotkey again.

### Step 9: Local Insights (Metrics)
**Goal**: Monitor your usage while maintaining privacy.
1. **Show Dashboard**:
   ```bash
   upii metrics show
   ```
   Displays a 7-day rolling view of queries, ingestion counts, and DB size.
2. **Export Transparency Report**:
   ```bash
   upii metrics export --out report.json
   ```
   Dumps all local telemetry to a JSON file for your review or analysis.
