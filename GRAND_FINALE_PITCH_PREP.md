# UPII — Karnataka Startup Grand Finale Pitch Prep
## Companion to `DataFrontier_UPII_GrandFinale_Deck.pptx`

**Application ID:** ELNXT20260000020
**Panel:** AI-ML / Health / Bio / Life Sciences
**Format:** 15 min pitch + 5 min Q&A
**Grant ask:** ₹ 1 crore · 12 months · 3 milestones
**Presenter:** Veenadhari Pola (Founder & CEO) · Madhusudhan Anand (Co-Founder & CTO)

---

## Why this deck exists

The Karnataka Startup Cell email is explicit: Pitch Deck B (May 11 submission) will be considered for the Grand Finale, **but any developments after submission may be presented directly to the jury during the pitching session**. This new deck is exactly that — a focused 15-slide *progress update* deck that you walk the jury through, while the submitted Deck B remains on file.

The narrative arc is intentional: "Since you last saw us, here's what shipped, here's who's using it, here's the measured proof, here's why this is the right moment, here's the ask."

---

## 15-minute timed script

| Time | Slide | What you say (anchor) | Evaluation hit |
|------|-------|------------------------|----------------|
| 00:00–01:00 | 01 Title | Brief opener. Names. Application ID. Panel. "We're presenting an update — what's shipped since May 11." | Setup |
| 01:00–02:00 | 02 What changed | "In 15 days we shipped three new capabilities, validated with a live anchor customer, and opened 5 pilot conversations. This deck covers the proof." | Setup (R&D, Validation) |
| 02:00–03:30 | 03 Problem | The Context Gap. Three rows: amnesia, data egress, regulated India. "₹0 of India's regulated knowledge can safely meet today's AI." | Socio-Economic (20) |
| 03:30–04:30 | 04 Solution | UPII = sovereign memory substrate. Three guarantees: zero privacy risk, sub-300ms recall, zero LLM lock-in. "Audit-logged. Reversible. Open-core." | Tech Foundation (20) |
| 04:30–06:30 | 05 What we shipped | Walk through the 3 new capabilities — ambient memory, knowledge graph, transparency. **Read each demo command out loud.** Tell the jury you'll show them all three in 90 seconds. | R&D Depth (20) |
| 06:30–08:30 | 06 Live demo | **Play the 90-second pre-recorded demo.** While it plays, narrate the 6 steps shown in "What the jury sees." Have the live CLI sequence ready as a fallback. | R&D Depth + Tech Foundation |
| 08:30–10:00 | 07 Architecture | Three-layer architecture. Lean hard into Context Rehydration as your core IP. Cite the four numbers: 91%, <300ms, 22M params, ₹40K laptop. | R&D Depth (20) + Tech Foundation (20) |
| 10:00–11:00 | 08 Validation | Ambee anchor + 5-org pipeline. "We're not pitching a pitch deck — we're pitching production use." Offer references on request. | Commercialisation (20) |
| 11:00–12:00 | 09 Market | TAM/SAM/SOM. Competitive gap row. End with "UPII is the only one that's local-first AND governed AND explainable." | Commercialisation (20) |
| 12:00–13:00 | 10 Business model | 4 revenue streams. Risk-infrastructure framing. ₹7–10 Cr LTV. "1 breach > 5× UPII cost." | Commercialisation (20) |
| 13:00–13:45 | 11 Karnataka angle | 4 impact vectors. Lean into K-Tech / NASSCOM / IISc / IIITB alignment. "Built in Bengaluru. For India. For the world." | Socio-Economic (20) |
| 13:45–14:15 | 12 Team | Three named leaders: Veena (CEO — 17+ yrs enterprise, GTM, regulators), Maddy (CTO — BITS Pilani / IIIT-B / MS DS LJMU; granted patents, raised institutional funding, scaled Ambee to several $M ARR), Dr. Chaitra C R (Chief Data Scientist — Ph.D. BITS Pilani Hyderabad, IIIT-B PG Dip AI/ML; 5 ACL/ECIR/Springer papers on LLMs, RAG, agentic QA). 7+ engineers total. | Team (10) |
| 14:15–14:45 | 13 Grant ask | ₹1 Cr · 3 milestones · 12 months. Lead with R&D 40%, every line tied to a deliverable. | Budget (10) |
| 14:45–15:00 | 14 Closing argument | Three reasons to fund **today** — DPDP enforcement window, shipping foundation, founder-market fit. | Closing |
| Optional 15:00 | 15 Thank you | "₹1 crore to build the missing memory layer for India's sovereign AI stack." Pause. Thank the jury. | Closing |

---

## What's new in this deck vs the May 11 deck

