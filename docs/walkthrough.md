# UPII v1.0 Project Walkthrough

**Status**: v1.0 (Sovereign Memory Engine)
**Goal**: A local-first, privacy-focused personal memory storage engine with ambient capabilities.

> 🎓 **Demoing to the grant jury?** Use
> [`jury_progress_demo.md`](jury_progress_demo.md) — a timed progress script + live
> walkthrough centred on the **T1.2 (deterministic ingestion)** milestone. This
> file is the general feature walkthrough.

> ℹ️ Examples below use `python -m upii.cli …`. After `pip install -e .` you can use
> the shorter `upii …` form instead (see [`packaging_and_release.md`](packaging_and_release.md)).

## 1. Core Documentation
- **v1.0 Blueprint**: [design_blueprint_v1.md](file:///Users/maddy/.gemini/antigravity/brain/f30adf6f-987c-4e2f-955a-422dfeaa805a/design_blueprint_v1.md)
- **Staging Schema**: [data_model_v1.md](file:///Users/maddy/.gemini/antigravity/brain/f30adf6f-987c-4e2f-955a-422dfeaa805a/data_model_v1.md)

## 2. New v1.0 Features (Ambient Memory)

### 🌊 Ambient Ingestion
- **Concept**: Monitors folders for changes but DOES NOT trust them immediately.
- **Opt-In**: Requires explicit feature flag activation.
- **Isolation**: Runs in a separate thread; writes to `staging.db`. Main memory (`upii.db`) is untouched.

### 📥 Inbox & Review
- **Inbox**: A staging area for captured content.
- **Trust**: You must explicitly `approve` items to promote them to Long Term Memory (LTM).

## 3. How to Use v1.0

### Step 1: Enable & Watch
```bash
# Verify it's opt-in (asks for confirmation first time)
python -m upii.cli watch ./demo_dataset
```
*Expected Output*: "Added to watch list... Starting watcher..."

### Step 2: Trigger Change
Create or modify a file in the watched directory.
```bash
touch demo_dataset/new_idea.md
```

### Step 3: Review Inbox
Check what was captured.
```bash
python -m upii.cli inbox
```
*Expected Output*: Table with "new_idea.md", Type="Created", Status="pending".

### Step 4: Approve (Ingest)
Promote the content to LTM.
```bash
python -m upii.cli inbox --approve <EVENT_ID>
```
*Expected Output*: "Ingested new_idea.md" -> "Extracted tasks...".

### Step 5: Verify
```bash
python -m upii.cli search "new idea"
```

## 4. Phase 2 — Deterministic, reproducible ingestion (T1.2)

Ingestion is **content-addressed**: documents and chunks are identified by a hash
of their content, so the same inputs always yield the same memory state.

### Dedup — re-ingest is a no-op
```bash
python -m upii.cli ingest ./demo_dataset --recursive   # first time: Processed N
python -m upii.cli ingest ./demo_dataset --recursive   # again: every file "Skipping (Unchanged)"
```

### Edit — re-chunk only what changed, purge the stale version
```bash
echo "New decision line." >> demo_dataset/project_omega.md
python -m upii.cli ingest ./demo_dataset --recursive    # "Updating … (purged N stale chunks)"
```

### Prove reproducibility
```bash
bash scripts/demo/repro_demo.sh                          # re-ingest -> identical chunk hashes ✓
python scripts/bench/scale_check.py --docs 500 --paras 60  # -> bench/results/scale_REPORT.md (100% reproducible)
```

Details: [`phase2_deliverables.md`](phase2_deliverables.md) ·
[`phase2_reproducibility_audit.md`](phase2_reproducibility_audit.md).

## 5. v0.5 Core Features (Retained)
- **Ingest**: `upii ingest /path --recursive`
- **Search**: `upii search "query"`
- **Ask**: `upii ask "question"` (cites sources; abstains when unsure; needs Ollama for local reasoning)
- **Doctor**: `upii doctor`
