# Claude Code Prompts — UPII v1.5 (Milestone M1)

> **How to use this file.** Below are **8 phase prompts**. Run them in order. Each phase is 1-2 features, sized so Claude Code can finish it in a single session without losing focus. Between phases, *manually verify* the phase's demo flow and `pytest -q` baseline before pasting the next prompt. If a phase fails verification, fix and re-run that phase before advancing — do not let bugs cascade.
>
> **Dependency graph (read this once before starting):**
>
> ```
> Phase 1 (ambient hardening) ──┬──> Phase 2 (inbox UX polish)
>                               ├──> Phase 4 (curator policy)
>                               └──> Phase 5 (onboarding wizard)
>
> Phase 3 (write + LLM consistency) ── independent ── can run any time after Phase 1
>
> Phase 6 (observability + perf gate) ── depends on Phase 3 (instruments LLM)
>
> Phase 7 (Cmd+Shift+K overlay) ── depends on Phases 1, 3, 6 (binds to hardened ambient + honest LLM + telemetry)
>
> Phase 8 (signed installers + release) ── runs last; ships v1.5.0
> ```
>
> **Recommended cadence:** one phase every 2-4 working days. Phase 7 (overlay) is the largest — budget a full week.
>
> Every prompt is self-contained. Each one starts with mission + read-list + acceptance + verify + report. Paste the entire fenced block into Claude Code from the repo root.

---

## PHASE 1 — Ambient source hardening (Feature #3)

> *Foundation. Everything else builds on a working watcher and a non-buggy inbox.*

```
# Mission

You are working on UPII, a local-first personal memory substrate. The CLI binary is `upii` (entry point `upii.cli:app`). Repo at cwd.

The ambient capture pipeline is partially wired but has known defects that block every downstream v1.5 feature. Fix them. This is a hardening phase — no new features, no new flags beyond what's listed, no architectural changes outside the named files.

Pitch context: I am presenting UPII to a Karnataka government deeptech jury in the next few weeks. The 90-second on-stage demo on Slide 6 of `DataFrontier_UPII_GrandFinale_Deck.pptx` depends on this pipeline working end-to-end on a fresh laptop from a clean `git clone`.

# Read before changing anything

```
README.md
src/upii/cli.py                            # all command stubs already here
src/upii/ambient/watcher.py                # FileSystemSource (polling)
src/upii/ambient/storage.py                # StagingDB
src/upii/ambient/sources.py                # registry
src/upii/core/features.py                  # FeatureFlags + watch_paths
src/upii/ingestion/loader.py
tests/test_ambient.py
tests/test_watcher_advanced.py
tests/test_ingest.py
docs/walkthrough_v1_0.md
```

Capture baseline test count first:

```bash
source venv/bin/activate
pytest tests/ -q
# Record pass/fail counts. You must leave this no worse.
```

# Known bugs (verify each is still present, then fix)

1. **`upii watch <path>` raises ImportError.** `cli.py` does `from upii.ambient.watcher import PollingWatcher`. The module exports `FileSystemSource`, not `PollingWatcher`.
2. **`features.add_watch_path()` is not connected to the running watcher.** It writes `features.yaml` but `FileSystemSource.watch_paths` is loaded from `self.watch_paths` directly. The two systems do not share state. Fix by having the watcher initialise its `watch_paths` from `features.get_watch_paths()` at start, and by having the `watch` command call `source.configure(...)` after registering the path.
3. **Double-insert in `inbox --approve`.** Around lines 419-422 of `cli.py`, `db.add_chunks(chunks)` and `vec.add(chunks)` are each called twice in succession. Approved docs get inserted twice.
4. **`inbox --approve` re-reads from disk.** Calls `loader.load(target['file_path'])`. The staging table already has `parsed_content` — that is what the operator reviewed. Re-reading defeats the audit. Add `StagingDB.get_staging_doc_by_event(event_id)` and use it.
5. **`inbox --approve` skips task extraction.** Explicit `ingest` runs `TaskExtractor`; approve does not. Make approve run it too.
6. **`--reject` flag is declared but no implementation branch.** Add it: set both `events.status` and `staging_docs.status` to `rejected`, write an audit-log entry. Do not delete rows.
7. **`--all` flag is declared but unused.** Implement: list pending + approved + rejected with a status column.
8. **Deleted-event approval crashes** (no file content to promote). Print a clear message ("cannot approve a deletion event"), mark event status as `acknowledged`, do not crash.
9. **Re-approving the same event ID corrupts state.** Make approve idempotent: if event status is already `approved`, print a clear message and exit cleanly.

# New scope (only these)

- Replace the polling watcher with `watchdog` for native FS events. Polling stays as a fallback (5-second interval) if `watchdog` import fails or the path is on a filesystem watchdog does not support (e.g., some network mounts).
- Add `watchdog>=4.0.0` to `requirements.txt` and `pyproject.toml` dependencies.
- Idle CPU usage of the watcher daemon must be measurably lower than the polling version. Capture before/after with `top -pid <upii-pid>` and report the numbers.

# Acceptance criteria — the 8-step demo flow must pass

```bash
# 1. Reset
python scripts/reset_demo_env.py
rm -f upii.db upii.log
rm -rf upii_vectors

