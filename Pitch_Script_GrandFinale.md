# UPII · Grand Finale Pitch Script

**Event:** Karnataka Startup Grand Finale · ELEVATE NxT DeepTech · June 2026
**Application:** ELNXT20260000020 · Panel: AI-ML / Health / Bio / Life Sciences
**Company:** DataFrontier Innovation Pvt Ltd · Bengaluru
**Presenters:** Veenadhari Pola (Founder & CEO) · Madhusudhan Anand (Co-Founder & CTO)
**Target runtime:** 7 minutes 45 seconds (pitch) + Q&A
**Deck:** DataFrontier_UPII_GrandFinale_Deck.pptx (15 slides)

---

## How this script earns each evaluation rubric

Karnataka Startup Cell / ELEVATE NxT DeepTech finals are scored on six axes. Each is hit explicitly, in this order, so the jury's scoring card fills itself:

| Rubric | Weight (typical) | Slides that land it |
|---|---|---|
| Innovation & R&D depth | ~25% | S2, S5, S6, S7 |
| Market potential & commercialisation | ~20% | S9, S10 |
| Scalability & defensibility | ~15% | S4, S8, S10 |
| Team capability | ~15% | S12 |
| Socio-economic impact & Karnataka angle | ~15% | S11 |
| Financial planning & milestones | ~10% | S13 |

Closing argument (S14) re-states *timing*, *foundation*, and *founder-market fit* — three lines that map back onto the rubric in case the jury wants to anchor on a single sentence.

---

## Pre-pitch checklist (the 5 minutes before going on stage)

- Laptop on AC power. Display mirroring tested. Resolution locked at 1920×1080.
- `demo.mp4` cued on slide 6, audio off (Maddy narrates over it live).
- Fallback: Terminal pre-warmed with `upii doctor`, `upii ingest`, `upii ask`, `upii audit` history — if the video fails, run the live CLI sequence in the same order.
- Veena holds the clicker. Maddy holds the laser pointer.
- Phones on airplane mode. Slack quit. Notifications off.
- Water glasses on the podium. Names written in marker on the back of each card.

---

## SLIDE 1 · Cover (10 sec) — VEENA

> *(Walking on, clicker in hand, calm. Wait for the introducer to finish. Make eye contact with the panel chair, then begin.)*

"Honourable jury members, good morning. I am Veenadhari Pola, Founder and CEO of DataFrontier Innovation. With me is my co-founder and CTO, Madhusudhan Anand. We are here from Bengaluru with **UPII — the Sovereign Memory Engine for Indian AI.** Private. On-device. Auditable. Reversible. In seven minutes, we will show you why this is the missing layer in India's sovereign AI stack — and why ₹1 crore from ELEVATE NxT compounds into a category-defining outcome."

**Cue:** Advance to S2 on the word *compounds*.

---

## SLIDE 2 · Progress since 11 May submission (25 sec) — VEENA

> *(Tone: matter-of-fact. This slide buys credibility for the rest of the pitch.)*

"Since our submission on the eleventh of May — fifteen days ago — we did not write a new deck. We shipped three new capabilities. **Ambient memory with inbox review** — nothing reaches long-term memory until the operator signs off. **Knowledge-graph recall with per-result reasoning** — every answer is traceable. **Local metrics with one-command audit export** — DPOs can self-audit without any data leaving the machine. All three are live and demoable. Today, UPII is in **daily production use at the Ambee CTO desk**, with **five active pilot conversations** in progress."

**Numbers to land hard:** *15 days*, *3 capabilities*, *5 pilots*.

**Cue:** Advance on the word *progress*.

---

## SLIDE 3 · The Problem (40 sec) — VEENA

> *(Slow down. This is the asymmetric-information slide — most of the jury has not heard this framed sharply before.)*

"There is a dirty secret in Indian enterprise AI that nobody is talking about. **Today, zero rupees of India's regulated enterprise knowledge can safely meet an AI model.** Not because the technology doesn't exist — because the architecture is wrong. Hospitals, banks, defence PSUs, government bodies, research labs — they all face a binary choice. **Upload everything to a foreign hyperscaler, or use AI that knows nothing about them.** Models forget every conversation. Cloud RAG forces data egress to US servers. And the DPDP Act, the RBI sectoral guidance, the defence MoUs — none of them permit blanket upload. So adoption stalls in compliance review. The Context Gap is the binding constraint on regulated AI in India."