| Was in Deck B (submitted) | New / strengthened here |
|---|---|
| 16 evaluation-criteria-mapped slides | 15 slides, narrative-driven, progress-update framing |
| TRL 4 with v0.5 shipped, generic capability list | Explicit "shipped in last 15 days" slide naming Ambient + KG + Metrics with live demo commands |
| Generic enterprise positioning | Named anchor (Ambee in production at CTO desk) + 5-org pipeline |
| 91% top-3 retrieval as a single claim | Same number + 3 supporting metrics on one slide (<300ms, 22M params, ₹40K laptop) |
| Karnataka mention | Four explicit Karnataka vectors + ecosystem-alignment bar |
| Standard milestone roadmap | Three concrete milestones with TRL deltas and converted-LOI targets |

---

## Demo plan (slide 6)

**Primary: pre-recorded 90-second video.** Record it before the pitch with these 6 cuts:

```bash
# 00:00 - Health check
python -m upii.cli doctor

# 00:08 - Ingest 5 sensitive Ambee docs
python -m upii.cli ingest demo_data_v2/

# 00:24 - Contextual recall (specific fact)
upii ask "What was the resolution and latency agreed with ICEYE?"

# 00:42 - Cross-document synthesis
upii ask "How does the NASA PACE calibration issue affect our roadmap?"

# 01:00 - Honesty / no hallucination
upii ask "What is the launch date for Project Alpha?"

# 01:18 - Explainable recall (show audit trail)
upii ask "Did I have a meeting last week?" --debug
```

**Fallback:** open Terminal, run the same sequence live. Keep the laptop on battery + DND, terminal font 18pt+, dark theme.

**Pre-flight checklist (do day-of, before reporting):**
- [ ] `source venv/bin/activate` + `python -m upii.cli doctor` shows all green
- [ ] `python scripts/reset_demo_env.py` resets the demo DB cleanly
- [ ] One full dry-run of the 6 commands (verify ICEYE / PACE / "I don't know" answers all behave)
- [ ] demo.mp4 is on the desktop AND embedded in slide 6
- [ ] Laptop at 100%, charger packed, DND on, notifications off
- [ ] Phone has the deck PDF as a backup
- [ ] Print one A4 of the budget table and the milestone table (insurance)

---

## Q&A — the questions to expect (5 min)

### On the new capabilities (slide 5)

**Q: "Ambient memory — how do you handle a user who turns it on and then mass-ingests garbage?"**
> A: That's exactly why we built the inbox layer. Ambient sources write to a staging DB, never long-term memory. Every event has to be explicitly approved. The audit log records every enable/disable/approve action — so even a misuse leaves a trail. We can also `wipe` any ingested entity to clear it from LTM and the knowledge graph.

**Q: "Knowledge graph without a graph DB — what does that mean in practice?"**
> A: We do entity extraction at ingest time and link entities to chunks in our metadata table. Retrieval is still SQL + vector + a lightweight entity-aware re-ranker. No Neo4j, no JanusGraph, no operational cost. We get the explainability without the infra overhead. It's the right level of "graph" for the regulated-enterprise use case.

**Q: "What does the transparency report actually contain?"**
> A: 7-day rolling counts of queries, ingestion events, DB size, and a per-source breakdown. The JSON export is meant to be handed to a DPO or auditor — they can verify the system's behaviour without ever seeing user content. It's the foundation for the v2.0 multi-tenant audit layer.

### On benchmarks (slide 7)

**Q: "91% top-3 — on what corpus, what queries?"**
> A: Internal Ambee corpus — 5 documents (NASA PACE notes, ICEYE partnership terms, strategic roadmap, CTO tasks, KG seed). Held-out query set of ~30 questions written before evaluation. We acknowledge this is a small dataset — Milestone 3 of the grant funds formal NDCG/precision@k benchmarking against MTEB + an India-specific corpus we're building.

**Q: "Why MiniLM and not a larger model?"**
> A: Three reasons. One: 22M parameters runs on CPU — a ₹40K laptop can host UPII. Two: MTEB shows MiniLM-L6-v2 above 0.80 — strong enough for retrieval at our chunk sizes. Three: we keep the embedder pluggable, so an enterprise customer with a GPU can swap in BGE-large or E5 without touching application code.

### On Ambee and pilots (slide 8)

**Q: "Is Ambee a real arms-length customer or just your day job?"**
> A: Honest answer — Madhusudhan is CTO at Ambee, so it's a captive deployment. But that's the *strength*, not the weakness: zero-latency feedback loop, real confidential data (satellite tasking, NASA/ESA NDAs), and Ambee's 100+ enterprise clients become a warm pipeline for UPII Enterprise. The Ambee deployment is the proving ground, not the destination.

**Q: "Can we talk to your pilot conversations?"**
> A: We can connect you with two of the five subject to their NDAs. The conversations are at different stages — POC scoping, confidentiality review, demo scheduled. We're being deliberate about not naming them publicly until pilots are signed.

### On business model (slide 10)

**Q: "₹15–50L enterprise license — is that what regulated Indian firms actually pay?"**
> A: It's calibrated against alternatives — Notion AI Enterprise + a separate vector DB + compliance review typically lands in this range, *and* the customer still has the data-egress problem. We're priced as risk infrastructure, not productivity software. A single DPDP breach costs ₹1 Cr+ — UPII is a fraction of that risk exposure.