# 2. Start watcher (background terminal)
mkdir -p /tmp/upii_demo_inbox
upii watch /tmp/upii_demo_inbox &

# 3. Drop a file
cat > /tmp/upii_demo_inbox/iceye_followup.md <<EOF
# ICEYE follow-up
Sarah confirmed the v3/tasking endpoint is ready.
First test pass scheduled for Nov 1 over Napa Valley.
EOF

# 4. List inbox within 3s
sleep 3
upii inbox
# expect: one pending event, type=created, file path, 120-char preview

# 5. Approve
upii inbox --approve <id_prefix>
# expect: chunks promoted, tasks extracted, audit-log entry

# 6. Ask
upii ask "What did Sarah confirm about v3 tasking?"
# expect: cites Sarah, v3/tasking, Napa Valley

# 7. Reject path
cat > /tmp/upii_demo_inbox/junk.md <<EOF
This is junk that should not enter LTM.
EOF
sleep 3
upii inbox
upii inbox --reject <id_prefix>
# expect: status=rejected, audit-log entry, content NOT in LTM

# 8. Listing modes
upii inbox --all
# expect: pending + approved + rejected, with status column

# Cleanup
pkill -f "upii watch"
```

# Out of scope

- Do **not** touch `LocalLLM` (`src/upii/analysis/llm.py`).
- Do **not** change embedding model or vector store.
- Do **not** add cloud sync / telemetry.
- Do **not** edit `.pptx` files or any `Pitch_Script_*` / `Demo_Recording_*` markdowns at repo root.
- Do **not** delete `staging.db` migrations. If schema changes are needed, ALTER, do not DROP.

# Add tests

At minimum: `test_inbox_approve_uses_staged_content`, `test_inbox_reject`, `test_inbox_idempotent_approve`, `test_watcher_uses_watchdog`, `test_watcher_falls_back_to_polling_on_import_error`.

# Final report

One message: feature-line summary, before/after pytest counts, idle-CPU before/after numbers, new files, deviations + reasons, the 8-step flow output copy-pasted, any concern about jury robustness.
```

---

## PHASE 2 — Inbox Review UX polish (Feature #2)

> *Builds on Phase 1. Makes the inbox a place an operator actually wants to use.*

```
# Mission

UPII's ambient capture pipeline is now hardened (Phase 1). The inbox itself is still too sparse to be operator-friendly. In this phase, add five UX upgrades that turn the inbox from "list of events" into "triage surface."

# Read first

```
src/upii/cli.py                            # current inbox command
src/upii/ambient/storage.py                # StagingDB
src/upii/storage/db.py                     # LTM access for diff/compare
```

Re-baseline:

```bash
source venv/bin/activate
pytest tests/ -q
```

# Five UX additions (single phase, all five required)

1. **Content preview in `upii inbox` listing.** Add a 5th column to the existing table: first 120 chars of `staging_docs.parsed_content`, cut on word boundary, with trailing `…` if truncated. Strip newlines so the preview is single-line.

2. **Batch approve / reject.** New flags: `upii inbox --approve-all` and `upii inbox --reject-all`. Also accept comma-separated id prefixes: `upii inbox --approve a1b2,c3d4,e5f6`. For `--approve-all`, require confirmation (`typer.confirm`) showing the count.

3. **Diff view for modified events.** `upii inbox --diff <id>` — for a `modified` event, fetch the LTM version of the same file (by path or content_hash lineage) and the staged version, then render a unified diff using Python's `difflib` with Rich colourisation (green=added, red=removed). If the file is new (no prior LTM), say so cleanly.

4. **Side-by-side staging vs. LTM comparison.** `upii inbox --compare <id>` — render two Rich `Panel`s side-by-side (use `rich.columns.Columns` or `rich.table.Table` with two columns): left = LTM current state, right = staged content. If LTM is empty, left panel says "no LTM record."

5. **Keyboard-driven triage TUI.** `upii inbox --interactive` — enter a Rich `Live` mode with key bindings:
   - `j` / `k` — next / previous event
   - `a` — approve current event
   - `r` — reject current event
   - `d` — show diff (for modified) or preview (for created)
   - `c` — show compare view
   - `q` — quit
   - Display current event highlighted in the table; bottom bar shows the keybinding cheat sheet.
   
   Use `prompt_toolkit` or `readchar` for single-key input (add to requirements). The mode exits when no pending events remain or `q` is pressed.

# Acceptance criteria

Re-run Phase 1's 8-step demo, then:

```bash
# Drop 3 files
for i in 1 2 3; do
  cat > /tmp/upii_demo_inbox/file_$i.md <<EOF
# File $i
Content $i.
EOF
done
sleep 3

# Listing now shows preview column
upii inbox

# Batch approve two of them
upii inbox --approve <id1>,<id2>

# Reject all remaining
upii inbox --reject-all

# Modify a previously approved file
echo "Updated content for file 1." >> /tmp/upii_demo_inbox/file_1.md
sleep 3

# Diff view
upii inbox --diff <new_modified_event_id>
# expect: unified diff with the appended line highlighted

# Compare view
upii inbox --compare <new_modified_event_id>
# expect: two side-by-side panels