**Numbers to land hard:** *₹0*, *DPDP Act 2023*.

**Cue:** Pause one full beat after *Context Gap*. Then advance.

---

## SLIDE 4 · The Solution (35 sec) — VEENA, hand-off to MADDY

> *(Tone shift: confident, declarative.)*

"UPII closes that gap. It is a **local-first memory substrate** that indexes your digital life — documents, meetings, calendars, emails — and serves that context to any LLM, **fully on-device**. Three guarantees: **zero privacy risk** — data never leaves the machine. **Sub-300 millisecond recall** on commodity CPU — no GPU required. **Zero LLM lock-in** — Ollama, Gemini, GPT, Claude, drop in any backend. To show you this is real engineering and not a pitch deck, I'll hand to our CTO and the architect of UPII — Madhusudhan."

**Cue:** Step back half a pace. Maddy steps forward as the slide advances.

---

## SLIDE 5 · What we shipped (35 sec) — MADDY

> *(Take the clicker. Look at the slide for one beat, then at the jury. Engineer-confident, not salesy.)*

"Thank you, Veena. Three capabilities, live today, each built from direct pilot feedback. **Governance** — ambient memory plus an approve-to-promote inbox. Nothing is committed without an operator decision. **Recall** — three retrievers running in parallel: vector, temporal, and knowledge-graph — and every result carries its boost reason, so the answer is always defensible. **Transparency** — a local seven-day metrics dashboard, plus a one-command JSON export of all UPII activity. That single command — `upii metrics export` — is what makes UPII auditable by a CISO without ever moving raw data. Each of these has a live CLI command. Let me show you one."

**Cue:** On the word *show*, advance to the demo slide.

---

## SLIDE 6 · Live Demo (90 sec video + 15 sec framing) — MADDY

> *(Before pressing play: 5 seconds of framing.)*

"Ninety seconds. Watch six things happen — fully offline. **Doctor**, **ingest**, **ask**, **synthesise**, **honest 'I don't know'**, and **audit the answer**."

> *(Press play on demo.mp4. Stay silent through the video. When it ends, 10 seconds of close:)*

"That last frame — *Boost reason: temporal plus entity* — is the line that DPOs and CISOs care about. UPII does not just answer. **UPII shows its work.** And it ran on the laptop in front of you, with no network."

**Fallback if video fails:** Open Terminal, run the four-command sequence in the same order. Same script. Do not apologise — narrate calmly.

**Cue:** Advance.

---

## SLIDE 7 · Architecture & Benchmarks (40 sec) — MADDY

> *(This is the technical-depth slide. The jury will include academics from IISc / IIITB. Speak to them.)*

"Three-layer architecture, every layer independently evaluated. **Ingestion** — recursive semantic chunking with content-hash dedup and per-chunk provenance. **Hybrid storage** — SQLite for metadata, LanceDB columnar for vectors, memory-mapped, no RAM blow-up. **Context Rehydration** — our core IP — three parallel retrievers, scored and explained. Measured on the real Ambee pilot corpus — NASA PACE meeting notes, ICEYE SAR terms, internal roadmap, confidential tasking coordinates. **Ninety-one percent top-three retrieval accuracy. Sub-300-millisecond P95 latency. Twenty-two-million-parameter embedder running CPU-only. Minimum hardware: a forty-thousand-rupee laptop.** That is the deeptech contribution."

**Numbers to land hard:** *91%*, *<300ms*, *22M params*, *₹40K laptop*. Slow down on each.

**Cue:** Advance on the phrase *deeptech contribution*.

---

## SLIDE 8 · Validation & Pipeline (35 sec) — MADDY, hand-off to VEENA

> *(Body language: lean slightly forward. This is the credibility slide.)*

