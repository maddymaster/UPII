# UPII — Milestone Build Plan & Claude Code Prompts

**Project:** UPII (Unified Personal Intelligence Interface) · DataFrontier Innovations Pvt Ltd
**Maps to:** Annexure-1 Tranche Plan (ELEVATE Nxt Deeptech 2026)
**Purpose:** Turn each grant milestone + its Completion Demonstration into buildable phases, each with ready-to-paste Claude Code prompts — then layer pilot validation, the Claude/MCP memory-bridge, and go-to-market on top.

---

## Priority order (read this first)

The work below is in three tiers. **Never let a lower tier steal time from a higher one** — the grant has a contractual 12-month clock and milestone-linked disbursement.

1. **PART 1 — Grant milestones (Priority 1, non-negotiable).** Phases 1–11. These are tied to money and a deadline. Everything else waits behind these.
2. **PART 2 — Pilot & market validation (Priority 2).** Overlaps grant Phase 10 but goes further. Proves the product is wanted *and* produces the Tranche-2 demonstration evidence — so it pays double.
3. **PART 3 — Complement-Claude features (Priority 3, engineering)** and **PART 4 — Go-to-market (Priority 3, business).** Start these lightweight *in parallel* (a few hours a week), scale only after v1.0 ships. The MCP memory-bridge (Part 3) is the highest-leverage non-grant item — it rides Claude's adoption instead of fighting it.

A label on each prompt tells you the tool: **[CC]** = Claude Code (engineering), **[CW]** = Cowork/Claude (drafting, research, business).

---

## How to use this document

1. **Each grant milestone = one phase.** Phases are ordered; later phases assume earlier ones are merged to `main`.
2. **Every phase ends in the exact evidence the grant demands** (a benchmark report, an eval number, a demo video, installers). Build the *measurement* as a first-class deliverable — the number on the slide is your milestone proof.
3. **Workflow per prompt:**
   - Start Claude Code in the repo root, run `/init` once if `CLAUDE.md` is stale.
   - Paste the **Context preamble** (below) once at the start of a session, then paste the phase prompt.
   - Ask Claude Code to **plan first** (`plan mode` / "propose a plan, don't write code yet"), review, then let it implement.
   - Require tests to pass + a short `REPORT.md` artifact for the milestone before you call it done.
4. **Constraints are non-negotiable** (local-first, deterministic, no cloud dependency). They're encoded in the preamble so every prompt inherits them.

---

## Context preamble (paste once per Claude Code session)

```
You are working on UPII, a local-first, privacy-preserving personal-memory engine
(Python). Architecture and hard rules:

- Sovereignty: embeddings, vectors and metadata stay on-device. No corpus byte
  may leave the machine. Cloud LLM (Gemini) is OPTIONAL and swappable; default is
  local Ollama with a deterministic mock fallback. Never introduce a hard cloud
  dependency.
- Source of truth: SQLite (src/upii/storage/db.py). Vectors: LanceDB
  (src/upii/storage/vector.py). Embeddings: sentence-transformers / MiniLM
  (src/upii/analysis/embeddings.py).
- Determinism: chunk boundaries and chunk hashes are a pure function of content +
  config (src/upii/ingestion/chunker.py). Same input => same chunk hashes. Never
  make ingestion order- or time-dependent.
- Ambient capture is consent-gated and isolated: passive ingestion writes only to
  staging.db and goes through an approval inbox before durable memory
  (src/upii/ambient/, design in project_docs/design_blueprint_v1.md).
- CLI is Typer (src/upii/cli.py): doctor, ingest, search, ask, sources, tasks,
  watch, inbox, knowledge, metrics, write, demo.
- Tests live in tests/ (pytest). Performance tests in tests/perf/.

Rules for every change:
1. Propose a plan and list files you'll touch BEFORE writing code. Wait for my OK.
2. Keep changes minimal and additive; do not break existing tests.
3. Add/extend pytest tests for every new behaviour.
4. No new heavy dependencies without flagging the trade-off first.
5. Produce reproducible numbers: any benchmark/eval must be a committed script I
   can re-run with one command, writing results to a file.
```

---

# PART 1 — Grant Milestone Build *(Priority 1)*

