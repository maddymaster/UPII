# UPII v1.0 Project Walkthrough

**Status**: v1.0 (Sovereign Memory Engine)
**Goal**: A local-first, privacy-focused personal memory storage engine with ambient capabilities.

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

## 4. v0.5 Core Features (Retained)
- **Ingest**: `upii.cli ingest /path`
- **Search**: `upii.cli search "query"`
- **Ask**: `upii.cli ask "question"` (Robust with CPU Fallback & Mock Mode)
- **Doctor**: `upii.cli doctor`
