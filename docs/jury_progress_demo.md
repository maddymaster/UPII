# UPII — Jury Progress Demo & Milestone Script

**Audience:** ELEVATE NxT review committee / jury — Tranche-1 progress update.
**Focus milestone:** **Annexure-1 T1.2** — *Deterministic, reproducible, content-addressed ingestion.*
**Duration:** ~10 minutes live (8 min demo + 2 min Q&A backstop).
**Machine:** procured Mac Studio (or any Mac/Windows with the repo installed).

> This is a live, on-device demo. Nothing in it touches the network — that is the
> point. Use it alongside the evidence docs in §4.

---

## Part 0 — Pre-demo setup (do this before the jury is watching)

```bash
cd UPII
source venv/bin/activate          # Windows: venv\Scripts\Activate.ps1
upii doctor                       # confirm the stack is green
```

Optional, only if you will show the `ask` step live: have [Ollama](https://ollama.com)
running with a model pulled (`ollama pull llama3.2`). The demo does **not** depend
on it — retrieval and the determinism story work with no LLM at all.

Have two terminal tabs ready and your font size large.

---

## Part 1 — The progress narrative (what to say, ~2 min)

> *"In our grant plan, Tranche-1 commits to a sequence of foundational milestones.
> Phase 1 — T1.1 — was the performance-baseline harness. The milestone we're
> demonstrating today is **Phase 2, T1.2: making the memory engine deterministic
> and reproducible at scale.*
>
> *Why this matters: a personal-memory system is only trustworthy if the same
> inputs always produce the same memory. If re-reading your files quietly changed
> your stored memory, or duplicated it, or left stale fragments behind, you could
> never trust a citation. So this milestone makes ingestion **content-addressed**
> — every document and every chunk is identified by a hash of its content, not by
> a random id or the time it was read.*
>
> *Concretely, we committed to four things and we'll show all four live:*
> 1. *100% reproducible chunk hashes — even at a million chunks;*
> 2. *de-duplication — re-reading an unchanged file does nothing;*
> 3. *incremental edits — a changed file re-chunks only what changed and cleans up the old version;*
> 4. *clean deletes — removing a file leaves no trace in the index.*
>
> *And all of it runs entirely on this machine."*

---

## Part 2 — Live demo (say / do / expect, ~6 min)

### Step 1 — Local-first, zero egress (30s)
*Say:* "First, the whole stack is local — vector store, embeddings, metadata."
```bash
upii doctor
```
*Expect:* health checks report OK (db, vector store, embedding model, disk). *Point out there is no API key or network check because nothing leaves the device.*

### Step 2 — Ingest a corpus (45s)
*Say:* "I'll ingest a small project corpus. Each file is hashed and chunked; action items are auto-extracted."
```bash
upii ingest ./demo_dataset --recursive
```
*Expect:* `Processing …` per file, occasional `Extracted N tasks`, and a `Summary: Processed N … Skipped 0`.

### Step 3 — Determinism = de-duplication (45s)  ⭐
*Say:* "Now the key behaviour. I run the **exact same ingest again**. A naive system would re-embed everything. Ours recognises the content is unchanged and does nothing."
```bash
upii ingest ./demo_dataset --recursive
```
*Expect:* every file `Skipping … (Unchanged)`, and `Summary: Processed 0 … Skipped N`. *This is content-addressed dedup — re-ingestion is a no-op.*

### Step 4 — Incremental edit (1 min)  ⭐
*Say:* "Let me edit one file and re-ingest. Only the changed file is touched — and its old chunks are purged so nothing stale lingers."
```bash
echo "Decision: NASA PACE blue-band calibration by Nov 15." >> demo_dataset/project_omega.md
upii ingest ./demo_dataset --recursive
```
*Expect:* one line `Updating …/<file> (purged N stale chunks)`, the rest `Skipping … (Unchanged)`, and `Summary: Processed 1 (of which 1 updated) …`.

### Step 5 — Reproducibility, provably (1.5 min)  ⭐⭐
*Say:* "Here's the headline claim as a recordable proof. This script ingests a corpus, then re-ingests the identical corpus, and verifies every chunk hash is byte-for-byte identical."
```bash
bash scripts/demo/repro_demo.sh
```
*Expect:* a tidy run ending in **"every chunk hash IDENTICAL ✓ — deterministic ✅"**.

*Say:* "And the same property at scale, with dedup / edit / delete all checked, producing a report we can hand you."
```bash
python scripts/bench/scale_check.py --docs 500 --paras 60
#   (grant/hardware run: --docs 20000  ≈ 1,000,000 chunks)
cat bench/results/scale_REPORT.md      # or open it
```
*Expect:* `ALL CHECKS PASSED`; the report shows **100% chunk-hash reproducibility** and correct dedup/edit/delete counts.

### Step 6 — Supporting capability: attributed retrieval (45s, optional)
*Say:* "Because identity is content-addressed, every retrieved result is traceable to an exact chunk."
```bash
upii search "satellite partner latency"
```
*Expect:* ranked chunks, each tagged with its content-hash id.

*Optional (needs Ollama):* "And synthesis cites those same chunks, or abstains if it isn't sure."
```bash
upii ask "What did we agree with ICEYE on?"
```
*Expect:* a cited answer, or a clean "I don't know" on out-of-corpus questions — never a hallucination.

---

## Part 3 — What to leave the jury with (30s)

*Say:* "To summarise: Tranche-1 milestone T1.2 is delivered. Ingestion is now
content-addressed and provably reproducible — dedup, incremental edit and clean
delete are all validated by automated tests and a scale report. This is the
foundation the retrieval-quality and knowledge-graph milestones build on next."

---

## Part 4 — Evidence artifacts (have these open in a tab)

| Artifact | What it proves |
|---|---|
| `bench/results/scale_REPORT.md` | 100% hash reproducibility + dedup/edit/delete counts at scale |
| `docs/phase2_deliverables.md` | Deliverable-by-deliverable status, features and metrics vs. the grant |
| `docs/phase2_reproducibility_audit.md` | The engineering audit: every non-determinism source found and fixed |
| Test run (below) | The same guarantees, enforced in CI |

```bash
python -m pytest tests/test_chunk_determinism.py tests/test_incremental.py -q
# 8 passed  — determinism + dedup/edit/delete with count assertions
```

---

## Part 5 — Milestone traceability

| Annexure-1 milestone | Status | Shown by |
|---|---|---|
| T1.1 — R&D infra + performance baseline | Harness in place; hardware run pending | `scripts/bench/` |
| **T1.2 — Deterministic, reproducible, content-addressed ingestion** | **Delivered** | **Steps 3–5 + scale_REPORT.md** |
| T1.3 — Context Rehydrator v2 + retrieval eval | Next | (in progress) |
| T1.4 — Local KG extraction + visualisation | Next | (in progress) |

---

## Part 6 — Q&A backstops (anticipated questions)

- **"How do you know it's 100% reproducible and not just usually?"** — The scale
  harness ingests the corpus into two independent stores and compares the full set
  of chunk hashes; the report prints the exact match count (e.g. 3000/3000). The
  unit tests assert it on every CI run.
- **"What stops re-embedding from drifting?"** — Chunk identity is a pure hash of
  (chunk text, chunker config). Same content + same config ⇒ same id, so unchanged
  chunks are never re-embedded.
- **"Does anything leave the device?"** — No. Embeddings are computed locally
  (MiniLM), vectors live in on-disk LanceDB, metadata in local SQLite. The cloud
  LLM is optional and off by default.
- **"Can you show a million chunks now?"** — The same command with `--docs 20000`;
  we run that on the procured Mac Studio and archive the report + screen recording
  as the formal T1.2 artifact.

---

## Timing cheat-sheet

| Segment | Target |
|---|---|
| Narrative (Part 1) | 2:00 |
| Steps 1–2 | 1:15 |
| Steps 3–4 (dedup + edit) | 1:45 |
| Step 5 (reproducibility proofs) | 1:30 |
| Step 6 + close | 1:15 |
| **Total** | **~7:45** + Q&A |