> **MoA commitments vs internal targets.** The numeric targets in the phases below (e.g. ≥500 docs/min, Recall@10 ≥0.85, citation ≥0.90) are your *internal engineering stretch goals* — aim for them. The **Annexure-1 MoA commits only to the conservative "establish a baseline and demonstrate measurable improvement" wording**, so a missed number can never breach the agreement. Build to the ambitious targets; report to KITS against the conservative baselines. A provisional patent filing is now a Tranche-1 milestone (Phase 4b) — funded outside the grant.

# TRANCHE 1 (Months 1–6)

## Phase 1 — R&D infra + performance baseline
**Grant demonstration:** procurement invoices; ingestion ≥ 500 docs/min and median retrieval latency < 300 ms on a 100,000-chunk corpus.

This phase is mostly a **measurement harness** — the hardware is purchased separately; what you build is the benchmark that produces the headline numbers.

**Prompt 1.1 — synthetic corpus generator**
```
Create scripts/bench/make_corpus.py that generates a reproducible synthetic
document corpus for benchmarking. Requirements:
- CLI args: --docs N, --target-chunks N, --seed S, --out DIR.
- Produces realistic .md/.txt files (varied length, headings, paragraphs) so that
  ingestion yields approximately the requested chunk count given our default
  chunker config.
- Fully deterministic for a given seed (so benchmarks are repeatable).
- Print the actual chunk count after a dry-run through the real chunker
  (src/upii/ingestion/chunker.py), not an estimate.
Add tests/perf/test_corpus_gen.py asserting determinism (same seed => identical
file hashes) and approximate chunk-count targeting.
```

**Prompt 1.2 — ingestion + retrieval benchmark**
```
Create scripts/bench/benchmark.py that measures and reports:
1. Ingestion throughput (docs/min and chunks/min) for a given corpus dir, using
   the real ingest path.
2. Retrieval latency distribution (p50/p90/p99 in ms) over a configurable number
   of representative queries against the ingested corpus.
Requirements:
- One command: `python scripts/bench/benchmark.py --corpus DIR --queries N`.
- Warm-up runs excluded; report machine info (CPU, RAM, OS, Python, model name).
- Write results to bench/results/<timestamp>.json AND a human-readable
  bench/results/REPORT.md with a summary table.
- Add a `upii bench` Typer command in src/upii/cli.py that wraps this.
Acceptance: on a 100k-chunk corpus the report cleanly shows docs/min and p50
retrieval latency. Add tests/perf/test_benchmark_smoke.py (tiny corpus) so CI
exercises the harness without needing 100k chunks.
```

**Milestone close:** run the benchmark on the procured hardware, save `REPORT.md` + the JSON, screenshot the summary. That file is your demonstration artifact.

---

## Phase 2 — Harden ingestion + deterministic chunking at scale
**Grant demonstration:** 100% reproducible chunk hashes on a ≥ 1,000,000-chunk corpus; recorded CLI demo of re-ingestion to identical state; dedup + edit-diff + delete-handling validated.

**Prompt 2.1 — reproducibility audit**
```
Audit src/upii/ingestion/chunker.py and the ingest path in src/upii/cli.py +
src/upii/ingestion/loader.py for any source of non-determinism (dict ordering,
timestamps, file-walk order, threading races, locale/encoding). Produce a short
findings list first. Then fix each so chunk boundaries and chunk hashes are a
pure function of (file content, chunker config) only.
Add tests/test_chunk_determinism.py that ingests a fixed fixture twice (and in
shuffled file order) and asserts identical chunk hashes both times.
```

**Prompt 2.2 — dedup, edit-diff, delete-handling at scale**
```
Validate and harden content-addressed dedup and incremental update:
- Re-ingesting an unchanged file must be a no-op (no new chunks, no re-embed).
- Editing a file must re-chunk only changed chunks (chunk-level diff), leaving
  untouched chunk hashes stable.
- Deleting a watched file must remove its chunks/vectors and metadata cleanly.
Extend tests (tests/test_ingest.py / a new tests/test_incremental.py) to cover
each case with assertions on counts in upii.db and the vector store.
Then create scripts/bench/scale_check.py that drives a 1,000,000-chunk corpus
through ingest, re-ingest (expect no-ops), a batch of edits, and deletes, and
writes bench/results/scale_REPORT.md proving 100% hash reproducibility and
correct dedup/edit/delete counts.
```

