# Claude Code Prompts — UPII (Reconciled Build Plan, v1.6)

**Prepared:** 22 June 2026
**Purpose:** A reprioritised prompt set that (a) keeps the v0.5→v3.0 roadmap's narrative, but (b) closes the gaps where that roadmap has **drifted from the signed Annexure-1 MoA milestones**, and (c) pulls forward the two highest-leverage moat items (MCP bridge + egress membrane).

> **Convention:** `[CC]` = run in Claude Code (in-repo). `[CW]` = do in chat (non-code / drafting).
> Each prompt is tagged with the **Annexure-1 milestone** it produces evidence for, so nothing the MoA commits to gets dropped.

---

## Why this set exists (read first)

The v1.5→v3.0 roadmap is an excellent **investor/jury narrative** and the enterprise revenue motion (3 pilots → 5 LOIs) is the right one. But three things in it are out of sync with what you are *contractually* committed to deliver in Annexure-1, and two strategic bets are scheduled too late:

1. **Evidence harnesses are scheduled ~6 months late.** Annexure-1 needs retrieval-eval, entity-eval and benchmark *reports* in **Tranche-1 (months 1–6)**. The roadmap puts the "formal benchmarking suite / NDCG" in **v3.0 / M3 (months 8–12)**. → **Track A pulls them forward.**
2. **A committed milestone is missing from the grant window.** Annexure-1 **T2.4** commits to **multi-device sync (laptop → phone/iPad over LAN)** inside the 12 months. The roadmap defers mobile/sync to **"Beyond v3.0 / v4.5."** That's a contractual gap. → **Track C, C1.**
3. **The provisional patent (T1.4b)** isn't in the roadmap's M1. It must be filed in Tranche-1, before any public pilot. → **Track D, D1.**
4. **Strategic, not contractual:** native **MCP bridge** is in the roadmap at **v5.0 (post-grant)** and the **egress/redaction membrane** isn't explicit. These are your moat and they're cheap — build them now. → **Track B.**

