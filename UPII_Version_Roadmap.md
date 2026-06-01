# UPII · Version Roadmap (v0.5 → v3.0)

**Grant horizon:** 12 months · ₹1 Cr · ELEVATE NxT (ELNXT20260000020)
**TRL trajectory:** TRL 4 (today) → TRL 6 (Month 12)
**Source of truth:** this document reconciles `docs/task.md`, `docs/walkthrough_v0_5.md`, `docs/walkthrough_v1_0.md`, `docs/design_blueprint_v1.md`, `docs/implementation_plan.md`, and the Slide-13 milestones in `DataFrontier_UPII_GrandFinale_Deck.pptx`.

The grant funds v1.5 → v3.0. v0.5 and v1.0 are pre-existing baselines (founder capital + Ambee-funded engineering time).

---

## Where we are today — the two shipped baselines

### v0.5 · Explicit Memory Substrate · SHIPPED

The reliability baseline. Everything in v0.5 is user-triggered, zero ambient capture, runs entirely on-device.

| Capability | Surface | Status |
|---|---|---|
| Document ingestion | `upii ingest <path>` | Shipped |
| Semantic search | `upii search "<query>"` | Shipped |
| RAG question-answering | `upii ask "<question>"` | Shipped |
| Task extraction | `upii tasks list/search/done` | Shipped |
| System diagnostics | `upii doctor` | Shipped |
| Storage | SQLite (`upii.db`) + LanceDB columnar vectors | Shipped |
| LLM backend | Ollama (local) / Gemini (cloud) / mock fallback | Shipped |
| Embeddings | `all-MiniLM-L6-v2` (22M params, CPU-only) | Shipped |
| Packaging | `pyproject.toml`, `upii` entrypoint | Shipped |

### v1.0 · Sovereign Memory Engine · IN PRODUCTION (Ambee CTO desk)

The trust baseline. Adds ambient capture without compromising the v0.5 reliability story. Per `docs/task.md`, all major work items are checked off except "Update Inbox to show Audit Logs."

| Capability | Surface | Status |
|---|---|---|
| Ambient filesystem watcher | `upii watch <path>` | Shipped (with bugs flagged for v1.5 hardening) |
| Source registry & lifecycle | `upii sources list/enable/disable/audit` | Shipped |
| Staging DB + isolation | `staging.db` (separate from `upii.db`) | Shipped |
| Inbox review workflow | `upii inbox`, `upii inbox --approve <id>` | Shipped (UX gaps flagged for v1.5) |
| Feature flag system | `src/upii/core/features.py`, `features.yaml` | Shipped |
| Calendar (.ics) connector | `src/upii/ambient/calendar_connector.py` | Shipped |
| Knowledge graph (rule-based) | `src/upii/analysis/entity_extractor.py` | Shipped |
| KG reversibility | `upii knowledge wipe` | Shipped |
| Context rehydration | 3 parallel retrievers (vector + temporal + entity) | Shipped |
| Explainable scoring | `upii ask "..." --debug` (boost_reason per chunk) | Shipped |
| Local metrics dashboard | `upii metrics show` | Shipped |
| Transparency export | `upii metrics export --out report.json` | Shipped |
| Voice-style drafting | `upii write "<topic>" --target email/tweet/linkedin` | Beta (style extraction is placeholder; v1.5 hardens) |
| Demo modes | `upii demo investor/customer/seed` | Shipped |
| Release artifacts | Mac + Windows builds, 18 test suites, CI/CD pipeline | Shipped |
| Benchmark on Ambee corpus | 91% top-3, <300 ms P95 latency | Measured |

---

## v1.5 · UX Layer & Production Hardening · MILESTONE M1 (Months 0–4)

**Theme:** make v1.0 stage-ready and operator-comfortable.
**TRL:** 4 → 5
**Demo target end of M1:** zero-friction onboarding + always-available context, all three Slide-5 capabilities (governance, recall, transparency) bulletproof on a fresh laptop.

### Features