**Prompt 2.3 — demo script**
```
Write scripts/demo/repro_demo.sh: a clean, narratable terminal demo that wipes a
demo DB, ingests a sample dir, prints chunk count + a few chunk hashes, re-ingests
the identical dir, and shows the hashes/counts are unchanged. Keep output tidy and
suitable for screen recording. Document the recording steps in the script header.
```

---

## Phase 3 — Context Rehydrator v2 (semantic + temporal + relational fusion)
**Grant demonstration:** Recall@10 ≥ 0.85 on an internal labelled eval set; live `upii ask` showing fused ranking.

**Prompt 3.1 — labelled eval set + harness**
```
Create an internal retrieval evaluation harness:
- eval/dataset/ : a small, committed, labelled set of (query -> relevant chunk
  ids) over a fixed sample corpus. Include a script eval/build_dataset.py that
  ingests the sample corpus deterministically and lets me annotate/relevance-label.
- eval/run_eval.py : computes Recall@k (k=1,5,10), MRR, and nDCG over the dataset
  against the current retrieval path, writing eval/results/REPORT.md.
- One command to run end-to-end.
Add tests/test_eval_harness.py (tiny dataset) verifying metric math.
```

**Prompt 3.2 — fusion ranking in the Rehydrator**
```
Review src/upii/analysis/rehydration.py and src/upii/analysis/search.py. Implement
v2 multi-signal fusion that combines, with configurable weights:
- semantic (dense vector similarity),
- temporal (recency / calendar-event proximity, via calendar_events),
- relational (knowledge-graph entity overlap from entity_extractor / entity_edges).
Make weights configurable in core/config.py and exposed via flags. Add a
`upii ask --debug` view that shows each signal's contribution to the final score.
After implementing, run eval/run_eval.py and iterate weights until Recall@10
>= 0.85 on the eval set. Commit the eval REPORT.md.
```

---

## Phase 4 — Local knowledge-graph extraction
**Grant demonstration:** entity precision ≥ 0.80 on a 500-document labelled set; knowledge-graph visualisation.

**Prompt 4.1 — extractor precision harness**
```
src/upii/analysis/entity_extractor.py extracts projects/people/orgs with rule-based
heuristics. Build eval/entities/ : a 500-document labelled fixture (or a generator
+ manual label file) with gold entities. Add eval/run_entity_eval.py computing
precision/recall/F1 per entity type, writing eval/results/entity_REPORT.md.
Then improve the extractor (better rules/heuristics, dependency-light) until
overall entity precision >= 0.80. Keep it fully local. Extend
tests/test_entity_extraction.py with regression cases.
```

**Prompt 4.2 — graph visualisation**
```
Add `upii knowledge --graph --out graph.html` that renders the local knowledge
graph (entities + entity_edges from upii.db) as a self-contained interactive HTML
file (no external/cloud calls; inline JS, e.g. a vendored force-graph lib). Nodes
coloured by entity type, edges weighted by co-occurrence. Add a smoke test that
the command produces valid HTML for a seeded DB.
```

---

## Phase 4b — Provisional patent filing *(Tranche-1 milestone, non-code)*
**Grant demonstration:** filed provisional patent application with its official application/receipt number.

File a **provisional** patent (cheap, fast, establishes a priority date, low commitment risk) covering UPII's novel methods — sovereign multi-signal context rehydration (semantic + temporal + relational fusion) and attributed on-device memory. File once Phases 3–4 have crystallised the novel method, but before any public launch/pilot so you establish priority first. **Filing cost is funded from your own funds, not the grant** (patent costs aren't grant-reimbursable per Annexure-2; claim them separately under Karnataka Startup Policy incentives).