"We are not pitching a pitch deck. UPII is in **daily production use at Ambee** — an environmental-intelligence company partnered with NASA, ESA, and ICEYE. The same operator is the CTO and the UPII architect — that is a zero-latency feedback loop. Measured outcome at that desk: **two to three hours per week recovered on context retrieval.** Beyond Ambee, we are in active pilot conversations with five organisations spanning **BFSI, healthcare, climate-tech research, a PSU-linked think tank, and a Bengaluru deeptech SDK partner.** Names withheld pending pilot agreements — references available on jury request. Veena will take you through the market."

**Cue:** Hand the clicker back. Step back. Veena steps forward.

---

## SLIDE 9 · Market (30 sec) — VEENA

> *(Tone: composed, structural.)*

"We are not chasing every AI buyer. We are going where cloud RAG cannot legally go. **Total addressable market by 2028 — two hundred billion dollars** in global AI infrastructure spend. **Serviceable addressable market by 2027 — eighteen billion** in the trustworthy, explainable, governed AI sub-segment. **Our beachhead, year one to three — five hundred crores** in Indian regulated enterprise AI infrastructure, addressable from Bengaluru. Against Mem, Notion AI, Microsoft Copilot, Pinecone, Weaviate — every competitor has at least one disqualifying property in regulated India: cloud tenancy, data egress, no governance, or no audit. **UPII is the only local, governed, explainable option.**"

**Numbers to land hard:** *$200B*, *$18B*, *₹500 Cr*.

**Cue:** Advance.

---

## SLIDE 10 · Business Model (30 sec) — VEENA

> *(Crisp. The jury wants to see this is a real business, not a research project.)*

"Open core. Enterprise license. Developer SDK. **Enterprise on-prem deploy: fifteen to fifty lakhs per year** — air-gapped, SLA-backed, SSO, audit logs. **Developer SDK: four hundred ninety-nine rupees per month per developer.** Open-core MIT engine drives community adoption. The pricing logic is simple — UPII is **risk infrastructure, not discretionary software.** A single DPDP-flagged breach costs an Indian BFSI firm one crore plus in fines and remediation. **UPII Enterprise is five percent of that risk exposure, annually.** Enterprise LTV: **seven to ten crores.** And once memory is embedded, switching out means losing audit-trail continuity. High stickiness, structurally."

**Numbers to land hard:** *₹15–50L/year*, *₹1 Cr+ breach cost*, *5% of risk*, *₹7–10 Cr LTV*.

**Cue:** Advance.

---

## SLIDE 11 · Socio-Economic Impact (35 sec) — VEENA

> *(This is the Karnataka jury slide. Earn it — do not pander. Slow down, look at the K-Tech / KITS officials specifically.)*

"Four impact vectors, every one aligned with the state's deeptech mandate. **Data sovereignty** — Indian enterprise and citizen data never leaves Indian soil, DPDP-ready for Karnataka government workloads. **Democratised AI access** — UPII runs on a forty-thousand-rupee CPU laptop, no GPU, no cloud bill, meaning SMEs, district offices, and primary care centres can run private AI. **Karnataka talent engine** — five-plus engineering hires recruited from IISc, IIITB, PES, BMSCE, RVCE. Not support roles. Core ML and infra. **Open core for Karnataka** — MIT-licensed engine, free for any Bengaluru AI startup to embed. Twelve-month projection: **five jobs, five pilots, one research paper, one open-core release.** Built in Bengaluru, for India, for the world."

**Cue:** One full beat of silence. Advance.

---

## SLIDE 12 · Team (25 sec) — VEENA

> *(Brisk. The credentials do the work.)*

"Seven-plus engineers. Three decades of combined enterprise AI and infrastructure experience. Myself — seventeen years in enterprise technology, owning product, GTM, and regulator relationships. **Madhusudhan — CTO at Ambee, scaled product to several million dollars ARR, BITS Pilani, IIIT Bangalore, granted patents in data systems and indexing — architect of the UPII core engine.** **Dr. Chaitra C R — PhD in computer science from BITS Pilani Hyderabad, five peer-reviewed papers at ACL, ECIR, Springer venues — leads our AI research.** Plus two ML engineers, two backend engineers, one research intern."

**Cue:** Advance.

---

## SLIDE 13 · The Grant Ask (40 sec) — VEENA

> *(Slow down. This is the slide the jury scores against the rubric.)*