1. **Cmd+Shift+K Global Overlay** — Spotlight-for-AI launcher available system-wide. Single keystroke summons a translucent query window that calls into the local substrate and returns the answer in <300 ms P95, with click-to-trace evidence inline. (Direct deliverable from M1 line item in Slide 13.)
2. **Inbox Review UX polish** — content preview in listing (first 120 chars), batch approve/reject, diff view for `modified` events, side-by-side staging vs. LTM comparison, keyboard-driven triage.
3. **Ambient source hardening** — replace polling watcher with `watchdog` native FS events (10× lower CPU on idle), fix the `PollingWatcher` import / `FileSystemSource` wiring bug, implement `--reject` and `--all` for `inbox`, graceful handling of deleted-event approvals, idempotent approve.
4. **Curator auto-policy** — opt-in policy engine that pre-classifies staged events ("auto-approve from `~/work/notes`", "always review from `~/Downloads`"). User signs off on policies, not individual events. Reduces inbox fatigue.
5. **`write` style synthesis (production-grade)** — author metadata via markdown frontmatter, `config.user_name`, per-target length enforcement (≤ 280 chars tweet, ≤ 1300 LinkedIn), deterministic Subject-line extraction for email, retry-with-shorter-prompt on overflow.
6. **Local LLM consistency** — temperature-locked "honest" mode for retrieval (forces "I don't know" when confidence < threshold), pre-warm on launch to avoid cold-start spinner.
7. **Signed installers** — Apple Developer ID + Windows Authenticode signing. Removes "unidentified developer" dialog that has been killing pilot install rates.
8. **First-run onboarding wizard** — 60-second walkthrough: connect a folder, drop a file, watch it land in the inbox, approve, ask. Converts trial users to active users.
9. **Performance lock-in** — sub-300 ms P95 latency as a CI gate, not just an observation. Regression on a benchmark commit fails the build.
10. **Observability** — extend `upii metrics show` with per-retriever timing breakdown (vector / temporal / KG / LLM), p50/p95/p99 columns, exportable as the audit packet a CISO actually wants.