**Prompt 4b.1 — invention disclosure draft [CW]**
```
Help me draft an invention disclosure for a provisional patent on UPII. Cover: the
problem (the Context Gap), what is novel vs prior art (local-first multi-signal
context rehydration fusing semantic + temporal + relational signals; content-
addressed deterministic chunking for reproducible attributed memory; the redaction/
egress membrane to cloud models), the core claims in plain language, and diagrams to
include. Output a structured disclosure I can take to a patent agent. Flag anything
that looks like it may already be prior art.
```
*(Actual filing is done with a registered patent agent — outside code.)*

---

## Phase 5 — Tranche-1 review & reporting *(non-code milestone)*
**Grant demonstration:** Tranche-1 completion report + demo video; CA-attested UC, audited expenditure, No-Lien statement.

**Prompt 5.1 — consolidate evidence**
```
Generate docs/tranche1_completion_report.md that pulls together the Phase 1–4
evidence: link each grant milestone to its committed artifact (bench REPORT.md,
scale_REPORT.md, eval REPORT.md, entity_REPORT.md, graph.html, demo scripts) with
the headline number for each. Produce a one-paragraph plain-English summary per
milestone suitable for the KITS reviewer. Flag any milestone whose target number
is not yet met.
```
*(The UC, audited statement and bank statement are handled with your CA — outside code.)*

---

# TRANCHE 2 (Months 7–12)

## Phase 6 — Ambient connectors (mail + calendar), consent-gated
**Grant demonstration:** ≥ 2 connectors live; live ingestion with consent + approval-inbox walkthrough.

**Prompt 6.1 — harden the two connectors**
```
Review src/upii/ambient/calendar_connector.py and
src/upii/ambient/email_connector.py against project_docs/implementation_plan.md.
Bring both to "live" quality:
- Calendar: robust local .ics parsing (Apple/Google/Outlook exports); keep
  SUMMARY/DTSTART/DTEND/ATTENDEE, drop DESCRIPTION/ATTACH; write to calendar_events.
- Email: local mailbox parsing (e.g. .mbox / .eml), sensitive-field minimisation,
  consent-gated.
Both must route through staging + the approval inbox, never directly to LTM.
Add/extend tests (tests/test_ambient.py, tests/test_sources.py) with realistic
fixtures and an isolation test proving nothing reaches upii.db before approval.
```

**Prompt 6.2 — consent + approval-inbox UX**
```
Polish the consent + review flow end-to-end: `upii sources` to enable/disable a
source (consent), `upii watch` to capture, `upii inbox` to review/approve/reject.
Ensure every ambient item shows provenance and that approve promotes it into LTM
(+ embeddings) while reject purges it from staging. Write scripts/demo/ambient_demo.sh
that demonstrates the full consent -> capture -> inbox -> approve loop for both
connectors, suitable for screen recording.
```

---

## Phase 7 — Attributed synthesis + answer verification
**Grant demonstration:** citation accuracy ≥ 0.90 on the eval set; side-by-side local vs optional-remote reasoning.

**Prompt 7.1 — citation grounding + guardrail**
```
In the RAG/answer path (src/upii/analysis/llm.py, rehydration.py, `upii ask`),
ensure every answer cites the source chunk ids it used and that cited chunks are
actually in the retrieved context (no fabricated citations). Add a guardrail that
abstains/flags when retrieval confidence is low instead of hallucinating.
Build eval/run_citation_eval.py measuring citation accuracy (fraction of answer
claims correctly attributed to a real retrieved chunk) over the eval set; target
>= 0.90; write eval/results/citation_REPORT.md.
```

**Prompt 7.2 — pluggable reasoning, side-by-side**
```
Confirm reasoning is cleanly pluggable: local Ollama (default), optional Gemini,
deterministic mock fallback — selected via config/env, no hard cloud dependency.
Add `upii ask --engine {local,remote,mock}` and a `--compare` mode that runs the
same query through local and remote and prints answers side-by-side with their
citations and latency. Add tests that the mock path works with no model/network.
```

---

## Phase 8 — Cross-platform packaged release v1.0
**Grant demonstration:** signed installers for macOS/Windows/Linux; clean-machine install + `upii doctor` health check on each.