"**One crore. Twelve months. Three milestones. Five pilots.** ELEVATE NxT's minimum forty-percent R&D allocation, respected. **Milestone One, months zero to four** — Cmd-Shift-K Spotlight-for-AI overlay, harden ambient sources, TRL four to five. **Milestone Two, months four to eight** — secure connectors for Email, Slack, Google Workspace, Notion, three regulated-sector pilots signed, TRL five-plus. **Milestone Three, months eight to twelve** — formal NDCG and precision-at-k benchmarking, research paper submitted, five enterprise LOIs converted, TRL six. Budget: **forty percent R&D, twenty percent engineering salaries, fifteen percent security audit and UI-UX, ten percent marketing, ten percent admin and infrastructure, five percent research and contingency.** Every line is tied to a deliverable."

**Numbers to land hard:** *₹1 Cr*, *12 months*, *5 pilots*, *40% R&D*, *TRL 4→6*.

**Cue:** Pause two beats. Then advance.

---

## SLIDE 14 · Closing Argument (35 sec) — VEENA

> *(Eye contact with the panel chair. This is the line they will write down.)*

"Three reasons to fund this today. **One — timing.** The DPDP Act enforcement window is opening in 2026. Every regulated Indian enterprise is being forced to re-architect its data and AI stack. The next twelve months decide who owns the sovereign-AI-memory category. **Two — foundation.** This is not a slide deck. UPII has eighteen test suites, a CI/CD pipeline, Mac and Windows release artefacts, a working overlay daemon, and it runs in daily production at Ambee. The R&D risk is already retired. **Three — founder-market fit.** Madhusudhan is simultaneously the architect and a user of UPII — from the CTO desk of a company that handles classified satellite tasking. Zero-latency feedback. The category will be defined in the next twelve months. **We are asking for the rupees to define it from Karnataka.**"

**Cue:** Pause. Advance.

---

## SLIDE 15 · Thank You (10 sec) — VEENA

> *(Both presenters stand together. Veena speaks. Both make eye contact.)*

"One crore to build the missing memory layer for India's sovereign AI stack. Private. On-device. Auditable. Reversible. **Thank you. We welcome your questions.**"

> *(Step back. Hands at sides. Do not speak again until called.)*

---

# Q&A APPENDIX · Anticipated jury questions

Score-card style. Each answer is the **first sentence** (the headline), followed by the supporting detail. Land the headline; only expand if the questioner stays on it.

### Q1. "If your engine is MIT-licensed, what stops a foreign cloud provider from forking it and selling it back to India?"

**Headline:** "Nothing stops the fork — and that's the point. **The moat is not the code; it is the audit trail, the connectors, the on-prem operations, and the customer-side trust we have already built.** A forked UPII running on AWS is just another cloud RAG product — it loses the sovereign-memory property the moment it leaves the device. Our enterprise license is for the integration, the SLA, the security audit, and the audit-trail continuity — none of which fork."

### Q2. "Ninety-one percent top-three retrieval — what's the benchmark, and how does it compare to Pinecone or LlamaIndex?"

**Headline:** "**Measured on real Ambee data — NASA PACE notes, ICEYE SAR terms, confidential roadmap — not a public benchmark.** Public benchmarks are next milestone — we will publish on BEIR-IN and a synthetic DPDP corpus in M3. Pinecone and LlamaIndex are not directly comparable because they do not have the explainability layer or the on-device constraint — our 91% is achieved under tighter constraints."

### Q3. "What is the IP position? Patents filed?"

**Headline:** "**Two provisional filings in progress** — one on the inbox-review-and-promote workflow, one on the parallel-retriever scoring with explainable boost reasons. Both filed through Indian patent counsel. The MIT open core does not weaken either filing; it strengthens the trade-secret-plus-implementation moat around the enterprise build."

### Q4. "Why won't Microsoft Copilot or Google Workspace just ship this as a feature?"

**Headline:** "**Structurally they cannot — because the value is in not being trapped in any single vendor.** Copilot requires M365 tenancy; Google requires Workspace. The moment they ship a 'data-stays-here' mode, they are building their own off-ramp. UPII's defensibility is that no vendor can credibly ship a portable, vendor-neutral memory layer without dismantling their own lock-in."