# Interactive triage
upii inbox --interactive
# expect: TUI with j/k/a/r/d/c/q working
```

# Out of scope

- Do not modify the approval logic itself from Phase 1.
- Do not introduce a graphical UI (TUI only).
- Do not change StagingDB schema beyond adding indexes if query performance demands it.

# Add tests

`test_inbox_preview_truncation`, `test_inbox_batch_approve`, `test_inbox_diff_modified_event`, `test_inbox_compare_with_empty_ltm`. The interactive TUI is exempt from unit tests (manual verification only — note this in the report).

# Final report

Feature line summary; before/after pytest; new dependencies added; the demo flow output above; one screenshot of the interactive TUI (terminal screencap, attached as a base64 string or saved file path).
```

---

## PHASE 3 — `write` style synthesis + LLM consistency (Features #5, #6)

> *Independent of Phase 1/2. Tightens the two output-quality commands (`write` and `ask`) so they behave deterministically.*

```
# Mission

`upii write` and `upii ask` are the two commands a jury will actually run during Q&A. Both have inconsistency problems today. Fix them in one phase because they share the underlying `LocalLLM` and benefit from a single per-command temperature profile system.

# Read first

```
src/upii/cli.py                            # write + ask commands
src/upii/analysis/llm.py                   # LocalLLM (Gemini + Ollama + mock)
src/upii/core/config.py                    # already has user_name="Maddy" and rag_min_similarity=0.5
src/upii/analysis/search.py                # SearchEngine
src/upii/analysis/rehydration.py           # ContextRehydrator + RankedChunk
src/upii/ingestion/loader.py               # LocalLoader (extend with frontmatter parsing)
src/upii/core/types.py                     # Document + Chunk + RankedChunk
```

Baseline:

```bash
pytest tests/ -q
```

# Known issues

**`write` (in `cli.py`):**
- Style query is a placeholder (`engine.search("email from me", limit=3)` with inline comment "Hypothetical query").
- Signature is hardcoded `"sign it as 'Maddy'"` instead of pulling from `config.user_name`.
- No per-target length enforcement (tweet exceeds 280 chars; LinkedIn unbounded).
- Subject-line extraction for email is non-deterministic — LLM may or may not include `Subject:`.
- No retry-on-overflow mechanism.

**`ask` and `LocalLLM`:**
- `LocalLLM.generate()` uses default temperature; calls from `ask` and from `write` should use different temperatures.
- `ask` does not enforce a confidence threshold — if all retrieved chunks score below `config.rag_min_similarity`, the model still answers and may hallucinate.
- First-call latency includes Ollama / sentence-transformer cold start (5-15s); on stage this looks broken.

# New scope

**A. Markdown frontmatter parsing in `LocalLoader`.**

For `.md` files, parse YAML frontmatter (lines between `---` markers at file top). Extract these fields into `Document.metadata`:
- `author` → `metadata['author']`
- `tags` → `metadata['tags']` (list)
- `created` → `metadata['created']` (ISO date)
- Any other key → stored as-is in metadata.

Frontmatter is optional — files without it work as today.

**B. Per-command temperature profiles in `LocalLLM`.**

Add a `mode` parameter to `LocalLLM.generate(prompt, mode='default')`. Modes:
- `'honest'` — temperature 0.1 (or equivalent Gemini setting), used by `ask`.
- `'creative'` — temperature 0.8, used by `write`.
- `'default'` — temperature 0.5, used by everything else.

For Ollama, pass `options={'temperature': X}`. For Gemini, include `generationConfig: {temperature: X}` in the request body.

**C. Confidence threshold in `ask`.**

In the `ask` command, after retrieval:
- Compute `max_score = max(chunk.score for chunk in results)` over the returned `RankedChunk` list.
- If `max_score < config.rag_min_similarity` (currently 0.5), do **not** call `answer_with_citations`. Instead, return the exact string:
  `"I don't know. No retrieved context met the confidence threshold (max score: {max_score:.2f} < {threshold:.2f})."`
- This must be a string the existing `cli.py` line 194 check (`"I don't know" not in answer`) can detect, so the `Sources used:` block is suppressed correctly.

**D. Production-grade `write`.**

- Add `config.user_name` reference where signature is currently hardcoded.
- Filter style examples by `Document.metadata.get('author') == config.user_name`. If no self-authored docs exist, log a warning ("no style examples found; using neutral tone") and proceed without style injection.
- Post-processor by target:
  - `email`: parse output for `Subject:` line. If absent, deterministically extract first sentence as subject (max 80 chars) and prepend `Subject: ...\n\n`. Re-format as `Subject: <subject>\n\n<body>` wrapped in the existing Rich `Panel`.
  - `tweet`: enforce ≤ 280 chars. If over, re-prompt the LLM with `"Shorten to under 280 characters: <current draft>"` (up to 2 retries). After retries, truncate at the nearest word boundary before 277 chars and append `…`.
  - `linkedin`: aim for ≤ 1300 chars. Same retry pattern. Final truncation at 1297 with `…`.
- Use `mode='creative'` when calling LocalLLM.

**E. LLM pre-warm.**

Add a `LocalLLM.warmup()` method that runs a 1-token dummy generation in a background thread. Call it from the Typer `main()` callback so first user command finds the model warm.

Acceptable cold-start budget: < 500 ms after warmup completes. If warmup is still running when the first command fires, fall back gracefully (no error, just slower first response).

# Acceptance criteria

```bash
# 1. Frontmatter parsing
cat > /tmp/style_test.md <<EOF
---
author: Maddy
tags: [test]
---
# My note
Body content here.
EOF
upii ingest /tmp/style_test.md
# Verify metadata['author'] = 'Maddy' was stored (check via sqlite3 inspection or new test)