**Prompt 8.1 — reproducible build pipeline**
```
Using the existing upii.spec / build/ setup, produce reproducible single-file (or
installer) builds for macOS, Windows and Linux via PyInstaller. Create a GitHub
Actions workflow (.github/workflows/release.yml) with a matrix over the three OSes
that builds artifacts on tag push and attaches them to a GitHub Release. Document
the signing/notarisation steps (macOS codesign + notarytool, Windows signtool) as
clearly-marked TODO steps requiring my certificates. Update docs/packaging_and_release.md.
```

**Prompt 8.2 — first-run health check**
```
Make `upii doctor` a reliable clean-machine acceptance check: verify DB, vector
store, embedding model availability, disk, and (gracefully) reasoning-engine
status, printing a clear PASS/FAIL summary with remediation hints. Add a
`scripts/release/smoke_install_check.sh` that a fresh install can run to confirm
the stack is healthy. This is the artifact you record on each OS.
```

---

## Phase 9 — Multi-device sync architecture (laptop + phone + iPad)
**Grant demonstration:** a memory captured on the laptop retrieved on iPhone and iPad over the local network (no cloud); on-device mobile inference benchmark on iOS and Android with citations preserved.

This is the biggest *architectural* change in the project: UPII today is single-machine. "Single user, multi-device" must hold the no-cloud line, so the design is a **local-network personal hub** — one device (e.g. the Mac Studio or the user's laptop) holds the canonical memory substrate, and the phone/iPad either query it over the LAN or hold an encrypted local replica that syncs peer-to-peer. Nothing transits a third-party cloud.

**Prompt 9.1 — sync architecture ADR (design first, no code)**
```
Before any code: produce docs/adr/0001-multi-device-sync.md (architecture decision
record). Compare options for single-user, multi-device sync that PRESERVE the
local-first/no-cloud guarantee:
(a) Personal hub: one device serves the memory substrate over the LAN; phone/iPad
    are thin clients.
(b) Peer replication: each device keeps a local store; encrypted P2P sync over LAN
    (e.g. CRDT-based merge of the SQLite metadata + vector deltas).
(c) Hybrid: hub-of-record + offline local cache on mobile.
For each: data model impact, conflict resolution, security (device pairing,
encryption at rest + in transit on LAN), offline behaviour, and effort. Recommend
one and list the concrete components to build. Do not write implementation code
until I approve the ADR.
```

**Prompt 9.2 — sync protocol + service (desktop side)**
```
Implement the approved sync design on the desktop/hub side:
- A local-network sync service (e.g. an authenticated localhost/LAN endpoint) that
  exposes the memory substrate to paired devices. Device pairing must be explicit
  (QR/code), encrypted in transit, and consent-gated like all other UPII capture.
- Conflict-safe merge of metadata (SQLite) and vector deltas so a memory added on
  one device appears on others without duplication (reuse content-addressed hashes).
- No cloud endpoints; LAN/loopback only. Add an integration test simulating two
  devices syncing a new memory and asserting identical resulting state + no dupes.
Update docs and add `upii sync` CLI commands (pair / status / list-devices).
```

**Prompt 9.3 — mobile on-device runtime (iOS/iPadOS + Android)**
```
Stand up a minimal mobile client that runs UPII retrieval ON-DEVICE and syncs via
the Phase 9.2 service:
- iOS/iPadOS: on-device embedding + small-model inference via Core ML / MLX; reuse
  the Apple-Silicon work from the Mac.
- Android: on-device inference via llama.cpp/GGUF or ONNX Runtime; one mid-tier
  test device is the floor target.
- The client retrieves with citations and degrades gracefully to retrieval-only
  when no local model fits. Keep all data on-device; sync only over the paired LAN
  channel.
Benchmark on-device retrieval latency + a small-model answer on iOS and Android and
write bench/results/mobile_REPORT.md. This file is your milestone artifact.
```

---

## Phase 10 — Design-partner pilot
**Grant demonstration:** ≥ 5 pilot users; usage/reliability metrics over ≥ 4 weeks; ≥ 3 testimonials.

**Prompt 10.1 — local, privacy-preserving usage metrics**
```
Extend `upii metrics` so it records LOCAL-ONLY usage/reliability counters (queries
served, ingestion volume, retrieval latency samples, errors) in the local DB — no
telemetry leaves the device. Add `upii metrics export --out metrics.json` producing
an anonymised summary a pilot user can voluntarily send me. Add tests for the
counters and the anonymisation (no file paths, no content, no PII in the export).
```

**Prompt 10.2 — pilot aggregation**
```
Create scripts/pilot/aggregate.py that ingests multiple anonymised metrics.json
exports and produces docs/pilot_report.md: active users, total queries, latency
distribution, error rate, week-over-week trend. Keep it deterministic and offline.
```

---

## Phase 11 — Project closure *(mostly non-code)*
**Grant demonstration:** final completion report; CA-attested UC + audited expenditure; evidence of ₹1,00,000 own-funds spend via No-Lien account; ₹25,000 earmarked to K-tech Innovation Hub.

**Prompt 11.1 — final report assembly**
```
Generate docs/final_completion_report.md consolidating all ten milestones, each
with its committed evidence artifact and final headline number, plus a v1.0
changelog and architecture summary. Produce a one-page executive summary for KITS.
```
*(Financial closure — UC, audit, own-funds spend, incubation earmark — is executed with your CA and the No-Lien account.)*

---

## Suggested cadence

| Months | Phases | Headline proof to bank |
|---|---|---|
| 1 | 1 | Benchmark REPORT.md (docs/min, p50 latency) |
| 2 | 2 | Scale REPORT.md (1M-chunk reproducibility) |
| 3–4 | 3 | Recall@10 ≥ 0.85 eval REPORT.md |
| 5 | 4 | Entity precision ≥ 0.80 + graph.html |
| 6 | 5 | Tranche-1 completion report + UC |
| 7 | 6 | Two live connectors + ambient demo |
| 8 | 7 | Citation accuracy ≥ 0.90 + compare demo |
| 9 | 8 | Signed installers + doctor PASS on 3 OSes |
| 10 | 9 | Multi-device sync: laptop → phone/iPad over LAN + mobile bench |
| 11 | 10 | Pilot report (≥5 users, ≥3 testimonials) |
| 12 | 11 | Final report + financial closure |

> Tranche-2 now carries six milestones in six months — multi-device sync (Phase 9) is the heaviest add. If it slips, the cleanest lever is to start the sync ADR (Prompt 9.1) during Phase 8 and run mobile work in parallel, since the desktop release and the mobile runtime share the Apple-Silicon inference path.

## Working tips for Claude Code on this repo
- Run `/init` to refresh `CLAUDE.md`, and keep the **Context preamble** in it so every session inherits the rules.
- Prefer **plan-first**: "Propose a plan and the files you'll touch; don't write code yet."
- After each phase: `pytest -q` must pass, and the milestone's `REPORT.md`/artifact must exist and contain the headline number.
- Commit the eval datasets and benchmark scripts — your grant proof is *reproducible numbers*, not screenshots alone.
- Keep every new capability behind the local-first rule; if Claude Code proposes a cloud call, reject it or make it optional + off by default.

---

# PART 2 — Pilot & Market Validation *(Priority 2)*

This track proves people actually want UPII **and** generates the exact evidence Tranche-2 (Phase 10) needs — so it's not "extra" work, it's the same work pointed at two goals. Run it from ~Month 7, but start customer interviews earlier (they're cheap and shape everything).

**Who you're validating with:** start with one beachhead — high-context technical professionals / founders handling sensitive data (your own persona) — then expand to regulated solos (lawyers, accountants, advisors). Don't validate "everyone with notes."

**The only metrics that matter** (vanity downloads don't count): activation (% who ingest their own corpus + connect ≥2 sources), engaged retention (week-4 retention; recall queries per active user per week), multi-device adoption, and willingness to pay (paid pilot / pre-order / LOI).

**Prompt 2A — interview guide & target list [CW]**
```
Help me run problem-validation interviews for UPII (local-first private memory for
people who can't put their data in cloud AI). Draft: (1) a 12-question interview
guide that tests the "can't use cloud AI" pain, current workarounds, and
willingness to pay — without leading the witness; (2) a screening profile for my
beachhead (technical professionals/founders handling sensitive data); (3) a
one-paragraph outreach DM/email I can personalise. Keep it neutral and short.
```

**Prompt 2B — synthesise interviews into a decision [CW]**
```
Here are my notes from N validation interviews [paste]. Synthesise: top recurring
pains (ranked, with verbatim quotes), which segment feels it most acutely, current
alternatives and what they'd pay, and a clear go / pivot / no-go recommendation
with the evidence behind it. Flag where my sample is too thin to conclude.
```

**Prompt 2C — design-partner pilot kit [CW]**
```
Create a design-partner pilot kit for 5–10 users: a one-page pilot agreement
(free access for 4 weeks in exchange for usage + a testimonial; data stays on
their device), an onboarding checklist, a weekly check-in template, and the 3
success metrics we'll track. Keep the agreement plain-English, not legalese.
```

**Prompt 2D — usage metrics & pilot report [CC]**
> Engineering side already covered by grant Phase 10.1 (local-only usage metrics) and 10.2 (pilot aggregation → `docs/pilot_report.md`). That report is the artifact you show **both** KITS and investors.

**Validation checklist (Priority 2 done = all true):**
- [ ] 20–30 problem interviews completed; pain + WTP confirmed for one segment
- [ ] ≥5 design partners live for ≥4 weeks
- [ ] Activation, week-4 retention and queries/user measured (locally, privacy-preserving)
- [ ] ≥3 testimonials captured
- [ ] ≥1 design partner converted to paying (or signed LOI)
- [ ] `docs/pilot_report.md` generated (doubles as Tranche-2 demonstration)

---

# PART 3 — Complement Claude / Cowork: the Memory-Bridge *(Priority 3 — engineering)*

**Strategy:** don't rebuild Claude's brain. Be the **memory and the membrane** — the private on-device memory Claude lacks about the user, and the boundary that controls what reaches it. Every new Claude/Cowork user then becomes a potential UPII user. Build these only once the v1.0 substrate (Parts 1) is stable; the MCP server (3A) is the single highest-leverage item and can be pulled forward if grant timelines allow.

**Prompt 3A — UPII as an MCP server (the bridge) [CC]**
```
Expose UPII as an MCP (Model Context Protocol) server so Claude, Cowork and Claude
Code can query the user's LOCAL memory as a tool. Requirements:
- Tools: upii_search (semantic+temporal+relational retrieval, returns cited chunks),
  upii_ask (attributed answer), upii_list_sources.
- Returns ONLY the relevant, user-approved chunks with citations — never the whole
  corpus. The corpus never leaves the device; the MCP server runs locally.
- Respect existing consent/source flags; unapproved sources are invisible to the tool.
- Add a config to enable/disable the server and per-tool scopes.
Add an integration test that drives the MCP tools end-to-end against a seeded DB,
and document setup so a user can add UPII to Claude/Cowork in one step.
```

**Prompt 3B — selective-disclosure / redaction gateway + egress log [CC]**
```
Build the "membrane": a gateway that sits between UPII and any cloud model. Before
context crosses to the cloud it must (1) detect and optionally redact PII/secrets,
(2) show the user exactly what is about to leave and require approval (configurable:
ask-every-time / allowlist / never), and (3) write an append-only egress audit log
(timestamp, destination model, what fields/chunks left, redactions applied).
Add `upii egress log` to view it. Tests: nothing reaches a cloud path without
passing the gateway; redaction rules are applied; the log is tamper-evident.
```

**Prompt 3C — model-agnostic memory [CC]**
```
Make the memory layer explicitly model-agnostic so the SAME substrate serves Claude
(via MCP), local Ollama, and an optional remote model, selected per-query. No memory
feature may assume a specific model. Add a thin adapter interface and tests proving
identical retrieval results regardless of the reasoning engine chosen.
```

**Prompt 3D — Cmd+K overlay parity [CC]**
```
Polish the existing overlay (src/upii/overlay/) into an always-available Cmd+K recall
bar that matches the ubiquity users now expect: instant (<300ms) open, query, cited
answer, and a one-keystroke "send this with my memory to Claude" action that routes
through the Part 3B gateway. Keep it local-first; add a smoke test for launch + query.
```

> Don't build: cloud compute, a general agent framework, multimodal generation, a big skills marketplace. That's Claude's turf — competing there is a money pit and dilutes the moat.

---

# PART 4 — Go-to-Market: what you'll need *(Priority 3 — business)*

A checklist of everything required to actually ship and sell, grouped. Most items are small and parallelisable; the engineering ones reference phases above.

**Product & distribution**
- [ ] Open-core decision: which parts are OSS (the engine — for "verify, don't trust") vs paid (sync, connectors, team). Pick a license (e.g. Apache-2.0 core).
- [ ] Signed/notarised installers for macOS/Windows/Linux — grant **Phase 8**.
- [ ] MCP server published + listed so Claude/Cowork users can find it — **Part 3A**.
- [ ] Landing page + waitlist; docs site; demo video (90s, the "unplug the internet, it still works" moment).

**Trust & compliance (your actual differentiator)**
- [ ] Threat model + independent security review before public launch.
- [ ] Privacy policy + a plain-English "what never leaves your device" statement.
- [ ] Egress audit feature shipped — **Part 3B** (this is a *sales* asset for regulated buyers).

**Commercial**
- [ ] Pricing tiers: free local core / Pro (multi-device sync + connectors) / Team-Enterprise (on-prem, admin, compliance).
- [ ] Billing infra (Stripe/Paddle/Lemon Squeezy) for license or subscription.
- [ ] Design-partner → paid conversion path — **Part 2C**.

**Brand & content**
- [ ] One-line positioning ("AI that knows your context and keeps your secrets").
- [ ] Architecture blog post (sovereign memory, deterministic chunking, attributed retrieval) — your CTO credibility carries it.
- [ ] Launch assets for HN / r/LocalLLaMA / r/privacy / Product Hunt / PKM communities.

**Ops**
- [ ] Support channel (Discord/email); privacy-preserving product analytics (opt-in, local-first) — **Phase 10.1**.
- [ ] Feedback loop into the roadmap.

**Prompt 4A — launch narrative & assets [CW]**
```
Draft my launch kit for UPII: (1) a "Show HN" post (honest, technical, no hype),
(2) a Product Hunt tagline + description, (3) a 90-second demo video script built
around the "unplug the internet and it still works" moment, (4) the one-line
positioning and three supporting bullets. Audience: privacy-conscious technical
users who already use Claude.
```

**Prompt 4B — pricing & open-core model [CW]**
```
Propose a pricing and open-core structure for UPII: what to open-source vs charge
for, three tiers (free / Pro / Team-Enterprise) with the feature split, price points
for the Indian + global market, and the rationale. Note the trade-offs (one-time vs
subscription) for a privacy-focused audience.
```

**Prompt 4C — architecture blog post [CW]**
```
Write a technical blog post explaining UPII's architecture for a developer audience:
the Context Gap problem, sovereign memory, content-addressed deterministic chunking,
multi-signal rehydration, attributed synthesis, and the MCP bridge to Claude. Make
the "verify, don't trust" open-core angle central. Confident, specific, no marketing fluff.
```

**Prompt 4D — landing page [CC]**
```
Build a single-file static landing page (HTML/CSS, no tracking, no external calls)
for UPII: hero with the positioning line, the 3 pillars (sovereignty, attribution,
multi-device), an MCP/"works with Claude" section, a waitlist email capture, and a
footer linking the OSS repo. Keep it fast and privacy-clean (no third-party scripts).
```

---

## One-page sequencing (how the three parts coexist)

| Horizon | Priority 1 (grant) | Priority 2 (pilot) | Priority 3 (bridge + GTM) |
|---|---|---|---|
| Months 1–6 | Phases 1–5 (build + prove) | Start customer interviews (2A/2B) | Reserve a few hrs/wk: positioning, blog draft |
| Months 7–9 | Phases 6–8 | Recruit design partners (2C) | Prototype MCP server (3A) once v1.0 nears |
| Months 10–12 | Phases 9–11 | Run pilot + report (2D) | Ship MCP bridge + gateway (3A/3B), launch assets (4A–4D) |
| Post-grant | Project closed | Convert partners to paying | Public launch, open-core, pricing live |

The discipline that makes this work: Priority 1 always wins a scheduling conflict. Priority 2 is cheap and feeds Priority 1's evidence. Priority 3 is where the company's long-term value is — but it only earns time once the grant deliverables are safe.
