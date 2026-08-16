# UPII — Tranche-1 Jury Walkthrough & Recording Script

**Project:** UPII (Unified Personal Intelligence Interface) · DataFrontier Innovations Pvt Ltd
**Grant:** ELEVATE Nxt (Deeptech) 2026 · Annexure-1 Tranche Plan
**Audience:** KITS reviewer / ELEVATE Nxt jury
**Purpose:** One continuous recording that demonstrates **every Tranche-1 milestone** — read this aloud as you go.
**Runtime:** ~14 minutes
**Companion document:** [`docs/tranche1_completion_report.md`](tranche1_completion_report.md) — the written evidence this video narrates.

> **This file replaces three earlier demo docs** (`grant_officer_demo_walkthrough.md`,
> `jury_progress_demo.md`, `demo_script.md`), all of which were stale. See
> [§ Document history](#document-history).

---

## How to use this file

Everything in a **> blockquote** is what you *say*. Everything in a ```bash``` block is
what you *run*. Expected output follows each command so you know, before you record,
whether the take is going well.

Milestones map to Annexure-1 as: **1** infrastructure/baseline · **2** deterministic
ingestion · **3** Context Rehydrator v2 · **4** knowledge graph · **5** provisional
patent. Milestone 6 is this recording plus the completion report.

**The single most important instruction:** three of the five milestones are
demonstrated by committed scripts that echo every command before running it, so the
recording documents itself. Do not type ad-hoc commands on camera. If something fails,
stop, fix it, and start the take again — a jury video with a stack trace in it is worse
than no video.

---

## Part 0 — Pre-flight (do all of this BEFORE you hit record)

```bash
cd /Users/maddy/Documents/UPII-master
source venv/bin/activate
upii doctor                     # every check must be green
pytest tests/ -q                # expect: 126 passed, 1 skipped
```

**Terminal setup.** ~100 columns, large font, clear scrollback, dark theme. Close
notifications. Nothing on screen but the terminal and, later, a browser.

**Pre-generate the Milestone 1 artifact.** The Phase 1 benchmark takes 15–30 minutes —
**you cannot run it inside the take.** Run it beforehand so the report is on disk and
you narrate the finished numbers:

```bash
DOCS=7750 NOTE="Apple M5 Max, 30-core CPU / 40-core GPU" bash scripts/demo/phase1_demo.sh
```

`DOCS=7750` clears 100,000 chunks (7,700 produced 99,702). After it finishes, **update
every number in Part 2 below and in the completion report** — throughput, p50, chunk
count and machine line will all have changed.

**No Ollama required.** Every demo script uses `upii ask --no-answer`, so the whole
recording runs with no language model and produces identical output every time. If you
*want* to show synthesis, start Ollama first — but it adds a live dependency to your
take, and I would not.

**Have open in browser tabs, ready to switch to:** the patent filing receipt, and
`bench/results/REPORT.md`.

**Recording.** Screen-record the whole session in one take, or use asciinema per
segment and cut them together:

```bash
asciinema rec upii_tranche1.cast -c "bash scripts/demo/<script>.sh"
```

---

## Part 1 — Opening (~90 seconds, no commands)

> "I'm Maddy, from DataFrontier Innovations. This is UPII — a local-first personal
> memory engine for knowledge workers.
>
> The problem we set out to solve is what we call the Context Gap. To make AI genuinely
> useful on your own work, you're currently forced to upload your digital brain — your
> emails, your contracts, your strategy documents — to somebody else's cloud. For
> regulated industries and for anyone handling sensitive partner data, that isn't a
> trade-off. It's a non-starter.
>
> UPII inverts that. Embeddings are computed on this machine. Vectors live in an on-disk
> store here. The metadata source of truth is a local SQLite database. A cloud language
> model is an optional accelerator you can swap out or switch off — it is never a
> dependency. No corpus byte has to leave the device for the system to work.
>
> In the next twelve minutes I'll demonstrate all five Tranche-1 milestones, in order,
> on this machine. Every number I show is written by a committed script that you can
> re-run yourself from our repository — I'll show you the command each time. Where we
> fell short of an internal target, I'll tell you that too, and show you the honest
> number."

---

## Part 2 — Milestone 1: R&D infrastructure and performance baseline (~2 min)

> **MoA Completion Demonstration:** procurement invoices; a baseline benchmark report
> recording ingestion throughput and median retrieval latency on a representative corpus.

**Do not run the benchmark live.** Display the report you generated in pre-flight:

```bash
open bench/results/REPORT.md      # or: cat bench/results/REPORT.md
```

> "The first milestone was standing up the R&D infrastructure and establishing our
> performance baselines. What we built is a measurement harness — a generator that
> produces a reproducible corpus from a fixed seed, and a benchmark that drives it
> through the real ingestion pipeline with the real embedding model, then replays
> queries through the live retrieval path. No mocks, no simulated timings.
>
> On a corpus of roughly one hundred thousand chunks, the system ingests **627 documents
> per minute** and answers a typical query in **40 milliseconds** at the median. Our
> internal targets were 500 documents a minute and 300 milliseconds. So we're comfortably
> past both.
>
> But the number I actually want to show you is this one."

*Scroll to the throughput-vs-index-size table.*

> "The first time we ran this benchmark, it measured 145 documents a minute — a clear
> miss — and throughput was decaying as the index grew. Our diagnosis was that this was
> algorithmic, not a hardware limitation: we were writing vectors to disk once per
> document, so every write got more expensive as the index grew. We batched those
> writes. Throughput went flat and rose four-fold.
>
> We publish the full curve rather than just the endpoint average, so you can verify
> that fix rather than take our word for it. That's the standard we've tried to hold
> across all of these milestones."

**If asked about hardware — volunteer it rather than wait:**

> "One caveat I should give you up front: this was measured on a MacBook Pro, not on the
> Mac Studio in our procurement plan, which is delayed in shipping. The MoA asks for a
> baseline on a representative corpus, which this is. When the Studio arrives, the same
> single command re-runs the whole benchmark and we expect a better number, not a
> different conclusion."

---

## Part 3 — Milestone 2: Deterministic, content-addressed ingestion (~2 min)

> **MoA Completion Demonstration:** a reproducibility test report showing identical chunk
> hashes when the same inputs are re-ingested, **and a recorded CLI demonstration** of
> re-running identical inputs to an identical memory state.
>
> *(This segment is that recorded demonstration — the MoA asks for it by name.)*

> "The second milestone is the one everything else rests on. A memory system is only
> trustworthy if the same inputs always produce the same memory. If re-reading your
> files quietly changed what was stored, or duplicated it, or left stale fragments
> behind, you could never trust a citation.
>
> So ingestion is content-addressed. Every document and every chunk is identified by a
> hash of its content — not by a random identifier, and not by the time it was read.
> Let me prove it."

```bash
bash scripts/demo/repro_demo.sh
```

*Expect: ingest → chunk count and sample hashes → re-ingest → every file a no-op →
closing `IDENTICAL ✓`.* **~90 seconds.**

> "It ingested a corpus, printed the chunk hashes, then ingested the identical corpus a
> second time. Every file was recognised as unchanged. Nothing was re-embedded, and
> every hash is byte-for-byte identical.
>
> The same property holds across the full lifecycle — editing a file re-chunks only that
> file and purges its stale chunks; deleting one removes its chunks, its vectors and its
> metadata together. Twelve automated checks, all passing, and an independent re-ingest
> reproduced three thousand out of three thousand chunk hashes. One hundred percent."

**Volunteer the scale gap — do not let them find it:**

> "Our internal stretch target named a one-million-chunk corpus and we validated at three
> thousand. I want to be straightforward about that. Reproducibility here is a structural
> property, not a statistical one — the chunk hash is a pure function of file content and
> chunker configuration, so it doesn't degrade with corpus size. The same committed
> harness runs the million-chunk check by changing one flag. It's a wall-clock cost, not
> an engineering gap."

---

## Part 4 — Milestone 3: Context Rehydrator v2 (~3 min)

> **MoA Completion Demonstration:** an evaluation report establishing a retrieval-quality
> baseline and demonstrating measurable improvement from multi-signal fusion over a
> semantic-only baseline, plus a live `upii ask` demonstration of fused ranking.

> "The third milestone is the core of the invention — what we call the Context
> Rehydrator. The idea is that recall shouldn't be treated as a single similarity
> calculation. It should be treated as sensor fusion: combine semantic similarity from
> vector search, temporal proximity from recency and calendar context, and relational
> overlap from an on-device knowledge graph, into one ranked context window."

```bash
bash scripts/demo/phase3_demo.sh
```

*Expect: ingest → `upii ask --debug` showing the per-signal contribution table → a
control run with temporal and relational zeroed → closing `Recall@10 = 0.958`.*
**~3 minutes.**

*When the `--debug` table appears:*

> "This is the fusion made visible. For each retrieved chunk you can see the final score
> and the contribution of each individual signal behind it. That's not a log line we
> added for this demo — it's the `--debug` view of the live retrieval path."

*When the Recall number appears:*

> "Against our committed labelled evaluation set, the correct passage appears in the top
> ten results for **95.8 percent** of queries. Our internal target was 85."

**Now the honesty moment. This is the most important thing you say in the whole
recording — script it, don't improvise:**

> "Now I need to be precise about what that number is and isn't, because the demo you
> just watched deliberately proves it against us.
>
> That 95.8 is a semantic-retrieval number. Watch what the script did in that second
> run — it re-ran the identical queries with the temporal and relational weights set to
> zero, and the ranking came back **identical**. So today the fusion architecture is
> built and live, but only the semantic signal is actually moving the ranking.
>
> There are two honest reasons. The temporal signal is a uniform offset on a corpus
> that was bulk-ingested in one go, so it can't reorder anything. And the relational
> signal — which now has real data, because our fourth milestone wired entity extraction
> into ingestion — turned out **not to be net-positive** when we measured it. It can
> promote a chunk that merely mentions a query entity over a better semantic match. It
> cost us precision at rank one.
>
> So we made a call: rather than ship a ranking regression as the default to make a
> slide look better, the relational weight ships at zero, and the signal is available
> per query for experimentation. The measurable improvement from fusion is the one part
> of this milestone we have not yet earned, and tuning it is our top technical priority
> going into Tranche 2. Everything else in that report — the baseline, the reproducibility,
> the live fused ranking — is delivered."

---

## Part 5 — Milestone 4: Local knowledge-graph extraction (~2.5 min)

> **MoA Completion Demonstration:** an extraction report establishing an entity-extraction
> quality baseline on a labelled set and demonstrating measurable improvement, plus a
> knowledge-graph visualisation.

> "The fourth milestone gives UPII a structural memory alongside the semantic one. As
> documents are ingested, the system reads out the people, the organisations and the
> projects they mention, and builds a knowledge graph of who appears alongside what —
> entirely on this machine, with no external service and no additional dependency."

```bash
bash scripts/demo/phase4_demo.sh
```

*Expect: ingest the labelled corpus → entity precision → `graph.html` opens in the
browser.* **~3 minutes.**

> "Measured against a committed 500-document labelled fixture containing 3,217 gold
> entities, the extractor achieved **perfect precision — 1.000, with zero false
> positives** — against a target of 0.80, and recovered 92 percent of the entities
> present.
>
> Two things make that number worth trusting. First, the fixture is deliberately
> adversarial: it seeds multi-word capitalised phrases that look like entities but
> aren't, and technical acronyms designed to be mistaken for organisation names.
> Precision there is earned, not handed over by an easy test set.
>
> Second — and I think this matters more — we didn't tune the fixture to flatter the
> extractor. When we first saw perfect recall, we went back and *added* uncommon
> surnames that a rule-based extractor can't recover without a title cue. That's why
> recall is reported at 0.92 and not at 1.0. We'd rather show you a real limit than a
> manufactured perfect score.
>
> The baseline-to-improvement story the MoA asks for is unusually clean here: our
> previous extractor scored **zero** precision on this same set."

*When `graph.html` opens:*

> "And this is the graph itself — a single self-contained HTML file. Nodes coloured by
> entity type, edges weighted by co-occurrence. No network calls, no CDN, nothing
> external. I could disconnect this machine right now and it would render exactly the
> same. That's the sovereignty principle applied all the way down to the visualisation."

---

## Part 6 — Milestone 5: Provisional patent filing (~1 min)

> **MoA Completion Demonstration:** a filed provisional patent application bearing its
> official application/receipt number. *(Filed from the company's own funds, not the
> grant, per Annexure-2.)*

> ⚠️ **FILL THIS IN BEFORE RECORDING.** Insert the application number, filing date and
> office. Have the receipt on screen. Do not record this segment from memory.

*Switch to the filing receipt on screen.*

> "The fifth Tranche-1 milestone was to file a provisional patent covering UPII's novel
> methods — sovereign multi-signal context rehydration, and attributed on-device memory
> through content-addressed deterministic chunking.
>
> That application has been filed. This is the receipt: application number
> **[NUMBER]**, filed **[DATE]** with the **[OFFICE]**. The filing covers the two
> methods you've just watched me demonstrate — the fusion architecture from milestone
> three, and the content-addressed reproducibility from milestone two. Filing costs were
> met from our own funds, not from grant expenditure."

---

## Part 7 — Close (~90 seconds, no commands)

> "So, to summarise Tranche 1.
>
> Infrastructure and performance baselines: delivered — 627 documents a minute, 40
> millisecond median retrieval, on a hundred-thousand-chunk corpus.
>
> Deterministic content-addressed ingestion: delivered — 100 percent hash reproducibility,
> with dedup, incremental edit and clean delete all validated, and you've seen the
> recorded demonstration.
>
> The Context Rehydrator: the retrieval-quality baseline is delivered at 95.8 percent
> recall, well past our target, with the fusion uplift honestly outstanding and a clear
> plan to close it.
>
> Local knowledge-graph extraction: delivered — perfect precision on an adversarial
> labelled set, with an offline visualisation.
>
> The provisional patent: filed, with a receipt number.
>
> Every number I've shown you is regenerable from a committed script in our repository
> with a single command. Both evaluation harnesses exit with an error if the metric
> falls below target, so a regression can't pass silently. And every one of those
> commands runs on this machine, offline.
>
> The written completion report cross-references each of these milestones to its
> artifact, its headline number and the release it shipped in — including a
> consolidated table of every place we fell short of an internal stretch target, with
> the honest number alongside it. Thank you."

---

## Part 8 — Q&A backstops

| Question | Answer |
|---|---|
| "Is it *really* 100 % reproducible, or usually?" | The chunk hash is `sha256(content_hash + index + chunk_text)` — a pure function of file content and chunker config. The harness ingests into two independent stores and compares the full hash set, printing the exact match count (3,000/3,000). Unit tests assert it on every CI run, including in shuffled file order. |
| "Why not one million chunks?" | Same harness, one flag: `--docs 20000`. Wall-clock cost only. The property is structural and doesn't degrade with size. |
| "Does anything leave the device?" | No. Embeddings computed locally with MiniLM, vectors in on-disk LanceDB, metadata in local SQLite. The cloud model is optional and off by default. UPII also runs as a local MCP server so an AI assistant can query this memory — and even that runs in-process, read-only, consent-gated, with every call written to an on-device audit log. |
| "Isn't 95.8 % just semantic search?" | Yes — and we say so in the report, in the README, and in the demo itself. See Part 4. |
| "Why does the relational signal ship at weight zero?" | Because enabling it measurably *hurt* rank-one precision. We'd rather ship the honest default and fix the signal than ship a regression. |
| "Why not the Mac Studio?" | Shipping delay. Procurement invoice is furnished separately. The MoA asks for a representative corpus, not specific hardware. |
| "How large is the test suite?" | 126 passing, 1 skipped. Both eval harnesses fail the build if their metric drops below target. |

---

## Part 9 — Timing sheet

| Segment | Target | Live command? |
|---|---|---|
| Part 1 — Opening | 1:30 | No |
| Part 2 — Milestone 1 | 2:00 | No — pre-generated report |
| Part 3 — Milestone 2 | 2:00 | Yes — `repro_demo.sh` (~90 s) |
| Part 4 — Milestone 3 | 3:00 | Yes — `phase3_demo.sh` (~3 min) |
| Part 5 — Milestone 4 | 2:30 | Yes — `phase4_demo.sh` (~3 min) |
| Part 6 — Milestone 5 | 1:00 | No — receipt on screen |
| Part 7 — Close | 1:30 | No |
| **Total** | **~13:30** | |

Scripts run slightly longer than their narration; let them finish rather than talking
over the output. If you need to trim, Part 2 is the most compressible.

---

## Appendix — artifacts to have ready

| Milestone | Artifact | Regenerate with |
|---|---|---|
| 1 | `bench/results/REPORT.md` | `DOCS=7750 bash scripts/demo/phase1_demo.sh` |
| 2 | `bench/results/scale_REPORT.md`, `docs/phase2_reproducibility_audit.md` | `python scripts/bench/scale_check.py --docs 500 --paras 60` |
| 3 | `eval/results/REPORT.md` | `python eval/run_eval.py --rebuild` |
| 4 | `eval/results/entity_REPORT.md`, `graph.html` | `python eval/run_entity_eval.py --rebuild` |
| 5 | Patent filing receipt | — |
| 6 | `docs/tranche1_completion_report.md` | — |

---

## Document history

Consolidated 2026-08-16 from three superseded documents, all of which contained
materially wrong claims by the time they were retired:

- **`grant_officer_demo_walkthrough.md`** (2026-07-08) — listed Milestone 1 as partial
  with the benchmark "not yet built" (it was built; 627 docs/min); claimed 1M-chunk
  reproducibility in its summary table (the run was 3,000); cited retrieval MRR 0.917 /
  nDCG 0.918 (actual: 0.903 / 0.911); listed the entity eval as "not yet built"
  (precision 1.000); had no MCP coverage; and presented `--w-relational 1.0` as evidence
  fusion was working, which it is not.
- **`jury_progress_demo.md`** (2026-06-30) — scoped to Milestone 2 alone, written when
  that was the current phase. Its narration structure survives in Parts 1, 3 and 8 here.
- **`demo_script.md`** (v0.5, January 2026) — obsolete `python -m upii.cli` invocation
  style and a v0.5 feature framing.

Archived, not deleted, under `docs/_archive/`.