### Success criteria
- All 8 steps of the end-to-end demo flow (see `CLAUDE_CODE_PROMPT_ambient_features.md`) pass on a fresh laptop from a clean `git clone`.
- 18 → 30+ test suites; CI gate blocks merges that regress latency or drop retrieval accuracy below 90%.
- Mac + Windows signed installers tested on at least two non-developer machines per platform.
- One additional internal user beyond the Ambee CTO desk (recommended: Veena's daily workflow) — proves the system works for non-engineers.

### Risks & mitigations
- **Overlay daemon stability under macOS Sequoia / Windows 11.** Mitigation: build a fallback CLI-only mode that pilots can run if the overlay misbehaves on their hardware.
- **LLM "honest mode" calibration.** Lowering temperature too aggressively kills the `write` voice synthesis. Mitigation: per-command temperature profiles, not a global setting.

---

## v2.0 · Enterprise Connectors & Multi-Tenant Foundation · MILESTONE M2 (Months 4–8)

**Theme:** the substrate stops being personal-only and starts being team/enterprise-deployable.
**TRL:** 5 → 5+
**Demo target end of M2:** an Ambee-shaped pilot in three regulated-sector orgs (BFSI, healthcare, climate-tech-research), each with their own connector mix, each fully air-gapped.

### Features

1. **Email connector — IMAP + Gmail API.** OAuth-scoped, read-only by default, scoped grant per folder/label. Stages each thread as one document with full headers preserved as metadata. (M2 line item.)
2. **Slack connector — read-only.** OAuth installation, scoped to specific channels (operator approves channel list), threads ingested as documents. Threads with attachments queue the attachment for separate ingestion via the same `inbox` review flow.
3. **Google Workspace connector — Drive, Docs, Calendar.** Drive watched at folder-granularity; Docs ingested with revision history; Calendar pipes through the existing `.ics` infrastructure but now via API. (M2 line item.)
4. **Notion connector — API-based.** Workspace-scoped; pages ingested with backlink structure preserved as KG edges. (M2 line item.)
5. **Multi-tenant foundation.** Workspace isolation per user — separate `upii.db` and `staging.db` per tenant, separate vector store, shared engine. Foundation called out explicitly on Slide 5 ("Foundation for v2.0 multi-tenant").
6. **SSO support.** SAML 2.0 + OIDC for enterprise login. Maps SSO identity to UPII workspace.
7. **Role-based access control (RBAC).** Three default roles: `operator` (full read/write), `auditor` (audit-log read + metrics, no LTM content), `admin` (RBAC + workspace lifecycle). Custom roles via capability tokens (precursor to the v3 capability ledger).
8. **Air-gapped on-prem deploy package.** Single signed bundle (Mac/Windows/Linux) that installs UPII + local LLM weights + all dependencies, with zero network calls required at install or runtime. Tested in a literal air-gapped VM.
9. **DPDP-compliant data residency module.** Configurable storage location, audit trail of every data crossing, exportable compliance report for the operator's DPO.
10. **Independent third-party security audit.** Budgeted under the M2 security-audit line in Slide 13. Output: a signed audit report enterprise procurement teams accept.
11. **Enterprise installer + group policy.** Windows MSI with GPO templates; Mac PKG with MDM profile compatibility (Jamf, Intune).
12. **Three regulated-sector pilots signed.** BFSI (mid-size NBFC), healthcare (Bengaluru hospital network), climate-tech research lab. Per Slide 8 pipeline. Each pilot is a signed contract, not a POC.

### Success criteria
- All four connectors (email, Slack, Google Workspace, Notion) ingest and stage successfully against real pilot accounts.
- Multi-tenant isolation verified: penetration test confirms no cross-workspace read paths.
- Independent security audit completed with no critical findings; medium findings remediated.
- Three pilot contracts signed with payment milestones tied to v2.0 deployment.
- Air-gapped install verified end-to-end on an isolated machine (no developer assistance required).

### Risks & mitigations
- **Connector OAuth complexity.** Each vendor's OAuth surface is different and changes. Mitigation: abstract behind a shared `Connector` interface (extends the existing `Source` registry), version-pin all SDKs, integration test against vendor sandbox envs nightly.
- **Multi-tenant performance regression.** Adding tenant isolation to the SQLite + LanceDB layer can blow up query plans. Mitigation: per-tenant DB files (not shared schema with tenant column), benchmark gate in CI before merge.
- **DPDP interpretation drift.** The Act is enforced from 2026 with evolving rules. Mitigation: monthly DPO review, conservative defaults (data-minimisation, opt-in everything).

---

## v3.0 · Research-Grade Benchmarks, Open Core, and Production Multi-Tenant · MILESTONE M3 (Months 8–12)

**Theme:** academic credibility + community ownership + enterprise-grade production.
**TRL:** 5+ → 6
**Demo target end of M3:** UPII referenced in a peer-reviewed publication, MIT-licensed core released, five enterprise LOIs converted.

### Features

1. **Formal benchmarking suite.** NDCG @ {1,3,5,10}, precision @ k, MRR, latency p50/p95/p99 on every retriever path. Published as a reproducible harness in the repo. (M3 line item.)
2. **BEIR-IN public benchmark.** UPII evaluated on the Indian-language subset of BEIR + a custom regulated-document benchmark we publish. Numbers are real and externally verifiable.
3. **Synthetic DPDP-compliant corpus.** A publishable benchmark dataset of synthetic-but-realistic Indian regulated-sector documents (healthcare consent forms, BFSI KYC, government correspondence templates), with ground-truth retrieval pairs. Released under a permissive licence as a contribution to the Indian AI research community.
4. **Research paper submission.** Target venues: EMNLP industry track, KDD applied data science track, or a vertical workshop (DPDP-AI, FAccT). Topic: "On-device personal context substrates: architecture, evaluation, and the cost of vendor-neutrality." (M3 line item.)
5. **Open-core MIT release.** The core engine — embeddings, storage, retrieval, context rehydration, capability primitive — released under MIT. Enterprise connectors and multi-tenant control plane remain proprietary. (Slide 11 commitment to Karnataka community.)
6. **Developer SDK.** Python + REST API. Pricing tier announced (₹499/month/dev per Slide 10).
7. **Plugin architecture for custom retrievers.** Allows community + enterprise users to register their own retrievers without forking the core. Lays groundwork for the v4+ federated-context vision.
8. **Production multi-tenant control plane.** Operator console for tenant lifecycle (create, suspend, export, delete), usage analytics, billing integration.
9. **Capability ledger (v1).** First user-facing implementation of the capability primitive from the UPII research note — agents request scoped grants, operator approves, audit trail. Builds on the v2 RBAC foundation.
10. **Public documentation portal.** docs.upii.ai (or similar) with tutorials, architecture reference, connector cookbook, benchmark methodology.
11. **Karnataka community engagement.** Free SDK access for Karnataka-registered AI startups (per Slide 11 commitment); IISc / IIITB benchmark collaboration formalised.
12. **Five enterprise LOIs converted.** Per Slide 13 grant deliverable.

### Success criteria
- Research paper submitted to a peer-reviewed venue with a reproducible artifact link.
- Open-core MIT repo with >50 GitHub stars and >5 external contributors within 60 days of release.
- Benchmark numbers (NDCG, precision@k) published with full methodology; jury or external reviewer can re-run.
- Multi-tenant control plane running in production with the three M2 pilots migrated onto it.
- Five enterprise LOIs signed, with named org, named sponsor, named success criteria.

### Risks & mitigations
- **Research paper rejection.** Mitigation: parallel-submit a workshop paper + an arXiv preprint; the artifact is what counts for the grant, peer-review is a stretch goal.
- **Open-core cannibalising enterprise revenue.** Mitigation: enterprise differentiator is connectors + multi-tenant + audit + SLA + indemnification, not the core engine. The core being open strengthens enterprise trust, not weakens it.
- **Benchmark numbers underwhelm.** Mitigation: publish honestly; UPII's claim is sovereign + governed + explainable + fast-enough, not state-of-the-art retrieval accuracy. The framing carries the story even if the numbers are middle-of-pack.

---

## Summary table — features × version × milestone × TRL

| Bucket | v0.5 | v1.0 | v1.5 (M1) | v2.0 (M2) | v3.0 (M3) |
|---|---|---|---|---|---|
| **Period** | Pre-grant | Pre-grant | Months 0–4 | Months 4–8 | Months 8–12 |
| **TRL** | 3 → 4 | 4 | 4 → 5 | 5 → 5+ | 5+ → 6 |
| **Ingestion** | Manual CLI | + ambient FS | + auto-curator policy | + Email, Slack, Workspace, Notion connectors | + plugin retrievers |
| **Storage** | SQLite + LanceDB | + staging DB | hardened | + multi-tenant isolation | + tenant control plane |
| **Retrieval** | Vector | + temporal + KG (rehydration) | per-retriever latency telemetry | (no change) | benchmarked (NDCG, p@k, MRR) |
| **Trust** | None needed | inbox review + audit | preview, batch, reject | RBAC + SSO + air-gapped install | capability ledger v1 |
| **UX** | CLI only | CLI + `write` (beta) | Cmd+Shift+K overlay, onboarding wizard | enterprise installer | docs portal |
| **Output** | answers, tasks | + voice-style drafts | production-grade drafts | (no change) | research paper, open-core release |
| **Compliance** | (n/a) | local-only by design | signed installers | DPDP residency module, 3rd-party security audit | benchmark methodology published |
| **Customers** | self-use | Ambee CTO desk | + 1 internal user | + 3 signed pilots | + 5 LOIs |
| **Tests** | unit | 18 suites + CI/CD | 30+ suites + latency gate | + connector integration tests | + benchmark regression suite |

---

## Beyond v3.0 — the horizon (not in this grant)

For context if a jury member asks "what's after the grant?" The substrate primitives in the UPII research note point at Year 2 work:

- **v4.0 · Federated context.** Substrates that can share scoped slices across organisations (e.g., a regulated firm's UPII shares a capability-scoped slice with its auditor's UPII). Builds directly on the v3 capability ledger.
- **v4.5 · Mobile substrate.** iOS + Android substrate that syncs with the desktop UPII via CRDT. The local-first paper's ideals applied to phone-class hardware.
- **v5.0 · Agent-native bindings.** Native MCP server + Anthropic/OpenAI/Gemini agent SDK adapters so any agent platform can bind to a user's UPII without per-platform integration work.
- **Research line.** Curator-granularity benchmark (Q5.1 in the UPII research note); capability-scope legibility study (Q5.2); multi-agent context compounding experiment (Q5.4); personal-substrate evaluation benchmark (Q5.5).

These are the questions whose existence makes v1→v3 a *research programme*, not a product roadmap. Mention them in jury Q&A only if asked; otherwise keep the conversation anchored on the 12-month deliverables.

---

## How to use this document

- **Jury Q&A backup.** If a panellist asks "what's in v2 specifically?" or "what does the ₹1 Cr buy in month 7?" — this is the answer. Pull the relevant row from the summary table.
- **Internal planning.** v1.5 is the next sprint. Work items map 1:1 to the feature list in §v1.5; the `CLAUDE_CODE_PROMPT_ambient_features.md` covers a subset of those (watch + inbox + write hardening).
- **Investor follow-up.** If a VC asks for a product roadmap after the grant pitch, this document is the answer, with the "Beyond v3.0" section as the Year-2 hook.
- **Version-bump checklist.** When tagging a release, the bullet list under the relevant version is the changelog skeleton.

If any milestone slips, the discipline is: update this file first, then update Slide 13 of the deck, then communicate the slip to the grant officer in writing. Versions are commitments — keep them honest.
