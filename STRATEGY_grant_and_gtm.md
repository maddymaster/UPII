# UPII — Grant Compliance + Go-to-Market + Growth Plan

**Prepared for:** Madhusudhan / DataFrontier Innovations Pvt Ltd
**Date:** 22 June 2026
**Scope:** What to build to stay compliant with the ELEVATE Nxt milestones, what gives UPII a defensible edge, what makes customers pay, and a 24-month path to traction → VC funding → scale.

---

## 1. Where UPII actually stands today (honest read)

The **substrate is largely built.** The codebase has working ingestion, deterministic chunker, local embeddings, LanceDB vector store, SQLite metadata, multi-signal rehydration, search, rule-based entity extraction, pluggable LLM (Ollama/Gemini/mock), ambient calendar + email connectors, a consent/approval inbox, a Cmd+K overlay daemon, and 12 CLI commands (`doctor, ingest, search, ask, sources, tasks, watch, inbox, knowledge, metrics, write, demo`). 57 tests exist.

**The gap is not the engine — it's the *evidence layer* and the *moat layer*.** Specifically:

- **Missing the measurement/benchmark/eval harnesses** that the grant literally requires as "Completion Demonstration." There is no `scripts/bench/`, no `eval/`, no `scripts/demo/`, no committed `REPORT.md` artifacts. You have the capability but not the proof.
- **Missing the GTM moat pieces:** no MCP server (the Claude/Cowork memory-bridge), no egress/redaction membrane, no multi-device sync, no signed installers.
- **Provisional patent** not yet filed (Tranche-1 milestone, own-funds).

Translation: you are closer to grant compliance than it looks, because most milestones are demonstrations of things the code already does — you mainly need to **build the harnesses that produce the reports and recordings.**

---

## 2. Grant compliance — the must-do list (in milestone order)

> Principle baked into your Annexure-1: each milestone only commits to *"establish a baseline and demonstrate measurable improvement."* Build to ambitious internal targets, **report against the conservative baseline wording.** A missed number can't breach the MoA.

### TRANCHE 1 (Months 1–6)

**T1.1 — R&D infra + performance baseline**
- [ ] Build `scripts/bench/make_corpus.py` (deterministic synthetic corpus generator).
- [ ] Build `scripts/bench/benchmark.py` + `upii bench` command → outputs `bench/results/REPORT.md` (ingestion docs/min, p50/p90/p99 retrieval latency).
- [ ] **Business:** procure Mac Studio M3 Ultra + dev/test fleet; keep original invoices in company name. Run the benchmark *on that hardware* — that's the artifact.

**T1.2 — Harden content-addressed ingestion + deterministic chunking**
- [ ] `tests/test_chunk_determinism.py` (identical hashes on re-ingest + shuffled file order).
- [ ] `scripts/bench/scale_check.py` driving a large corpus through ingest → re-ingest (no-ops) → edits → deletes; emit `scale_REPORT.md`.
- [ ] `scripts/demo/repro_demo.sh` — clean, recordable terminal demo of reproducible hashes.

**T1.3 — Context Rehydrator v2 (eval baseline)**
- [ ] `eval/` labelled dataset + `eval/run_eval.py` (Recall@k, MRR, nDCG) → `eval/results/REPORT.md`.
- [ ] Add `upii ask --debug` showing each signal's (semantic/temporal/relational) contribution.
- [ ] Report **fusion vs semantic-only** improvement (that delta IS the milestone).

**T1.4 — Local knowledge-graph extraction**
- [ ] `eval/run_entity_eval.py` over a labelled fixture → `entity_REPORT.md` (precision/recall/F1).
- [ ] `upii knowledge --graph --out graph.html` (self-contained, no cloud) — the visualization artifact.

**T1.4b — Provisional patent (non-code, own funds)**
- [ ] Draft invention disclosure: sovereign multi-signal context rehydration + attributed on-device memory + the redaction/egress membrane. File **before** any public pilot to lock priority. Claim cost under Karnataka Startup Policy, not the grant.

**T1.5 — Tranche-1 review & reporting**
- [ ] `docs/tranche1_completion_report.md` linking each milestone → artifact → headline number + plain-English summary for the KITS reviewer. Demo video.
- [ ] **Business:** CA-attested Utilisation Certificate, audited expenditure, No-Lien statement.

### TRANCHE 2 (Months 7–12)

**T2.1 — Ambient connectors (mail + calendar), consent-gated**
- [ ] Harden both connectors (robust .ics / .mbox/.eml parsing, sensitive-field minimisation); ensure everything routes staging → approval inbox, never directly to durable memory.
- [ ] Isolation test proving nothing reaches `upii.db` pre-approval; `scripts/demo/ambient_demo.sh` recording the consent→capture→inbox→approve loop.

