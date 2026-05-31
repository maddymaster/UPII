# UPII v1.0: Investor Demo Strategy (Ambee Edition)

**Target Audience**: Seed/Series A Investors (Focus on AI Infrastructure, Privacy, and Climate Tech)
**Core Narrative**: "The Operating System for Sovereign AI Memory."

---

## 1. The Pitch (Market & Context)

**The Industry Problem: The Context Gap**
"We are entering the era of ubiquitous AI, yet our models remain amnesiac. To make an LLM truly useful today, enterprises and individuals are forced to make a dangerous trade-off: **Upload your entire digital brain (emails, contracts, strategy) to the cloud, or settle for dumb, generic AI.**
For regulated industries, CTOs, and privacy-conscious users, 'uploading everything' is simply not an option. This is the **Context Gap**: The friction between data sovereignty and AI utility."

**The Solution: UPII (Sovereign Memory)**
"UPII is the missing infrastructure layer. It is a **Local-First Memory Substrate** that indexes your digital life—files, calendars, meetings—and serves it to your AI models *on-device*.
-   **Zero Privacy Risk**: Data never leaves the machine.
-   **Zero Latency**: Sub-300ms retrieval context.
-   **Universal**: Agnostic to the underlying LLM (Ollama, proprietary, or cloud via redacted API)."

**The Evidence (Why we built this at Ambee):**
"I didn't build this for fun; I built it because I needed it. As CTO of Ambee, I deal with NASA partnerships and ICEYE satellite targeting data. I cannot paste that into ChatGPT. I need an AI that knows *my* context but keeps *my* secrets."

---

## 2. Demo Setup & Ingestion

> [!IMPORTANT]
> **Data Prep**: We have pre-generated a realistic "Ambee Dataset" (Strategic roadmap, meeting notes, tasks) in `demo_data_v2`.

### Step 1: Ingest the Datasets
Run this command 5 minutes before the call to wipe the DB and index the fresh Ambee documents:

```bash
# 1. Activate environment
source venv/bin/activate

# 2. Run the Ingestion/Reset Script
python scripts/reset_demo_env.py
# Output should say: "Found 5 files to ingest... SUCCESS"
```

### Visual Setup
1.  **Terminal**: Clean, large font.
2.  **Narrative**: You are playing yourself (Maddy, CTO).

---

## 3. The Live Demo Script (5 Minutes)

### Scenario 1: The "Contextual Recall" (ICEYE Partnership)
*Context: You forgot the specific resolution details from the ICEYE meeting.*

**Command:**
```bash
upii ask "What was the resolution and latency agreed upon with ICEYE?"
```

**Expected Answer:**
"The agreed latency is < 3 hours for tasking, and the resolution is 50cm GeoTIFFs."
*(Source: `meeting_iceye_partnership.md`)*

### Scenario 2: The "Synthesis" (Strategic Planning)
*Context: Combining NASA issues with Engineering tasks.*

**Command:**
```bash
upii ask "How does the NASA PACE calibration issue affect our roadmap?"
```

**Expected Answer:**
"The 'Blue Band' need recalibration, which affects our AOD calculations by 5%. We decided to ignore the Blue Band until the Nov 15 patch and prioritize UV data for pollen detection instead."
*(Source: `meeting_nasa_pace_integration.md` + `ambee_strategic_roadmap.md`)*

### Scenario 3: The "Actionable Intelligence" (Tasks)
*Context: What do I need to do?*

**Command:**
```bash
upii ask "What are my high priority recruiting tasks?"
```

**Expected Answer:**
"Interview the 2 Senior ML Engineer candidates from DeepMind."
*(Source: `cto_personal_tasks.md`)*

---

## 4. VC Q&A (Anticipated)

**Q: "Can it handle the massive NetCDF/GRIB files Ambee uses?"**
**A:** "Currently in v1.0, we tackle the *meta-layer*—the meetings, specs, and emails about the data. For v2.0, we are building connectors to index the metadata headers of NetCDF files directly."

**Q: "Why local?"**
**A:** "Because our satellite tasking orders are confidential. We can't risk an LLM training on our proprietary 'Firewatch' coordinates."


---

## 5. Post-Demo Follow-up
*   Send them the `walkthrough_v1_0.md` artifact.
*   Offer to install the CLI on their local machine (The "Viral Loop").