**Q: "Open core — won't enterprises just self-host the free version?"**
> A: That's exactly what we want them to do — for evaluation. The paid tier adds air-gapped deploy automation, SLA, audit log integration with their SIEM, SSO, and customer support. Open core is the funnel; enterprise license is the conversion. It's the GitLab / HashiCorp playbook for the regulated-AI category.

### On grant / Karnataka

**Q: "What does ₹1 Cr buy that ₹50 L doesn't?"**
> A: ₹50 L gets us through Milestone 1 (ambient + overlay UI) and partial Milestone 2. ₹1 Cr lets us also fund the formal benchmarking, the research publication, and the security audit — the parts that make UPII credible to BFSI procurement and to academic collaborators. The 40% R&D minimum is honoured either way; the extra ₹50L is what turns a working product into a defensible deeptech moat.

**Q: "How does this benefit Karnataka specifically — beyond hiring?"**
> A: Three concrete ways. One: K-Tech / KITS can position UPII as the sovereign-AI-memory layer in any state digital programme — DPDP enforcement gives them a real reason to mandate this. Two: NASSCOM Bengaluru gets a member-company asset to co-sell into BFSI. Three: open-sourcing the core means every Bengaluru AI startup can build on top of it without paying foreign cloud bills — that's compounding ecosystem value.

**Q: "Risk of grant misuse?"**
> A: Every line in the budget is tied to a milestone deliverable, every milestone has a TRL transition target, and we'll publish quarterly burn + milestone reports. The founder DNA is operational rigor — Maddy has BITS Pilani / IIIT Bangalore / MS Data Science (LJMU), granted patents, published papers, has raised institutional funding before, and has scaled products from idea to several $M ARR. R&D and capital discipline are both demonstrated track record, not promise.

**Q: "Who is doing the actual research?"**
> A: Dr. Chaitra C R, our Chief Data Scientist, just defended her Ph.D. in CS from BITS Pilani Hyderabad on LLM-based information systems. She has five peer-reviewed publications at ACL, ECIR, and Springer venues — including LeGen (legal NLP using T5/BART + GPT/Llama) and Prabodhini (LLM accessibility for low-text-literate Indian users). She also holds the IIIT Bangalore PG Diploma in AI/ML. She owns the retrieval-quality benchmarking, the knowledge-graph layer, and the research-paper deliverable in Milestone 3. This isn't a generalist engineering team papering over an "ML strategy" — we have a publishing applied-AI researcher in-house.

### Curveballs to prepare for

**Q: "Couldn't Google / Microsoft just build this and crush you?"**
> A: They could build the tech — they cannot ship the trust. Their entire business model depends on data flowing to their cloud. A sovereign-by-design product from a US hyperscaler is a contradiction. That's the moat — not the algorithm, but the alignment.

**Q: "What if DPDP enforcement gets delayed?"**
> A: It tightens our timing argument but doesn't break the thesis. Even without DPDP, BFSI sectoral guidelines (RBI master direction on IT governance), IRDAI, defence procurement, and health-data protection rules all require what UPII delivers. DPDP is the accelerator; the demand is structural.

**Q: "What if a jury member wants to install it right now?"**
> A: Open the laptop. `pip install -e .` from the repo, `upii doctor` works on their machine. We've been deliberate about not requiring Docker / GPU / cloud accounts. (If you're confident, offer this — it's the strongest possible signal.)

---

## Mindset reminders

- You are the **only person in the room** who has built this. Speak with authority.
- The submitted Deck B is your fallback if anything goes wrong with this update deck — both are on file.
- When a question stumps you: "Great question — currently we handle it this way... on our roadmap to extend with X." Never bluff.
- Slow down on the architecture slide. The jury includes technical evaluators. Earn the R&D 20 marks deliberately.
- Your strongest card remains: **it's already working.** When in doubt, run a command.
- If asked about competitors, acknowledge them then immediately pivot to local-first + governed + explainable.

---

## Key numbers — memorise cold

| Fact | Number |
|---|---|
| Retrieval accuracy (Ambee corpus, top-3) | 91 % |
| End-to-end recall latency (P95) | < 300 ms |
| Embedder model size | 22 M params, CPU-only |
| Minimum hardware | ₹ 40 K laptop |
| Test suites | 18 |
| New capabilities shipped since May 11 | 3 |
| Active pilot conversations | 5 |
| Ambee network reach | 100+ enterprise clients |
| Enterprise license band | ₹ 15 – 50 L / year |
| Enterprise LTV | ₹ 7 – 10 Cr |
| Grant ask | ₹ 1 Cr |
| Milestones | 3 over 12 months |
| R&D allocation | 40 % (= ₹ 40 L) |
| Jobs created | 5 engineering hires in Bengaluru |

---

*Prepared for the Karnataka Startup Grand Finale, June 2026. Good luck — you've got this.*