**Good news from the code audit:** the substrate is real. `watchdog` is already the primary watcher backend (the roadmap's "replace polling watcher" item is largely done — *verify the wiring bug is actually still present before fixing*). Cmd+Shift+K overlay daemon, inbox approve/reject + audit logging, KG, rehydration, and `write` all exist. The only open `task.md` item is "Update Inbox to show Audit Logs." So most grant milestones are **demonstrations of existing capability** — you mainly need the harnesses that produce the proof.

**Do NOT duplicate** what `CLAUDE_CODE_PROMPTS_v1.5.md` already covers (ambient hardening, inbox UX polish, `write` + honest-mode, curator auto-policy, overlay, signed installers, observability). Run those as-is for product hardening. **This file adds the missing strategic + compliance layer on top.**

---

## Suggested execution order

1. **Track A (A1–A5)** — grant evidence harnesses. Highest compliance leverage; unblocks 4 Tranche-1 milestones + 1 Tranche-2 from code you already have.
2. **Track D, D1** — draft the patent disclosure in parallel (no code).
3. **Track B (B1–B2)** — MCP bridge + egress membrane. Your moat; start once A is underway.
4. **Track C (C1–C2)** — multi-device sync ADR (design-first) + pluggable reasoning. The committed T2.4 + T2.2 architecture.
5. Run the existing `CLAUDE_CODE_PROMPTS_v1.5.md` phases for product hardening alongside.

---

# TRACK A — Grant evidence harnesses *(Tranche-1 critical)*

### A1 — Benchmark harness + `upii bench` *(→ Annexure-1 T1.1)* `[CC]`
```
Build the measurement harness that produces UPII's headline performance numbers.

1. scripts/bench/make_corpus.py — a deterministic synthetic corpus generator.
   - CLI: --docs N --target-chunks N --seed S --out DIR.
   - Emits realistic .md/.txt files so ingestion yields ~the requested chunk count
     under our default chunker (src/upii/ingestion/chunker.py).
   - Fully deterministic for a seed; print the ACTUAL chunk count via a dry run
     through the real chunker, not an estimate.
2. scripts/bench/benchmark.py — measures, against the real ingest + retrieval path:
   - ingestion throughput (docs/min, chunks/min),
   - retrieval latency distribution (p50/p90/p99 ms) over N representative queries.
   - excludes warm-up; records machine info (CPU/RAM/OS/Python/model).
   - writes bench/results/<timestamp>.json AND a human-readable bench/results/REPORT.md.
3. Add a `upii bench --corpus DIR --queries N` Typer command in src/upii/cli.py wrapping it.

Tests: tests/perf/test_corpus_gen.py (same seed => identical file hashes; approx
chunk-count targeting) and tests/perf/test_benchmark_smoke.py (tiny corpus, CI-safe).
Acceptance: on a ~100k-chunk corpus, REPORT.md cleanly shows docs/min and p50 latency.
This REPORT.md (run on the procured Mac Studio) is the T1.1 demonstration artifact.
```

### A2 — Determinism + scale reproducibility *(→ Annexure-1 T1.2)* `[CC]`
```
Prove content-addressed ingestion is reproducible and incremental at scale.

1. Audit chunker.py + the ingest path (cli.py, ingestion/loader.py) for non-determinism
   (dict ordering, timestamps, file-walk order, threading races, locale/encoding).
   Produce a findings list, then make chunk boundaries + hashes a pure function of
   (file content, chunker config) only.
2. tests/test_chunk_determinism.py — ingest a fixed fixture twice AND in shuffled
   file order; assert identical chunk hashes both times.
3. tests/test_incremental.py — re-ingest unchanged file = no-op (no new chunks/re-embed);
   edit = re-chunk only changed chunks (stable untouched hashes); delete = clean removal
   of chunks/vectors/metadata. Assert counts in upii.db and the vector store.
4. scripts/bench/scale_check.py — drive a large corpus through ingest → re-ingest
   (expect no-ops) → batch edits → deletes; write bench/results/scale_REPORT.md proving
   100% hash reproducibility and correct dedup/edit/delete counts.
5. scripts/demo/repro_demo.sh — clean, recordable terminal demo (wipe demo DB, ingest,
   print chunk count + a few hashes, re-ingest, show unchanged). Recording steps in header.

Acceptance: scale_REPORT.md shows 100% reproducible hashes; repro_demo.sh is screen-record ready.
```

### A3 — Retrieval evaluation harness *(→ Annexure-1 T1.3)* `[CC]`
```
Build the internal retrieval eval that proves multi-signal fusion beats semantic-only.

1. eval/dataset/ — a small, committed, labelled set of (query -> relevant chunk ids)
   over a fixed sample corpus. eval/build_dataset.py ingests deterministically and
   supports annotating relevance labels.
2. eval/run_eval.py — computes Recall@{1,5,10}, MRR, nDCG against the current retrieval
   path; writes eval/results/REPORT.md. One command end-to-end.
3. In rehydration.py / search.py, expose configurable fusion weights (semantic/temporal/
   relational) in core/config.py, and add `upii ask --debug` output showing each signal's
   contribution to the final score (build on the existing boost_reason).
4. Run eval with semantic-only vs full fusion; record BOTH in REPORT.md.

Tests: tests/test_eval_harness.py (tiny dataset) verifying metric math.
Acceptance: REPORT.md shows a measurable Recall@10 improvement from fusion over
semantic-only (that delta IS the T1.3 milestone — no fixed number is contractually required).
```

### A4 — Entity-extraction eval + KG visualisation *(→ Annexure-1 T1.4)* `[CC]`
```
Quantify KG quality and produce the graph artifact.

1. eval/entities/ — a labelled fixture (or generator + manual gold-label file) of
   documents with gold projects/people/orgs. eval/run_entity_eval.py computes
   precision/recall/F1 per entity type; writes eval/results/entity_REPORT.md.
2. Improve entity_extractor.py rules until overall precision clears a sensible internal
   bar (~0.80 stretch); keep it fully local/dependency-light. Extend
   tests/test_entity_extraction.py with regression cases.
3. `upii knowledge --graph --out graph.html` — self-contained interactive HTML (inline
   JS / vendored force-graph lib, NO external/cloud calls) of entities + entity_edges
   from upii.db. Nodes coloured by type, edges weighted by co-occurrence. Smoke test
   that it emits valid HTML for a seeded DB.

Acceptance: entity_REPORT.md (baseline + improvement) + graph.html are the T1.4 artifacts.
```

### A5 — Citation accuracy eval + abstention guardrail *(→ Annexure-1 T2.2, pulled forward)* `[CC]`
```
Make attributed synthesis verifiable now (it's cheap and de-risks Tranche-2).

1. In the answer path (analysis/llm.py, rehydration.py, `upii ask`): guarantee every
   answer cites the source chunk ids it used, and that every cited chunk is actually in
   the retrieved context (no fabricated citations).
2. Add a guardrail that abstains/flags ("I don't know — no retrieved context met the
   confidence threshold") when retrieval confidence is low, instead of hallucinating.
   Reuse the v1.5 honest-mode threshold; expose it in config.
3. eval/run_citation_eval.py — citation accuracy = fraction of answer claims correctly
   attributed to a real retrieved chunk; writes eval/results/citation_REPORT.md.

Tests: abstention triggers on out-of-corpus queries; no Sources block when abstaining.
Acceptance: citation_REPORT.md establishes a baseline (T2.2 demonstration, early).
```

---

# TRACK B — Moat: build now, not post-grant

### B1 — UPII as a local MCP server *(strategic; roadmap had this at v5.0 — pull forward)* `[CC]`
```
Expose UPII as a local Model Context Protocol (MCP) server so Claude, Cowork and Claude
Code can query the user's LOCAL memory as a tool. This is the distribution wedge: every
Claude/Cowork user becomes a potential UPII user.

Requirements:
- Tools: upii_search (semantic+temporal+relational retrieval, returns CITED chunks),
  upii_ask (attributed answer with citations), upii_list_sources.
- Returns ONLY relevant, user-APPROVED chunks with citations — never the whole corpus.
  The corpus never leaves the device; the MCP server runs locally.
- Respect existing consent/source flags; unapproved sources are invisible to the tool.
- Config to enable/disable the server and set per-tool scopes.
- Add `upii mcp serve` to start it; document one-step setup to add UPII to Claude/Cowork.

Add an integration test driving the MCP tools end-to-end against a seeded DB.
Acceptance: from a fresh Claude/Cowork config, `upii_ask` returns a cited answer sourced
only from approved local chunks; disabling a source makes its chunks unreachable via MCP.
```

### B2 — The Membrane: redaction + egress audit log *(strategic; your enterprise moat)* `[CC]`
```
Build the gateway that sits between UPII and ANY cloud model (Gemini today, MCP-bridged
cloud agents tomorrow). This is the feature regulated buyers sign contracts for.

Before context crosses to a cloud path it must:
1. Detect and optionally redact PII/secrets (emails, phone, IDs, keys) — configurable rules.
2. Show the user exactly what is about to leave and require approval, configurable:
   ask-every-time / allowlist / never.
3. Write an append-only, tamper-evident egress audit log: timestamp, destination model,
   which fields/chunks left, redactions applied. Add `upii egress log` to view it.

Wire it so NO cloud reasoning path (the Gemini branch in analysis/llm.py, and the MCP
bridge from B1 if it ever routes to a cloud model) can bypass the gateway.
Tests: nothing reaches a cloud path without passing the gateway; redaction rules applied;
log is append-only and detects tampering.
Acceptance: `upii egress log` shows a complete, ordered record; a forced-redaction query
proves PII never leaves. This log + a threat model is your enterprise security kit.
```

---

# TRACK C — Committed architecture the roadmap under-scheduled

### C1 — Multi-device LAN sync — ADR first, then build *(→ Annexure-1 T2.4)* `[CC]`
```
This is a CONTRACTUAL Tranche-2 milestone the v3.0 roadmap deferred to v4.5 — do not let
it slip out of the grant window. Design before coding.

Step 1 (this prompt): write docs/adr/0001_multidevice_sync.md proposing a LOCAL-NETWORK
PERSONAL HUB design: one canonical device (Mac Studio or the user's laptop) holds the
memory substrate; phone/iPad either (a) query it over the LAN, or (b) hold an encrypted
local replica that syncs peer-to-peer. NOTHING transits a third-party cloud.
Cover: discovery (mDNS/Bonjour), transport + auth (device pairing, TLS on LAN), the
sync unit (chunks + vectors + metadata), conflict policy (single-user => last-writer-wins
or CRDT), and the mobile on-device RETRIEVAL path (generative inference on mobile is an
explicit STRETCH goal per Annexure-1 — design for retrieval first).
List trade-offs (LAN-query vs replica), security risks, and a phased build plan.

Step 2 (later prompt, after ADR approved): implement the laptop-side hub service + a
minimal mobile retrieval client proving a laptop-captured memory is retrievable on a
phone/iPad over LAN with nothing leaving the user's devices. That demo IS the T2.4 artifact.
```

### C2 — Pluggable reasoning, side-by-side *(→ Annexure-1 T2.2)* `[CC]`
```
Confirm reasoning is cleanly pluggable: local Ollama (default), optional Gemini (must pass
through the Track B2 membrane), deterministic mock fallback — selected via config/env with
no hard cloud dependency.
Add `upii ask --engine {local,remote,mock}` and a `--compare` mode that runs the same query
through local and remote and prints answers side-by-side with citations and latency.
Tests: the mock path works with no model/network; --compare renders both columns.
Acceptance: side-by-side local vs remote on identical queries (the T2.2 demonstration).
```

---

# TRACK D — Non-code, time-sensitive

### D1 — Provisional patent invention disclosure *(→ Annexure-1 T1.4b)* `[CW]`
```
Help me draft an invention disclosure for a PROVISIONAL patent on UPII, to take to a
registered patent agent. Cover: the problem (the Context Gap); what is novel vs prior art —
(1) local-first multi-signal context rehydration fusing semantic + temporal + relational
signals, (2) content-addressed deterministic chunking for reproducible attributed memory,
(3) the redaction/egress membrane to cloud models; the core claims in plain language; and
the diagrams to include. Flag anything that may already be prior art.
NOTE: file BEFORE any public pilot to secure priority; filing cost is OWN FUNDS, not the
grant (claim separately under Karnataka Startup Policy).
```

### D2 — Reconcile the roadmap with the MoA *(governance)* `[CW]`
```
Produce a one-page reconciliation table mapping every Annexure-1 milestone (T1.1–T1.5b,
T2.1–T2.6) to the v0.5→v3.0 roadmap version that delivers it, flagging any milestone with
NO roadmap home (expected: multi-device sync, provisional patent, Tranche-1 eval reports).
Output the corrected roadmap edits so the deck and the MoA tell the same story. Then draft
the written note to the grant officer for any deviation that needs Review-Committee approval.
```

---

## Traceability — every Annexure-1 milestone has a home

| Annexure-1 milestone | Delivered by |
|---|---|
| T1.1 Infra + perf baseline | **A1** (+ hardware procurement) |
| T1.2 Deterministic chunking, reproducible | **A2** |
| T1.3 Rehydrator v2 + retrieval eval | **A3** |
| T1.4 Local KG extraction + viz | **A4** |
| T1.4b Provisional patent | **D1** (own funds) |
| T1.5 Tranche-1 reporting | report compiling A1–A4 + CA docs |
| T2.1 Ambient connectors + approval inbox | existing `v1.5` ambient prompts (hardening) |
| T2.2 Attributed synthesis + abstention + local/remote | **A5 + C2** |
| T2.3 Cross-platform signed installers v1.0 | existing `v1.5` installer prompts |
| T2.4 Multi-device LAN sync + mobile retrieval | **C1** |
| T2.5 Design-partner pilot | pilot metrics + `docs/pilot_report.md` |
| T2.6 Closure | final report + CA UC + own-funds + K-tech ₹25k |
| *(strategic, non-grant)* MCP bridge | **B1** |
| *(strategic, non-grant)* Egress membrane | **B2** |

---

*Sources: ELEVATE Nxt Annexure-1 Tranche Plan; v0.5→v3.0 Version Roadmap (pasted); CLAUDE_CODE_PROMPTS_v1.5.md; docs/task.md; UPII codebase audit (src/upii/ambient/watcher.py, overlay/daemon.py, cli.py) as of 22 Jun 2026.*