# 2. write — email
upii write "Confirm Nov 1 ICEYE test pass with Sarah" --target email
# expect: Panel with "Subject: ..." on line 1, body below, signed with user_name

# 3. write — tweet
upii write "Releasing UPII v1.5 with sovereign memory layer" --target tweet
# expect: ≤ 280 chars, no truncation marker if LLM cooperates

# 4. write — linkedin
upii write "Why DPDP is forcing Indian enterprises to rethink AI architecture" --target linkedin
# expect: ≤ 1300 chars

# 5. ask honest-mode — known answer
upii ask "What was the ICEYE resolution?"
# expect: clear answer with Sources used

# 6. ask honest-mode — unknown answer
upii ask "What is the launch date for Project Alpha?"
# expect: "I don't know. No retrieved context met the confidence threshold..."
# expect: NO Sources used block

# 7. Pre-warm
time upii doctor    # first call cold
time upii ask "test"  # subsequent call should be fast
```

# Out of scope

- Do not change retrieval (`ContextRehydrator`).
- Do not change embedding model.
- Do not add new LLM backends.
- Do not modify the `--debug` boost reason output (Phase 6 instruments timings).

# Tests

`test_loader_parses_frontmatter`, `test_write_signs_with_config_user_name`, `test_write_email_extracts_subject`, `test_write_tweet_enforces_length`, `test_ask_honest_mode_below_threshold`, `test_llm_temperature_modes`, `test_llm_warmup_does_not_block`.

# Final report

Feature lines; before/after pytest; latency numbers (cold vs warm `ask`); confirmation that all 7 acceptance checks pass; one paragraph on which `write` topics produced the cleanest output (this will inform the demo).
```

---

## PHASE 4 — Curator auto-policy (Feature #4)

> *Builds on Phase 1 (needs working watcher) and Phase 2 (so policy actions interact with the polished inbox). Independent of Phase 3.*

```
# Mission

Add an opt-in policy engine that pre-classifies staged events so the operator approves *policies*, not individual events. The point is to reduce inbox fatigue without giving up the human-in-the-loop trust property of v1.0.

# Read first

```
src/upii/cli.py                          # for inbox + watch
src/upii/ambient/watcher.py              # FileSystemSource._handle_change
src/upii/ambient/storage.py
src/upii/core/features.py                # extend with policies, or new policies.yaml
src/upii/core/config.py
```

Baseline pytest.

# Design

**Policy schema (YAML):**

```yaml
policies:
  - name: auto_work_notes
    path_glob: "~/work/notes/**/*.md"
    action: auto-approve
    file_types: [".md", ".txt"]
    
  - name: review_downloads
    path_glob: "~/Downloads/**/*"
    action: always-review
    
  - name: ignore_temp
    path_glob: "/tmp/**/*.tmp"
    action: ignore
```

Three actions:
- `auto-approve` — bypass staging entirely, run the approve flow directly. Audit-logged with policy name in details.
- `always-review` — stage in inbox as today. (This is the default if no policy matches.)
- `ignore` — log to audit ("ignored by policy {name}"), do not stage.

**Storage:** new file `policies.yaml` at the same level as `features.yaml`. Read at watcher start and on `upii policy reload`.

**CLI surface:**

- `upii policy list` — table of active policies.
- `upii policy add` — interactive prompt: name, path_glob, action, optional filters. Validates the glob, writes to `policies.yaml`.
- `upii policy remove <name>` — remove by name.
- `upii policy test <path>` — dry-run a given path against all policies. Prints which policy (if any) would match and what action would fire.
- `upii policy reload` — re-read `policies.yaml` without restarting the watcher.

**Watcher integration:**

In `FileSystemSource._handle_change`, before staging:
1. Consult policy engine: `policy = PolicyEngine.match(path)`.
2. If `policy.action == 'ignore'`: log audit, return.
3. If `policy.action == 'auto-approve'`: stage AND immediately run approve flow. Audit-log with `auto_approved_by_policy: <name>`.
4. If `policy.action == 'always-review'` or no policy: stage as today.

# Acceptance criteria

```bash
# Setup three policy zones
mkdir -p /tmp/upii_work_notes /tmp/upii_downloads /tmp/upii_tmp

# Add policies
upii policy add  # interactive: name=auto_work, path=/tmp/upii_work_notes/**, action=auto-approve
upii policy add  # interactive: name=review_dl, path=/tmp/upii_downloads/**, action=always-review
upii policy add  # interactive: name=ignore_tmp, path=/tmp/upii_tmp/**, action=ignore

upii policy list   # expect: 3 policies

# Watch all three
upii watch /tmp/upii_work_notes &
upii watch /tmp/upii_downloads &
upii watch /tmp/upii_tmp &
sleep 1

# Test routing
echo "work content" > /tmp/upii_work_notes/note.md
echo "download content" > /tmp/upii_downloads/doc.md
echo "temp content" > /tmp/upii_tmp/tmp.md
sleep 3