**T2.2 — Attributed synthesis + answer verification**
- [ ] `eval/run_citation_eval.py` (citation accuracy) → `citation_REPORT.md`.
- [ ] Abstain/flag guardrail when retrieval confidence is low (no hallucinated citations).
- [ ] `upii ask --engine {local,remote,mock}` + `--compare` for side-by-side local vs remote.

**T2.3 — Cross-platform packaged release v1.0**
- [ ] PyInstaller builds via GitHub Actions matrix (mac/win/linux); **signed + notarised** (your certs).
- [ ] `upii doctor` as clean-machine PASS/FAIL acceptance check; demonstrate clean install on ≥2 OSes; tag v1.0.

**T2.4 — Multi-device sync (laptop + phone + iPad)** ← *biggest architectural lift; start the ADR in Month 7*
- [ ] Design as a **local-network personal hub** (one canonical device; phone/iPad query over LAN or hold an encrypted P2P replica). Nothing transits a third-party cloud.
- [ ] Demonstrate a laptop-captured memory retrieved on phone/iPad over LAN; on-device mobile *retrieval* (mobile generative inference is an explicit *stretch* goal — don't over-commit).

**T2.5 — Design-partner pilot**
- [ ] 5–10 pilot users for ≥4 weeks; local/privacy-preserving usage metrics (active users, queries, latency); ≥3 testimonials; `docs/pilot_report.md` (doubles as the Tranche-2 demonstration).

**T2.6 — Project closure**
- [ ] Final completion report, CA-attested UC, audited expenditure; ₹1,00,000 own-funds through No-Lien account; ₹25,000 earmarked to K-tech Innovation Hub.

**Compliance guardrails (don't trip these):** all spend from the No-Lien account only; respect cost-head caps (R&D ≥40%, Outsourcing ≤20%, Salaries ≤20%, Admin ≤10%, Marketing ≤10%; hardware ≤60% of R&D capex); no founder drawing >₹50k/mo from grant; patent + the prohibited categories (vehicles, furniture, travel, etc.) not charged to grant; any tranche-plan deviation needs written Review-Committee approval first.

---

## 3. The edge — what makes UPII defensible

The grant builds the product. **These five things build the moat.** Notably, three of them are *not* in the grant scope — which is exactly why they're your differentiation, not table stakes.

1. **Sovereignty by construction (architectural moat).** Cloud incumbents (OpenAI, Notion, Glean, mem.ai) cannot credibly retrofit "your data never leaves the device" — it contradicts their business model. You own a position they structurally can't copy.
2. **The Membrane — selective-disclosure + egress audit (compliance moat, your real enterprise wedge).** A gateway that detects/redacts PII before anything crosses to a cloud model, shows the user exactly what's about to leave, requires approval, and writes a tamper-evident egress audit log (`upii egress log`). *This is the feature regulated buyers sign contracts for.* **Build this even though it's not a grant milestone.**
3. **MCP memory-bridge — "be the memory and the membrane" for Claude/Cowork (distribution moat).** Expose UPII as an MCP server: `upii_search`, `upii_ask`, `upii_list_sources` return only user-approved, cited chunks — the corpus never leaves the device. Every Claude/Cowork user becomes a potential UPII user. **This is the single highest-leverage non-grant item.** It rides Claude's adoption instead of fighting it.
4. **Verifiable / attributed memory (trust moat).** Content-addressed chunks + citations + deterministic reproducibility = "verify, don't trust." This is your open-core credibility and your enterprise audit story.
5. **Provisional patent on multi-signal rehydration (legal moat).** Priority date on the novel method before launch.

**Don't build** (Claude's turf, money pit): cloud compute, a general agent framework, multimodal generation, a big skills marketplace. Stay the *memory + membrane*.

---

## 4. What makes customers pay

Free local core gets adoption; **these three convert to revenue:**

| Tier | Who | What they pay for | Indicative price |
|------|-----|-------------------|------------------|
| **Free / OSS core** | Privacy/PKM/dev community | The engine, local-only, "verify don't trust" — drives adoption + credibility | ₹0 |
| **Pro (prosumer)** | Technical pros, founders, consultants handling sensitive data | Multi-device sync, polished connectors, Cmd+K everywhere, MCP bridge polish | ~$10–20/mo (₹800–1,600) |
| **Team / Enterprise** | **Regulated buyers: legal, finance/accounting, healthcare, govt/defence, IP-heavy firms** | On-prem/admin, the **egress audit + redaction membrane**, compliance reporting, DPDP/data-residency posture | $25k–100k+/yr ACV |

**The money is in Tier 3.** Prosumer Pro funds the funnel and tells the PLG story; **regulated-enterprise compliance deals are how you reach $10M fastest** (10–20 logos at $50k–100k ACV ≈ $1M; the membrane + egress audit is the line item they buy). India's DPDP Act is a tailwind — "rethink your AI architecture for data sovereignty" is a live enterprise pain right now.

**Willingness-to-pay test (do this during the pilot):** activation (% who ingest their own corpus + connect ≥2 sources), week-4 retention, queries/active-user/week, and a signed LOI or paid conversion from ≥1 design partner. Vanity downloads don't count.

---

## 5. Go-to-market motion

**Beachhead → expand:** start with **high-context technical professionals / founders handling sensitive data** (your own persona — easiest to reach, sharpest pain), then expand to **regulated solos** (lawyers, accountants, advisors), then land **regulated teams/enterprises**.

**Three coordinated motions:**
1. **PLG / community (top of funnel):** publish the MCP server to the Claude/Cowork directory; Show HN, Product Hunt, r/LocalLLaMA, r/privacy, PKM communities. The demo moment: *"unplug the internet — it still works."*
2. **Content / credibility:** architecture blog post (sovereign memory, deterministic chunking, attributed retrieval, the membrane) — your CTO credibility carries it. One-line positioning: **"AI that knows your context and keeps your secrets."**
3. **Design-partner → enterprise (bottom of funnel, the revenue):** convert pilots to paid; use the egress audit log + threat model + independent security review as the enterprise sales kit.

**GTM checklist:** open-core license decision (e.g. Apache-2.0 core); signed installers; MCP listing; landing page + waitlist + 90s demo video; privacy policy + plain-English "what never leaves your device"; pricing tiers live; billing infra (Stripe/Paddle/Lemon Squeezy); support channel; opt-in local-first analytics.

---

## 6. The 24-month plan: traction → VC → scale

### A candid word on "$10M in 24 months"
Be precise about which $10M. **$10M ARR in 24 months** for a privacy-first, local-first tool is top-decile-outlier territory and shouldn't be the plan of record. The realistic, fundable shape is:

- **$10M *raised*** (Seed → Series A) — very achievable with the right traction signals.
- **~$1–3M ARR by Month 24** with a *credible, evidenced path to $10M* — this is what unlocks the Series A and what you should engineer toward.

Both interpretations point to the same operational plan below; the difference is honesty in the pitch.

### Phased plan

**Phase A — Months 0–6 (grant T1 + foundations).** Ship the benchmark/eval/entity harnesses (compliance) and *in parallel, a few hours/week*, build the MCP bridge MVP and start the membrane. File the provisional patent. Begin 20–30 problem-validation interviews. **Exit:** Tranche-1 cleared; MCP server in private beta; patent filed; pain + WTP confirmed for the beachhead.

**Phase B — Months 6–12 (grant T2 + first revenue).** Ship v1.0 signed installers, attributed synthesis + abstention, ambient connectors, multi-device sync. Publish the MCP server publicly. Run the 5–10 design-partner pilot; convert ≥1–2 to paid; capture testimonials. **Exit:** Tranche-2 cleared; v1.0 + MCP live; first paying customers; `pilot_report.md` (doubles as grant evidence *and* investor proof).

**Phase C — Months 12–18 (raise).** Use grant completion + pilot conversions + MCP adoption metrics as the **pre-seed/seed deck**. Story: "the sovereign memory layer for AI — the memory and the membrane Claude lacks, sold to buyers who legally can't use the cloud." Target a **seed round ($1.5–4M)** to hire 3–5 (sales + 2 eng + GTM). Stand up the enterprise compliance offering (egress audit, on-prem, security review). **Exit:** seed closed; first 3–5 enterprise logos in pipeline.

**Phase D — Months 18–24 (scale to the Series-A signal).** Land 10–20 regulated-enterprise logos at $50k–100k ACV; grow prosumer Pro via the MCP funnel. Reach **~$1–3M ARR with strong net retention.** That metric set + DPDP/data-sovereignty tailwind + a defensible patent = the **Series A ($6–10M)** that funds the actual scale to $10M ARR beyond Month 24. **Exit:** Series A raised / $10M milestone in sight.

### The four metrics that decide everything
Activation, week-4 retention, enterprise ACV × logo count, and net revenue retention. Everything else is noise.

---

## 7. Immediate next 30 days (do these first)

1. **Build the evidence harnesses** (`bench/`, `eval/`, entity eval, `repro_demo.sh`) — unblocks 4 of 5 Tranche-1 milestones from code you already have.
2. **Draft + file the provisional patent** (own funds) — lock priority before any public move.
3. **Stand up the MCP server MVP** — your single highest-leverage GTM bet; get it ready to list.
4. **Start 20–30 validation interviews** with the beachhead — cheap, shapes everything, and feeds the pilot.
5. **Specify the Membrane** (redaction + egress audit) — your enterprise wedge; write the ADR now even if you build it in Phase B.

---

*Sources: ELEVATE Nxt Annexure-1 Tranche Plan (DataFrontier Innovations); Milestone_Build_Plan_and_ClaudeCode_Prompts.md; UPII codebase (src/upii, tests/, .github/workflows) and project_docs/ as of 22 Jun 2026.*