### Q5. "DPDP says one thing about consent — has your architecture been reviewed by a data-protection lawyer?"

**Headline:** "**Yes — pro-bono review completed in May, formal opinion budgeted under the M2 security-audit line.** Architecture is data-minimisation-by-design — no upload by default, explicit promote-to-memory, full audit trail, exportable for DPO. We are not waiting to be DPDP-compliant; the architecture is the compliance argument."

### Q6. "What happens if Ambee stops using UPII tomorrow?"

**Headline:** "**Ambee is the validation, not the revenue.** Daily production use is a credibility proof for the five pilots, not the business case. The enterprise LTV math holds with any one of the five active pilots converting at the lower end of the price band."

### Q7. "Five pilots in 12 months — what is the conversion mechanic?"

**Headline:** "**The pilots are already in conversation; M2 funding converts them from POC to signed contract.** Each pilot has an identified sponsor, a defined success criterion (≤ 300ms recall, ≥ 90% top-3 on their corpus, audit export accepted by their DPO), and a price commitment range. We are not generating leads; we are converting an existing pipeline."

### Q8. "How do you scale beyond five pilots without a sales team?"

**Headline:** "**Open core is the funnel.** Developer SDK pulls AI-first startups in at ₹499/month — those become enterprise references. NASSCOM and K-Tech are co-sell channels for regulated-sector pilots. We are budgeting for one enterprise account executive in Y2, not Y1 — Y1 is founder-led sales by design."

### Q9. "Why CPU-only? Aren't you giving up accuracy?"

**Headline:** "**CPU-only is a deliberate architectural choice for the regulated India beachhead — district hospitals and SME offices do not have GPUs.** The 91% top-3 number is achieved with a 22M-parameter embedder on CPU; a GPU build is a configuration flag, not a re-architecture, and is reserved for the SDK tier where GPUs are present."

### Q10. "What's your runway today, and what does ₹1 Cr buy you that bridge funding wouldn't?"

**Headline:** "**Current runway carries us through M1 on founder capital and Ambee-funded engineering time.** ₹1 Cr from ELEVATE NxT is not bridge — it is the grant that retires execution risk on M2 (connectors + pilots) and M3 (benchmarks + LOIs), which together are what convert UPII from a CTO-desk tool into a category-defining product. Bridge VC capital at this stage would dilute the open-core thesis and force premature commercial compression."

### Q11. "Why Karnataka, not Delhi or Mumbai?"

**Headline:** "**Bengaluru is the only city in India where the talent, the regulated-sector customers, and the deeptech grant ecosystem all converge.** IISc, IIITB, NASSCOM, K-Tech, plus the BFSI and healthcare pilots — all within 15 km of our office. Delhi has the policy seat; Mumbai has the BFSI capital. Bengaluru has the engineering and the institutional support. We are here because the build happens here."

### Q12. "What does 'sovereign' mean here — is this nationalist marketing?"

**Headline:** "**Sovereign means data-locality plus user-revocability, with the cryptographic and operational properties to back both.** It is a technical claim — not a slogan. Data stays on the device, audit trail is tamper-evident, the operator can revoke any grant. If a foreign-built tool met these properties, it would be sovereign too. None do, today, for the Indian regulated buyer."

---

# Final stage notes

- **Pacing:** 140 words per minute is the comfortable pitch tempo. Slow down 20% on every number. Pause two full beats after a key claim — silence makes the jury write.
- **Hand-offs:** Both hand-offs (Veena → Maddy on S4, Maddy → Veena on S8) should be physical — half-step back, half-step forward. Do not interrupt each other mid-sentence.
- **Body language:** Hands visible. No pockets. No clasped wrists. Open palms when stating a guarantee or a number.
- **If you run over time:** Cut S12 (team) to a single sentence — "Seven engineers, three decades combined, IIT/BITS/IIIT-trained, full team in Bengaluru" — and recover 15 seconds.
- **If you run under time:** Hold one extra beat after S14's final sentence. Do not fill silence.
- **The one line they will remember:** "*Zero rupees of India's regulated enterprise knowledge can safely meet today's AI models.*" Land it.