# Verify
upii inbox --all
# expect: doc.md = pending (review_dl), note.md = approved (auto_work),
#         tmp.md NOT listed (ignored)

upii ask "what's in note.md?"
# expect: real answer (work_notes was auto-approved into LTM)

upii sources audit | tail -10
# expect: audit entries for all three policies firing

# Dry-run
upii policy test /tmp/upii_work_notes/new_file.md
# expect: "Matches policy 'auto_work' → action: auto-approve"

# Cleanup
pkill -f "upii watch"
```

# Out of scope

- No regex policies — globs only (use `fnmatch` or `pathlib.Path.match`).
- No content-pattern matching — path-based only in this phase. (Could extend in v2.)
- No GUI for policy management — CLI only.
- Do not modify the inbox listing or approve logic from Phases 1-2.

# Tests

`test_policy_engine_matches_glob`, `test_policy_auto_approve_bypasses_staging`, `test_policy_ignore_logs_audit_no_stage`, `test_policy_no_match_defaults_to_review`, `test_policy_test_dry_run`.

# Final report

Feature line; pytest counts; demo flow output; one note on whether any pilot/operator would actually want a fourth action (e.g., "tag-and-review") that is worth deferring to v2.
```

---

## PHASE 5 — First-run onboarding wizard (Feature #8)

> *Independent of Phases 3/4 in principle, but easier to write after them so the wizard demo is end-to-end real.*

```
# Mission

Add `upii setup` — a 60-second guided first-run experience that takes a fresh user from zero to a working substrate with one approved document, one ask query, and the wizard flag set.

This is the converter from "I installed it" to "I have a memory." Pilot conversion rate today is bounded by people not finishing setup.

# Read first

```
src/upii/cli.py
src/upii/core/config.py
src/upii/core/features.py
README.md
```

# Design

**Trigger:** `upii setup` — also auto-prompted on every CLI call if `features['wizard_completed']` is `False` (with a `--skip-wizard` escape).

**Steps (use Rich for prompts):**

1. **Welcome + privacy promise.** One screen: "UPII runs entirely on your laptop. No data is ever sent to a remote server unless you explicitly ingest from one. Press Enter to begin."

2. **Identity.** Prompt for name → write `user_name` to `.upii_config.yaml`. Default = `os.environ.get("USER", "Operator")`.

3. **Pick a folder to watch.** Prompt with default `~/Documents/upii_inbox/`. Create if it doesn't exist. Call `features.add_watch_path(path)`. Spawn the watcher in the background.

4. **Drop-a-file moment.** Print: "Now drop or save a markdown file into `<path>`. I'll wait." Poll the staging DB once per second; when an event appears (timeout 120 s), proceed. If timeout, write a sample file ourselves and tell the user.

5. **Approve walkthrough.** Show the inbox listing with the just-staged event. Explain the row. Ask "Approve this? [Y/n]". If yes, run approve. Audit-logged.

6. **First query.** Generate a sensible question from the file content (use LLM in `mode='default'`: prompt = "Given this document content: <first 500 chars>, what is one simple question I could ask about it?"). Print "Suggested query: \"<q>\". Run it? [Y/n]". If yes, run `ask` and show the answer with sources.

7. **Done.** Set `features['wizard_completed'] = True`. Print three next-step commands:
   - `upii inbox` — see what's in your staging area
   - `upii write "topic" --target email` — draft in your voice
   - `upii metrics show` — see your activity

# Acceptance criteria

```bash
# Clean slate
rm -rf ~/.upii_config.yaml upii.db staging.db features.yaml
rm -rf ~/Documents/upii_inbox

# Run wizard
upii setup
# Walk through interactively. Total wall-clock < 90 seconds.

# Verify final state
cat ~/.upii_config.yaml | grep user_name
cat features.yaml | grep wizard_completed
upii inbox --all       # one approved event
upii metrics show      # one query, one passive ingest

# Re-running should be a no-op
upii setup
# expect: "Wizard already completed. Re-run with --force?"
```

# Out of scope

- No GUI wizard — terminal only.
- No multi-folder watch in the wizard (one is enough).
- Do not wire the wizard into Phase 7's overlay.

# Tests

`test_wizard_writes_user_name_to_config`, `test_wizard_creates_watch_folder`, `test_wizard_sets_completed_flag`, `test_wizard_idempotent_on_rerun`. For the interactive flow, use Typer's `runner.invoke(app, ["setup"], input="\nMaddy\n\nY\nY\n")` style scripted input.

# Final report

Feature line; pytest counts; the actual recorded wall-clock for a full wizard run (record with `time`); one paragraph on which steps a non-engineer found friction at (test with Veena before submitting).
```

---

## PHASE 6 — Observability + Performance gate (Features #10, #9)

> *Depends on Phase 3 (LLM mode parameter must exist so we can instrument it). Sets up the CI gate that protects every subsequent phase.*

