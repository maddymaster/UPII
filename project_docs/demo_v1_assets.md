# UPII v1.0 Founder Demo Assets

## 1. The 5-Minute "Vision" Script
**Target**: VCs / High-Level Stakeholders.
**Focus**: Speed, Privacy, "Magic".

**Scene 1: The Problem (0:00 - 1:00)**
> "We all have 'Digital Amnesia'. Files, emails, meetings—lost in the cloud. Existing tools send your data to OpenAI. We built something different."

**Scene 2: Core Capability (1:00 - 2:30)**
*Action*: Open Terminal.
> "This is UPII. It runs 100% on my Macbook M1. No data leaves. Watch."
*Action*: `upii ask "What did I discuss with Alice last week about Project Omega?"`
> "It didn't just search keywords. It understood 'last week' from my calendar, 'Project Omega' from my notes, and synthesized an answer using a local LLM."

**Scene 3: The Magic (2:30 - 3:30)**
*Action*: Press `Cmd+Shift+K` (Overlay appears instantly).
> "It's always there. I'm working, I forget a detail. Bam. Global access. <300ms latency. No context switching."

**Scene 4: The Trust (3:30 - 4:30)**
*Action*: `upii metrics show`
> "We track usage, not user data. Here's my local telemetry. And if I want to see what it knows?"
*Action*: `upii demo investor` (Shows graph).
> "Full observability. I own the graph."

**Scene 5: Close (4:30 - 5:00)**
> "Sovereign AI. Enterprise grade. Local speed. This is UPII v1.0."

---

## 2. 10-Minute Deep Dive Script
**Target**: Engineers / Technical Due Diligence.
**Focus**: Architecture, Safety, Code.

**1. Architecture Walkthrough (2 mins)**
- Show `design_blueprint_v1.md`.
- Explain Staging DB vs LTM (Isolation).
- "We don't pollute the long-term memory with junk. Everything goes to staging first."

**2. Passive Ingestion Demo (3 mins)**
- *Action*: `upii sources enable filesystem` (Select a test folder).
- *Action*: Create `meeting_notes.txt` in that folder.
- *Action*: `upii inbox` -> Show it appeared instantly (Watcher).
- *Action*: `upii inbox --approve <id>` -> "Promoted to LTM."

**3. Graph & Temporal Logic (3 mins)**
- Explain `ContextRehydrator`.
- *Action*: `upii ask --debug "Who is working on the API?"`.
- Show `[entity:API]` boost in the debug output.
- Show `calendar_events` table via `sqlite3`.

**4. Safety & QA (2 mins)**
- Run `pytest tests/test_memory_integrity.py`.
- "We have a regression suite ensuring no data corruption. It's built for 24/7 uptime."

---

## 3. Before (v0.5) vs After (v1.0) Comparison

| Feature | v0.5 (Proof of Concept) | v1.0 (Sovereign Engine) |
| :--- | :--- | :--- |
| **Ingestion** | Manual CLI only (`upii ingest`) | **Passive + Ambient** (File Watcher, Calendar) |
| **Memory Model** | Vector Only (Flat) | **Hybrid Rehydration** (Vector + Graph + Time) |
| **UX** | Terminal Only | **Global Overlay** (Spotlight-like UI) |
| **Safety** | None (Direct Write) | **Staging Area** (Review before Commit) |
| **Latency** | Cold Boot (~2s) | **Instant** (Daemonized, <300ms) |
| **Observability** | `print()` statements | **Local Telemetry** (Metrics, Audit Logs) |

---

## 4. Investor Mode Features
**Command**: `upii demo investor`

1.  **Architecture Visualizer**: Prints a high-fidelity ASCII block diagram of the v1 system (Source -> Staging -> Rehydrator -> LLM).
2.  **Memory Graph**: Visualizes the top connected entities in the database as a text-based tree or network.
3.  **Audit Pulse**: Shows the last 5 "Passive" events to prove the system is alive and listening safely.
