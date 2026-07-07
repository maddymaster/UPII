# UPII — Product Requirements Document (PRD)

**Product:** UPII — Unified Personal Intelligence Interface
**Company:** DataFrontier Innovations Pvt Ltd
**Owner:** Madhusudhan
**Version:** 1.0 (PRD) · **Date:** 22 June 2026
**Status:** Living document

> One line: **UPII is a local-first, privacy-preserving memory substrate that gives AI your full context without your data ever leaving your device.**

---

## 1. TL;DR

Knowledge workers and regulated organisations face a forced trade-off: upload your entire digital brain (email, contracts, strategy, patient/customer data) to a third-party cloud to get useful AI, or keep your data private and settle for context-blind, generic AI. UPII removes the trade-off. It captures your documents, notes, calendar and mail, turns them into an addressable, queryable, reasoning-capable memory, and keeps the **entire loop — capture, embedding, retrieval, reasoning — on your own machine.** The cloud LLM becomes an optional, swappable accelerator, not a dependency.

UPII's wedge into the market is two-fold: a free local **engine** that earns developer/prosumer trust ("verify, don't trust"), and an enterprise **membrane** (selective disclosure + egress audit) that regulated buyers pay for because it's the only way they can legally adopt AI. We ride Claude/Cowork's adoption by exposing UPII as a local **MCP server** — the private memory those agents lack.

---

## 2. Problem

### The Context Gap
To make AI genuinely useful it needs your context. To get your context into mainstream AI you must surrender it to a provider's cloud — where it's embedded remotely, retained, and rented back to you. For three groups this is a non-starter:

- **Regulated industries** (BFSI, healthcare, legal, government) — compliance, data-residency (India's DPDP Act), and client confidentiality make "upload everything" illegal or contractually impossible.
- **Technology leaders / founders** handling sensitive partner, M&A, or strategy data — uploading is a competitive and legal risk.
- **Privacy-conscious professionals** — lawyers, accountants, advisors, researchers — whose work product *is* confidential by definition.

### Why existing tools don't solve it
Mainstream "second brain" and RAG products (Notion AI, mem.ai, Glean, ChatGPT memory) externalise the corpus, embed it remotely, and create vendor lock-in. They optimise for convenience at the cost of sovereignty. None can credibly say *"your corpus never leaves your device"* — it contradicts their business model. That structural gap is UPII's opening.

### Pain, quantified (validate in interviews)
- Regulated teams either ban cloud AI outright (lost productivity) or shadow-adopt it (compliance exposure).
- Professionals manually copy-paste sanitised snippets into ChatGPT — slow, lossy, and still leaky.
- "AI that forgets" — every session starts from zero context.

---

## 3. Target users (ICP & personas)

**Beachhead (start here):** high-context technical professionals and founders handling sensitive data — your own persona. Easiest to reach, sharpest pain, fastest feedback.

**Expansion ring 1:** regulated solo professionals — lawyers, chartered accountants, financial advisors, independent consultants.

**Expansion ring 2 (the revenue):** regulated *teams and enterprises* — BFSI (NBFCs, banks), healthcare networks, legal firms, climate/IP-heavy research orgs, government.

| Persona | Job-to-be-done | Why UPII |
|---|---|---|
| **"Sovereign Solo"** — founder/consultant/CTO | "Give me an AI that knows everything I've worked on, without me leaking it." | Local-first; ambient capture; cited recall; Cmd+K everywhere |
| **"Regulated Professional"** — lawyer/CA/advisor | "I can't put client files in the cloud, but I need AI leverage." | On-device by construction; attributed answers; audit trail |
| **"Compliance Buyer"** — CISO/DPO at a regulated org | "Let my people use AI without a data-residency breach." | Air-gapped deploy; egress audit log; redaction membrane; DPDP module |
| **"Agent Power-User"** — Claude/Cowork user | "I want my agent to know my context safely." | UPII MCP bridge: cited local memory, corpus never leaves device |

---

## 4. Value proposition

**Problem solved:** the Context Gap — the friction between data sovereignty and AI utility.

**Value created:**
- **For individuals:** cloud-grade recall and synthesis with zero privacy surrender; an AI that remembers everything you've touched and cites its sources.
- **For regulated orgs:** the ability to adopt AI *at all* without breaching compliance — UPII is often the difference between "AI banned" and "AI deployed."
- **For the ecosystem:** a trustworthy, auditable, open-core memory layer that any agent (Claude, Cowork, local models) can bind to.

**Positioning line:** *"AI that knows your context and keeps your secrets."*
**Demo moment:** *"Unplug the internet — it still works."*

**The three durable properties (and why they're a moat):**
1. **Sovereignty by construction** — local embeddings, on-disk vectors, local metadata source of truth. No corpus byte must leave the device. (Cloud incumbents can't copy this.)
2. **Verifiable memory** — every answer traced to source chunks via content-addressed IDs. Attributed, not just plausible.
3. **Graceful degradation** — reasoning is pluggable (local Ollama / optional Gemini / mock); retrieval still answers if inference is unavailable.

---

## 5. Goals & non-goals

**Goals (next 12 months)**
- Ship a trustworthy, fast (<300 ms P95 recall) local substrate on macOS + Windows (Linux stretch).
- Land 3 signed regulated-sector pilots and convert ≥1 to paid.
- Publish the UPII MCP server so Claude/Cowork users can adopt it in one step.
- File a provisional patent on the novel methods.
- Establish published, reproducible retrieval/citation benchmarks.

**Non-goals (explicitly out of scope — "Claude's turf")**
- Building a general agent framework, cloud compute, multimodal generation, or a large skills marketplace.
- Competing on raw retrieval-accuracy leaderboards. UPII's claim is *sovereign + governed + explainable + fast-enough*, not state-of-the-art accuracy.

---

## 6. Product scope

**Shipped today (v0.5 + v1.0):** document ingestion, semantic search, RAG Q&A, task extraction, diagnostics; ambient filesystem watcher; consent-gated source registry; staging DB + approval inbox; rule-based knowledge graph; multi-signal context rehydration (vector + temporal + entity) with explainable scoring; local metrics dashboard; voice-style drafting (beta); Cmd+Shift+K overlay; Mac/Windows builds.

**Near-term (v1.5 hardening + grant evidence):** overlay/onboarding polish, signed installers, inbox UX, abstention guardrail, and the **evidence harnesses** (benchmark, retrieval eval, entity eval, citation eval) the grant requires.

**Strategic (pull forward):** **MCP bridge** and the **egress/redaction membrane** (see strategy + reconciled prompt docs).

**Enterprise (v2.0):** email/Slack/Workspace/Notion connectors, multi-tenant isolation, SSO + RBAC, air-gapped deploy, DPDP residency module, third-party security audit.

> Full feature × version detail lives in the Version Roadmap; grant traceability in `CLAUDE_CODE_PROMPTS_v1.6_reconciled.md`.

---

## 7. Key user flows

1. **Capture:** user enables a source (consent) → ambient watcher stages new files → user reviews in inbox → approves → content enters durable memory + embeddings.
2. **Recall:** Cmd+Shift+K → type a question → cited answer in <300 ms P95, click-to-trace evidence inline.
3. **Synthesise:** `upii write "<topic>" --target email/linkedin` → draft in the user's own voice, grounded in their memory.
4. **Govern (enterprise):** any cloud-bound context passes the membrane → PII redacted → user approves what leaves → egress audit log records it.
5. **Agent bridge:** Claude/Cowork calls `upii_search` / `upii_ask` → receives only approved, cited local chunks → corpus stays on device.

---

## 8. Non-functional requirements

- **Privacy:** no corpus byte required to leave the device for core function; cloud is opt-in and gated by the membrane.
- **Performance:** recall P95 < 300 ms on reference hardware; ingestion throughput benchmarked and CI-gated against regression.
- **Determinism:** chunk hashes are a pure function of (content, config) — reproducible, attributable.
- **Security:** append-only tamper-evident egress log; air-gapped install with zero network calls; passes independent audit with no critical findings.
- **Reliability:** graceful degradation when no model/GPU/network; mock fallback always answers.
- **Compliance:** DPDP-aligned defaults (data minimisation, opt-in everything), configurable residency.

---

## 9. Success metrics

**North star:** weekly cited recalls per active user (proves the memory is actually used).

**Funnel / health (the only metrics that matter):**
- Activation: % who ingest their own corpus AND connect ≥2 sources.
- Engaged retention: week-4 retention; recall queries per active user per week.
- Multi-device adoption.
- Willingness to pay: paid pilot / pre-order / signed LOI.

**Commercial:** enterprise ACV × logo count; net revenue retention.

---

## 10. Go-to-market plan

### 10.1 Strategy in one paragraph
Win trust at the bottom with a free, open-core, local engine and an MCP bridge that rides Claude's distribution; monetise at the top with regulated-enterprise compliance deals where the egress audit + redaction membrane is the line item buyers sign for. Beachhead → regulated solos → regulated teams.

### 10.2 Three coordinated motions
1. **PLG / community (top of funnel):** publish the MCP server to the Claude/Cowork directory; launch on Show HN, Product Hunt, r/LocalLLaMA, r/privacy, PKM communities. Free local core removes all adoption friction.
2. **Content / credibility (middle):** an architecture blog post (sovereign memory, deterministic chunking, attributed retrieval, the membrane) — your CTO credibility carries it. A 90-second "unplug the internet" demo video.
3. **Design-partner → enterprise (bottom, the revenue):** convert pilots to paid using the egress audit log + threat model + independent security review as the enterprise sales kit.

### 10.3 How to get the first 10 customers (concrete)
1. **Start with your own network.** You're the persona. List 20–30 founders/CTOs/regulated professionals you know personally. Run problem-validation interviews (not pitches) — confirm the "can't use cloud AI" pain and willingness to pay before building more.
2. **Run a 5–10 person design-partner pilot.** Offer 4 weeks free access in exchange for usage + a testimonial; data stays on their device. One-page plain-English agreement, onboarding checklist, weekly check-in. This *is* your Tranche-2 grant evidence too — double-counted work.
3. **Land 3 regulated-sector pilots as signed contracts, not POCs.** Target a mid-size NBFC (BFSI), a Bengaluru hospital network (healthcare), and a climate/IP research lab. Lead with: "deploy AI without a DPDP breach." Tie payment milestones to deployment.
4. **Use the MCP listing as inbound.** Every Claude/Cowork user searching for "memory" or "private context" is a warm lead. Instrument opt-in local analytics to see activation.
5. **Publish to seed credibility.** The benchmark numbers + architecture post + open-core repo turn cold outreach warm. "Verify, don't trust" is a developer-trust magnet.
6. **Convert.** Target ≥1–2 paid conversions or signed LOIs from the pilot cohort. A named org + named sponsor + named success criteria is what unlocks the next raise.

### 10.4 What makes them pay (recap)
Free core drives adoption; **multi-device sync + connectors (Pro)** and **air-gapped + audit + compliance (Enterprise)** convert. The enterprise membrane is the difference between "AI banned" and "AI deployed" — that's worth a contract, not a coffee.

---

## 11. Landing page specification

**Goal:** convert privacy-conscious technical users to a waitlist/download, and regulated buyers to a "book a pilot" call. Fast, no third-party trackers (the privacy story must hold on your own site).

**Section-by-section:**

1. **Hero**
   - Headline: **"AI that knows your context and keeps your secrets."**
   - Sub: "UPII is a local-first memory for your documents, notes, calendar and mail. Cloud-grade recall and synthesis — without a single byte leaving your device."
   - Primary CTA: **Download free** (or **Join the waitlist**). Secondary CTA: **Book a pilot** (enterprise).
   - Visual: the Cmd+K overlay returning a cited answer.

2. **The "unplug the internet" proof** — a short looping demo/GIF: ask a question with Wi-Fi off, get a cited answer. One line: *"No cloud. No account. No corpus leaving your laptop."*

3. **The problem (the Context Gap)** — three cards: "Cloud AI wants all your data," "Local tools forget everything," "Regulated work can't use either." Tension stated crisply.

4. **The three pillars** — Sovereignty (your data never leaves), Attribution (every answer cites its source), Multi-device (your memory on laptop + phone, peer-to-peer, no cloud).

5. **How it works** — 4 steps with icons: Connect a folder → Review what's captured (consent) → Ask anything → Get cited answers. Reinforce "you approve everything."

6. **Works with Claude (the bridge)** — "Add UPII to Claude or Cowork in one step. Your agent gets your context; your corpus stays on your device." Link to MCP listing. This section captures the agent crowd.

7. **For regulated teams** — the enterprise band: air-gapped deploy, egress audit log, redaction membrane, DPDP residency, RBAC/SSO, third-party security audit. CTA: **Book a pilot**. (This is where ACV comes from — give it real estate.)

8. **Trust / "verify, don't trust"** — open-core repo link, "what never leaves your device" plain-English statement, benchmark numbers (recall %, P95 latency), security-audit badge when available.

9. **Pricing** — the three-tier table (below). Transparent.

10. **Social proof** — pilot testimonials, logos (once permitted), "as used at [Ambee CTO desk]".

11. **FAQ** — "Is my data really local?", "What happens if I have no GPU?", "Does it work offline?", "How is this different from Notion AI / ChatGPT memory?", "DPDP compliance?".

12. **Footer CTA + waitlist email capture** — repeat primary CTA; link OSS repo, docs, privacy policy.

**Copy principles:** honest, technical, no hype. Lead with sovereignty + attribution. Let the "unplug the internet" moment do the emotional work.

---

## 12. Pricing

### 12.1 Model
**Open-core + freemium PLG at the bottom, sales-led enterprise at the top.** The engine is free and open (trust + adoption); value-added capabilities and compliance controls are paid.

### 12.2 Tiers

| Tier | Audience | Includes | Price (global) | Price (India) |
|---|---|---|---|---|
| **Free / Core (OSS)** | Privacy/PKM/dev community, solo self-use | Local engine: ingest, search, ask, tasks, KG, rehydration, Cmd+K, single device. MIT-licensed core. | $0 | ₹0 |
| **Pro** | Technical pros, founders, regulated solos | Multi-device LAN sync, polished connectors, MCP bridge polish, voice-style drafting, priority builds | **$12–19 / mo** (annual discount) | **₹799–1,499 / mo** |
| **Team** | Small regulated teams (3–25 seats) | Everything in Pro + shared workspace isolation, RBAC, basic audit export, email support | **$25–40 / seat / mo** | **₹1,999–3,499 / seat / mo** |
| **Enterprise** | Regulated orgs (BFSI/health/legal/gov) | Air-gapped on-prem, egress audit log, redaction membrane, DPDP residency module, SSO/SAML, admin console, security-audit report, SLA + indemnification | **Custom: $25k–100k+ / yr ACV** | **₹20L–80L+ / yr** |
| **Developer SDK** | Builders embedding UPII | Python + REST API, plugin retrievers | **₹499 / mo / dev** (≈ $6) | ₹499 / mo / dev |

> Karnataka-registered AI startups: free SDK access (community commitment).

### 12.3 What to price on (and why)
- **Pro/Team:** price on *capability* (sync, connectors, agent bridge) — clear, predictable, low-friction for PLG.
- **Enterprise:** price on *value and risk reduction*, not seats alone. The buyer is purchasing the ability to use AI without a compliance breach + an auditor-ready trail. Anchor on the cost of the alternative (a data-residency violation, or AI banned entirely). Land at $25k–50k for the first logos to build references, expand to $100k+ as the compliance suite deepens.
- **Avoid** per-query/usage metering at the core — it fights the "local, yours, unlimited" story. Meter only optional cloud-accelerated reasoning if at all.

### 12.4 Packaging logic
Free core maximises adoption and credibility (and is your open-core moat-strengthener, not a revenue leak — enterprise pays for connectors + multi-tenant + audit + SLA + indemnification, which OSS doesn't threaten). Pro funds the funnel and proves PLG to investors. **Enterprise is where the $1M+ comes from** — 10–20 logos at $50k–100k ACV.

---

## 13. Risks & mitigations

| Risk | Mitigation |
|---|---|
| **Grant milestone drift** (roadmap vs signed MoA) | Reconcile per `CLAUDE_CODE_PROMPTS_v1.6_reconciled.md`; produce evidence harnesses on the MoA's Tranche-1 schedule |
| Overlay daemon instability on new macOS/Windows | Fallback CLI-only mode pilots can run |
| Open-core cannibalising enterprise | Differentiator is connectors + multi-tenant + audit + SLA + indemnification, not the engine |
| Benchmark numbers underwhelm | Publish honestly; the claim is sovereign + governed + explainable + fast-enough, not SOTA accuracy |
| Long enterprise sales cycles | Run prosumer PLG in parallel for cash + signal; use design-partner pilots to shorten trust-building |
| DPDP interpretation drift | Conservative defaults; monthly DPO review |

---

## 14. Milestones (next 12 months, abbreviated)

- **M0–4 (v1.5):** hardening + grant evidence harnesses + signed installers + MCP bridge MVP + provisional patent + 20–30 validation interviews.
- **M4–8 (v2.0):** enterprise connectors, multi-tenant, air-gapped deploy, security audit, **3 signed pilots**, multi-device LAN sync.
- **M8–12 (v3.0):** published benchmarks, open-core MIT release, SDK, control plane, **convert pilots → paid + LOIs** → seed raise.

---

*Companion docs: `STRATEGY_grant_and_gtm.md` (strategy), `CLAUDE_CODE_PROMPTS_v1.6_reconciled.md` (build prompts + grant traceability), Version Roadmap (v0.5→v3.0), ELEVATE Nxt Annexure-1 Tranche Plan.*