```
# Mission

Make UPII's latency and accuracy claims defensible by (a) instrumenting per-retriever timing all the way through the rehydration pipeline, (b) exposing those timings in `upii metrics show` and a CISO-grade audit packet, and (c) wiring a CI benchmark that fails the build on regression.

# Read first

```
src/upii/analysis/rehydration.py           # ContextRehydrator
src/upii/analysis/metrics.py               # MetricsCollector
src/upii/analysis/llm.py                   # LocalLLM (instrument generate())
src/upii/analysis/search.py
src/upii/cli.py                            # metrics command
src/upii/core/types.py                     # RankedChunk
tests/perf/test_long_running.py
.github/workflows/release.yml
```

Baseline pytest.

# Scope

**A. Per-retriever timing instrumentation.**

In `ContextRehydrator.rehydrate`:
- Wrap each retrieval stage (vector / temporal / entity) in a high-resolution timer (`time.perf_counter_ns`).
- Wrap the LLM call in the same.
- Store the timings on a new `RetrievalTrace` dataclass (or attach to RankedChunk list as a sibling).
- Return the trace alongside the chunks (extend the function signature or add a new method that returns both).

Fields in `RetrievalTrace`:
- `vector_ms: float`
- `temporal_ms: float`
- `kg_ms: float`
- `llm_ms: float`
- `total_ms: float`
- `query: str`
- `timestamp: ISO datetime`

**B. Persist traces.**

Add a `retrieval_traces` table in `upii.db`:

```sql
CREATE TABLE IF NOT EXISTS retrieval_traces (
    trace_id TEXT PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    query TEXT,
    vector_ms REAL,
    temporal_ms REAL,
    kg_ms REAL,
    llm_ms REAL,
    total_ms REAL,
    result_count INTEGER
);
```

`MetricsCollector` writes one row per `ask` invocation.

**C. Extend `upii metrics show`.**

Add a section after the daily rollup: "Latency (last 50 queries)":

```
Retriever     p50      p95      p99
vector        45 ms    120 ms   210 ms
temporal      8 ms     22 ms    45 ms
kg            12 ms    35 ms    80 ms
llm           180 ms   420 ms   650 ms
total         245 ms   290 ms   380 ms
```

**D. Audit packet export.**

`upii metrics export --audit-packet --out audit.json` — JSON with:
- All daily_metrics rows
- All retrieval_traces rows (with timestamps, queries hashed for privacy)
- All audit_logs from staging.db
- A signature line: SHA-256 hash of the rest of the document, with `signed_by: <user_name>`, `signed_at: <iso>`. This is not a real cryptographic signature — it's a tamper-evidence hash. (Real signing comes in v3.)

**E. Benchmark scripts.**

Create:

- `scripts/benchmark_latency.py` — ingests `demo_data_v2/`, runs N=50 queries from a fixed list, reports p50/p95/p99 per retriever and total, outputs `benchmark_latency.json`. Exit code 1 if total p95 > 300 ms.

- `scripts/benchmark_accuracy.py` — ingests `demo_data_v2/`, runs a golden set of (query, expected_doc_substring) pairs, computes top-3 accuracy, outputs `benchmark_accuracy.json`. Exit code 1 if accuracy < 0.90.

Hardcode 10 golden pairs in the script (ICEYE / PACE / Stream-First / Project Omega / etc., based on the demo_data_v2 content).

**F. CI gate.**

New file `.github/workflows/benchmark.yml`:
- Triggers: on push to main, on PR to main.
- Steps: install, ingest, run both benchmarks. Upload artifacts. Fail build on non-zero exit.

# Acceptance criteria

```bash
# Local
upii ingest demo_data_v2/
for q in "ICEYE resolution" "PACE calibration" "Stream-First architecture"; do
  upii ask "$q"
done

upii metrics show
# expect: latency table at the bottom

upii metrics export --audit-packet --out audit.json
cat audit.json | jq .signature
# expect: SHA-256 hex string

python scripts/benchmark_latency.py
# expect: exit 0; benchmark_latency.json written

python scripts/benchmark_accuracy.py
# expect: exit 0; accuracy >= 0.90

# CI: simulate a regression
# Modify rehydration.py to add time.sleep(0.5) in vector path
# Run benchmark — must exit 1
```

# Out of scope

- Do not change retrieval logic itself (no accuracy improvements in this phase).
- Do not add Prometheus / external telemetry.
- Do not change the audit-log schema in staging.db.

# Tests

`test_rehydrator_returns_trace`, `test_metrics_writes_trace_row`, `test_metrics_show_latency_table`, `test_audit_packet_has_signature`, `test_benchmark_latency_exits_nonzero_on_regression`, `test_benchmark_accuracy_loads_golden_set`.

# Final report

Feature lines; pytest counts; the actual p50/p95/p99 numbers measured on your dev laptop; a one-line statement of whether the 300 ms P95 claim in the pitch deck (Slide 7) is honest at current code state. If P95 exceeds 300 ms, say so plainly and recommend either lowering the claim or which retriever needs optimisation first.
```

---

## PHASE 7 — Cmd+Shift+K Global Overlay (Feature #1)

> *Largest phase by surface area. Depends on Phases 1, 3, 6 being green. Platform-specific; expect adjustments per OS.*

```
# Mission

Build the system-wide overlay called out in Slide 13 of `DataFrontier_UPII_GrandFinale_Deck.pptx`: press Cmd+Shift+K (Mac) or Ctrl+Shift+K (Windows) from any application, a translucent query window appears, you ask a question, the answer appears in <300 ms P95 with click-to-source evidence.

This is the most visible v1.5 feature and the one a jury will ask to see live.

# Read first

```
src/upii/cli.py
src/upii/analysis/search.py
src/upii/analysis/llm.py
src/upii/analysis/rehydration.py
docs/walkthrough_v1_0.md
README.md
```

Also research the right primitives:
- macOS: PyObjC, `AppKit.NSPanel` for translucent floating panel, `Quartz` event tap for global hotkey.
- Windows: `pywin32` + `ctypes` for `RegisterHotKey`; `tkinter` or `PyQt6` for transparent always-on-top window.

If you can't reliably get PyObjC working in the dev environment, use `rumps` for the menu bar and `tkinter` with `wm_attributes("-transparent")` as the cross-platform fallback. Document the decision in the report.

# Design

**Daemon model:**
- `upii overlay start` — spawns a background process that registers the global hotkey, runs an event loop, exits cleanly on SIGTERM.
- `upii overlay stop` — signals the daemon to exit.
- `upii overlay status` — prints running/not running + PID.
- `upii overlay logs` — tails the daemon log.

**Window:**
- 600×400, centred on the active display, translucent (alpha ~0.95), always-on-top, no titlebar.
- Single text input at the top (auto-focused).
- Results pane below — markdown-rendered answer, then a horizontal rule, then numbered source citations.
- Each source citation is clickable: opens the source file with the OS default app (`open <path>` on Mac, `start "" <path>` on Windows).
- Escape closes the window.
- Cmd/Ctrl+Shift+K toggles visibility.

**Wiring:**
- The overlay process imports `SearchEngine`, `LocalLLM`, `ContextRehydrator`. Reuses the existing substrate — no duplicate state.
- On query: call `rehydrate(query)` → `llm.answer_with_citations(query, chunks, mode='honest')` (from Phase 3). Render result. Record trace (from Phase 6).
- Target latency: hotkey-press → first character of answer rendered < 300 ms P95. Pre-warm the LLM on daemon start.

**Fallback CLI mode:**
- If the daemon fails to start (e.g., AppleEvents permission denied, or `pywin32` import error), `upii overlay start` prints a clear message: "Overlay unavailable on this system. Use `upii ask \"...\"` from the terminal." Exit code 0 (not an error — the substrate still works).

# Acceptance criteria

Manual verification on Mac + Windows:

```bash
# Mac
upii overlay start
# Press Cmd+Shift+K from any app (browser, mail, Slack)
# Window appears in <100 ms
# Type "What did Sarah confirm about v3 tasking?"
# Answer appears in <300 ms P95
# Click source citation → opens the .md file in default editor
# Press Esc → window closes
# Press Cmd+Shift+K again → window reappears
upii overlay stop

# Windows (same flow with Ctrl+Shift+K)

# Fallback
# On a system without PyObjC/pywin32 (e.g., a Linux dev env):
upii overlay start
# expect: "Overlay unavailable on this system. Use `upii ask`..."
```

# Out of scope

- No multi-monitor handling beyond "centred on active display."
- No themes / customisation (one translucent style only).
- No conversation history in the overlay (single-turn only). History is a v2 feature.
- No keyboard shortcut customisation (Cmd+Shift+K hardcoded; user can edit `~/.upii_config.yaml` to override but no CLI flag).

# Tests

Hard to unit-test platform-specific code. At minimum:
- `test_overlay_daemon_starts_and_stops` (verify PID file lifecycle)
- `test_overlay_fallback_message_on_missing_deps` (mock the import errors)
- `test_overlay_query_invokes_rehydrator` (mock the GUI, verify the substrate call)

Manual test checklist in the report:
- [ ] Mac: hotkey works from Chrome
- [ ] Mac: hotkey works from Slack
- [ ] Mac: hotkey works from full-screen app
- [ ] Mac: click-source opens file
- [ ] Mac: daemon survives screen sleep/wake
- [ ] Windows: hotkey works from Edge
- [ ] Windows: hotkey works from Outlook
- [ ] Windows: click-source opens file
- [ ] Both: fallback message when deps missing

# Final report

Feature line; chosen platform primitives (PyObjC vs alternatives); measured hotkey-to-first-character latency on dev laptop; the manual test checklist with pass/fail per row; one honest paragraph on whether this would survive a 30-minute live demo or whether the fallback CLI is the safer demo path.
```

---

## PHASE 8 — Signed installers + v1.5.0 release (Feature #7)

> *Runs last. Tags v1.5.0 with signed artifacts. Assumes all prior phases are green.*

```
# Mission

Sign and ship UPII v1.5.0 as installer packages that don't trigger "unidentified developer" dialogs. This is the difference between pilots installing UPII in two minutes versus pilots emailing the founder asking for help.

# Read first

```
.github/workflows/release.yml
upii.spec                          # PyInstaller spec
scripts/                           # build.sh, build.bat if present
release/mac/README.md
release/windows/README.md
pyproject.toml
```

Baseline pytest, run full demo from earlier phases.

# Scope

**A. Mac signing + notarisation.**

- Sign the PyInstaller-built binary with Apple Developer ID Application certificate (the cert is already enrolled — config secret name `APPLE_DEV_ID_CERT_P12` and `APPLE_DEV_ID_PASSWORD`).
- Use `codesign --force --options runtime --sign "Developer ID Application: ..." dist/upii.app`.
- Build a `.pkg` installer using `pkgbuild` and `productbuild`, signed with `productsign`.
- Notarise via `notarytool submit ... --wait` (secrets: `APPLE_NOTARY_USER`, `APPLE_NOTARY_TEAM_ID`, `APPLE_NOTARY_PASS`).
- Staple notarisation: `xcrun stapler staple`.
- Output artifact: `UPII-1.5.0-mac.pkg`.

**B. Windows signing.**

- Sign with Authenticode using `signtool.exe` (secrets: `WINDOWS_CERT_P12` base64-encoded, `WINDOWS_CERT_PASS`).
- Use `signtool sign /f cert.pfx /p ... /tr http://timestamp.digicert.com /td sha256 /fd sha256 dist\upii.exe`.
- Build an MSI installer using `WiX Toolset` (or `pyinstaller` + a minimal MSI wrapper). Sign the MSI too.
- Output artifact: `UPII-1.5.0-win.msi`.

**C. Updated release workflow.**

Modify `.github/workflows/release.yml`:
- After PyInstaller build, run signing step (per OS).
- Add notarisation step on Mac.
- Upload signed installers (not the unsigned binaries) as artifacts.
- Attach to GitHub Release.

**D. Version bump.**

- `pyproject.toml`: `version = "1.5.0"`.
- Tag: `git tag v1.5.0`.

**E. Release notes.**

Generate `RELEASE_NOTES_v1.5.0.md` summarising all 7 prior phases. Use the bullet structure from `UPII_Version_Roadmap.md` §v1.5 — each bullet becomes a release-note line. Include the benchmark numbers from Phase 6.

# Acceptance criteria

```bash
# Tag and push
git tag v1.5.0
git push origin v1.5.0

# CI runs the release workflow. Wait.
# Download the two artifacts from the GitHub Release.

# Mac: install on a clean macOS VM (no Xcode, no developer tools)
sudo installer -pkg UPII-1.5.0-mac.pkg -target /
which upii
upii doctor
# expect: no "unidentified developer" Gatekeeper dialog at any point

# Windows: install on a clean Windows 11 VM
msiexec /i UPII-1.5.0-win.msi /quiet
where upii
upii doctor
# expect: no SmartScreen warning

# Repeat on a second clean machine per platform (target: 2 non-developer machines per OS per the Slide 14 success criteria).
```

# Out of scope

- No auto-update mechanism (defer to v2).
- No Linux build in this phase (the pitch is Mac + Windows focused).
- No Homebrew / Chocolatey distribution (defer to v2).

# Tests

CI integration tests:
- `test_release_workflow_produces_signed_mac_pkg` (CI artifact present)
- `test_release_workflow_produces_signed_windows_msi`
- `verify_macos_signature.sh` — runs `codesign -dv` and `spctl --assess` on the .pkg
- `verify_windows_signature.bat` — runs `signtool verify /pa /v` on the .msi

# Final report

Feature line; CI run URL; manual install test results from two machines per OS; any code-signing complications (cert chain issues, notarisation rejections — these are common, document them); the final v1.5.0 release page URL.

Tag this phase done only after the v1.5.0 release page on GitHub has both signed artifacts and a working `upii doctor` confirmation from at least one tester who is not the developer.
```

---

# Integration smoke test (run after Phase 8)

After v1.5.0 is tagged, run this single end-to-end script on a fresh laptop. If it passes, M1 is done:

```bash
# 1. Install
curl -L https://github.com/<org>/upii/releases/download/v1.5.0/UPII-1.5.0-mac.pkg -o /tmp/upii.pkg
sudo installer -pkg /tmp/upii.pkg -target /

# 2. Onboard
upii setup
# Wizard walks through. Wall-clock < 90 s.

# 3. Hotkey
upii overlay start
# Press Cmd+Shift+K, ask a question, click a source.

# 4. Policy
upii policy add  # auto-approve from ~/Documents/upii_inbox
# Drop a file → check it lands directly in LTM via audit log.

# 5. Write
upii write "Confirming meeting with Sarah on Friday" --target email

# 6. Audit packet
upii metrics export --audit-packet --out /tmp/audit.json
jq .signature /tmp/audit.json

# 7. CI gate
# Open the GitHub Actions tab for the v1.5.0 tag.
# Verify: benchmark.yml passed, release.yml signed both installers.
```

If every step is green: tag v1.5.0 as the M1 deliverable to ELEVATE NxT, update the deck's Slide 14 with the actual benchmark numbers, and move to Phase 1 of v2.0 (enterprise connectors).

---

# A note on cadence and reality

The 8 phases above represent roughly 8-12 working weeks of focused engineering at the current pace of the repo. M1's nominal budget is 16 weeks (months 0-4), so there is headroom — but every phase will discover at least one unknown unknown (especially Phase 7's platform-specific overlay work, which is notorious for OS-version-specific bugs).

If you fall behind: **the safe cuts in priority order are Phase 8 (ship unsigned for the demo), Phase 7 (fall back to CLI for the live demo), Phase 5 (skip wizard, document a manual setup)**. Do not cut Phase 1 (hardening), Phase 3 (write/ask consistency), or Phase 6 (the CI gate that protects everything else from regression).

The jury will not penalise an unsigned binary if the live demo works. The jury will penalise a hotkey demo that misfires on stage. Plan accordingly.
