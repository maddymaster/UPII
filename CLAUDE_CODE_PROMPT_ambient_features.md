# Claude Code Build Prompt — UPII Ambient Features

> Paste everything inside the `---` fences into Claude Code (or run `claude` from the repo root and paste it as your first message). The prompt is self-contained — Claude Code does not need any of this conversation's context. Notes for the human (you) sit outside the fences.

---

# Mission

You are working on UPII, a local-first personal memory substrate written in Python. The CLI binary is `upii` (entry point: `upii.cli:app`, see `src/upii.egg-info/entry_points.txt`). The repo is at the current working directory.

Three Slide-5 demo capabilities are partially scaffolded but not actually working. I am pitching this to a Karnataka government deeptech jury in the next few days, and Slide 6 of my deck (`DataFrontier_UPII_GrandFinale_Deck.pptx`) shows a live 90-second CLI demo that depends on these features. Your job is to make them work end-to-end.

The three features to fix and complete:

1. **`upii watch <path>`** — opt-in filesystem watcher that captures changes into a staging DB.
2. **`upii inbox --approve <id>`** — review staged events and promote approved ones to long-term memory (LTM).
3. **`upii write "<topic>" --target email`** — draft a reply/message in my voice, grounded in retrieved context.

The features chain into one demo flow: `watch` populates the inbox, `inbox --approve` promotes to LTM, `ask` and `write` use that LTM. Failure of any one breaks the demo.

# Read before changing anything

Spend the first 5 minutes reading these files. Do not skim — the prompt below assumes you know what they actually do today.

```
README.md
src/upii/cli.py                              # All three command stubs already exist here
src/upii/ambient/watcher.py                  # FileSystemSource — polling watcher
src/upii/ambient/storage.py                  # StagingDB schema (events, staging_docs, audit_logs)
src/upii/ambient/sources.py                  # Source registry pattern
src/upii/core/features.py                    # FeatureFlags singleton + watch_paths
src/upii/analysis/llm.py                     # LocalLLM (Gemini + Ollama + mock fallback)
src/upii/analysis/search.py                  # SearchEngine
src/upii/ingestion/loader.py                 # LocalLoader
src/upii/ingestion/chunker.py                # RecursiveChunker
src/upii/storage/db.py                       # Main LTM DB
src/upii/storage/vector.py                   # LocalVectorStore (LanceDB)
tests/test_ambient.py
tests/test_watcher_advanced.py
tests/test_ingest.py
docs/demo_script.md
project_docs/investor_demo_v1.md
project_docs/walkthrough_v1_0.md             # If it exists; otherwise skip
```

Run the existing test suite once before changing anything so you know what was passing on arrival:

```bash
source venv/bin/activate
pytest tests/ -q
```

Capture the baseline pass/fail count. You will be expected to leave it no worse than you found it.

# Known bugs and gaps (do not just trust the stubs — verify these)

I have read the stubs. They look more complete than they are. Concretely:

### `upii watch <path>` — broken at import time

`src/upii/cli.py` does:

```python
from upii.ambient.watcher import PollingWatcher
```

But `src/upii/ambient/watcher.py` exports `FileSystemSource`, not `PollingWatcher`. This is an `ImportError` the moment the user runs `upii watch <path>`. Beyond the import:

- The command calls `features.add_watch_path(abs_path)` (writes to `features.yaml`), but `FileSystemSource.start()` reads from `self.watch_paths`, not from `features.get_watch_paths()`. The two systems are not connected. Configuring the source registry instance with the new path is the missing wire.
- The command runs the watcher in the foreground (`while True: time.sleep(1)`). That's fine for the demo, but make sure `Ctrl+C` cleanly stops the watcher thread (the existing `stop()` method joins with a 2-s timeout — confirm it actually exits).
- The watcher polls every 2 s and only catches `.md`, `.txt`, `.pdf` files. The demo will use `.md` — leave the filter as-is unless tests demand otherwise.

### `upii inbox` — listing and approve both have gaps

In `inbox()` in `cli.py`:

- **Double-insert bug.** Around lines 419-422, `db.add_chunks(chunks)` and `vec.add(chunks)` are each called twice in succession inside the approve branch. Every approved doc gets ingested twice. Fix.
- **Wrong content source.** The approve branch calls `loader.load(target['file_path'])` to re-read the file from disk. The whole point of staging is to pin the content that the operator reviewed — re-reading defeats that. Use `staging_docs.parsed_content` for the approved staging_id instead. (You may need to add a `StagingDB.get_staging_doc_by_event(event_id)` accessor — current `storage.py` doesn't expose one.)
- **No task extraction on approve.** The explicit `ingest` command runs `TaskExtractor` on chunks; approve doesn't. Make approve run it too, so the auto-extracted tasks beat from Slide 5 ("audit-logged capture, tasks extracted") works whether the ingest was explicit or ambient.
- **Listing is too sparse.** Today it shows ID / type / file / time. Add a short content preview (first 120 chars of `parsed_content`) so the operator can decide without opening the file. Truncate cleanly on word boundary.
- **`--reject` does nothing.** The flag is declared and parsed, but there's no `if reject:` branch. Implement: set both the event and staging_doc rows to status `rejected`, log to audit. Do not delete — the audit trail must survive rejection.
- **`--all` does nothing.** Either implement (list rejected + approved too, with a status column) or remove the flag. Implementing is preferred — it makes the audit story stronger.
- **Deleted-file events crash approve.** If the staged event is a `deleted` event, there's no content to promote. Return a clear "cannot approve a deletion event" message and mark the event status as `acknowledged` (new status — add to schema if needed).

### `upii write "<topic>" --target email` — placeholder style logic

In `write()` in `cli.py`:

- The "style extraction" runs `engine.search("email from me", limit=3)` with an inline comment that says it's hypothetical. There is no actual mechanism to find "things written by me." Two acceptable fixes:
  - **(a) Minimum viable:** require the user to maintain a folder of `style_examples/` and ingest those with a metadata tag `is_self_authored=true`. Filter on that tag when extracting style.
  - **(b) Better, still simple:** add a `Document.metadata['author']` field, let the loader populate it from a frontmatter `author:` key if present (markdown files), and filter on `author == config.user_name` (add `user_name` to `config.py`).
  - Pick (b) — it generalises better and the demo dataset can be patched to include the frontmatter cheaply.
- The prompt hardcodes the signature `"sign it as 'Maddy'"`. Pull from `config.user_name` instead.
- The output for `--target email` should structure as `Subject: ...\n\n<body>` so an operator can paste straight into a mail client. The current prompt asks for "Subject line" but the LLM is inconsistent — add a deterministic post-processor that extracts the subject and reformats.
- `--target tweet` should enforce ≤ 280 chars in the post-processor (re-prompt with a "shorter" instruction up to 2 retries before truncating).
- `--target linkedin` should aim for ≤ 1300 chars and a single-line opening hook.
- The current code wraps the draft in `Panel(draft, title="Generated Draft", border_style="green")` — keep that, it's nice.

# End-to-end demo flow that must work

These commands, run in order from a clean shell, must produce sensible output without any manual fix-ups:

```bash
# 1. Reset to a known good state
python scripts/reset_demo_env.py
rm -f upii.db upii.log
rm -rf upii_vectors

# 2. Start watching a temp folder (foreground; new terminal tab)
mkdir -p /tmp/upii_demo_inbox
upii watch /tmp/upii_demo_inbox

# 3. In the original terminal: drop a file into the watched folder
cat > /tmp/upii_demo_inbox/iceye_followup.md <<EOF
# ICEYE follow-up
Sarah confirmed the v3/tasking endpoint is ready.
First test pass scheduled for Nov 1 over Napa Valley.
Action: spin up S3 bucket for SAR drops by EOW.
EOF

# 4. Within ~3 seconds, the inbox should list the event with a preview
upii inbox

# 5. Approve it
upii inbox --approve <id_prefix_from_step_4>

# 6. The promoted content is now in LTM and queryable
upii ask "What did Sarah confirm about the v3 tasking endpoint?"
# Expect: an answer mentioning Sarah, v3/tasking, Napa Valley test pass

# 7. Draft a follow-up email in my voice, grounded in that context
upii write "Confirming Nov 1 SAR test pass with Sarah" --target email
# Expect: a Panel-wrapped draft with Subject + body, signed with config.user_name,
# referencing the v3/tasking endpoint and Napa Valley test pass

# 8. Reject path: drop another file, then reject it
cat > /tmp/upii_demo_inbox/junk.md <<EOF
This is junk that should not enter LTM.
EOF
sleep 4
upii inbox
upii inbox --reject <id_prefix>
# Expect: event marked rejected, audit log entry, NOT queryable via ask
```

If any of these 8 steps produces a stack trace, hangs, or returns the wrong content, the feature is not done. Re-run from step 1 between iterations — the demo state should be reset-able from a single script.

# Acceptance criteria summary

For each feature, the demo must pass and the following must hold:

**watch:**
- `upii watch /tmp/upii_demo_inbox` runs without ImportError.
- New `.md`/`.txt`/`.pdf` files in the watched path appear in `upii inbox` within 5 seconds.
- Modified files appear as `modified` events; deleted files as `deleted` events.
- `Ctrl+C` exits cleanly (no Python traceback, watcher thread joined).
- The watched path persists in `features.yaml` so a second `upii watch` invocation does not need to re-add it.

**inbox:**
- `upii inbox` lists pending events with id-prefix, type, file path, and a 120-char content preview.
- `upii inbox --approve <id>` promotes the staged content (NOT a fresh disk read) to LTM, runs task extraction, marks both event and staging_doc as `approved`, writes an audit-log entry, and is idempotent (re-approving the same id is a no-op with a clear message).
- `upii inbox --reject <id>` marks both event and staging_doc as `rejected`, writes an audit-log entry, leaves rows in the DB.
- `upii inbox --all` lists pending + approved + rejected, with a status column.
- Approving a `deleted` event prints a clear message and does not crash.

**write:**
- `upii write "<topic>" --target email` returns a Panel-wrapped draft with `Subject: ...` on the first line, body below, signed with `config.user_name`.
- Style context comes from documents with `author == config.user_name` metadata (loaded from markdown frontmatter where present).
- `--target tweet` enforces ≤ 280 chars.
- `--target linkedin` aims for ≤ 1300 chars.
- If no style examples exist, draft still works but logs a warning ("no style examples found; using neutral tone").

**Cross-cutting:**
- `pytest tests/ -q` passes at least at the baseline you captured at start. Add new tests for the new behaviour (at minimum: `test_inbox_approve_uses_staged_content`, `test_inbox_reject`, `test_watch_registers_with_filesystem_source`).
- No new top-level dependencies added without telling me. The existing `requirements.txt` should suffice (`watchdog` is acceptable to add if you replace the polling watcher — flag it explicitly in your final report).

# Out of scope — do not touch

- **Do not refactor `LocalLLM`.** It works. The Gemini + Ollama + mock fallback is deliberate.
- **Do not change the embedding model.** `all-MiniLM-L6-v2` is the 22M-param choice cited in the pitch deck — switching it invalidates the "CPU-only, ₹40K laptop" claim.
- **Do not change `LocalVectorStore` (LanceDB).** Same reason.
- **Do not add cloud sync, telemetry, or phone-home.** UPII's whole pitch is that data never leaves the device.
- **Do not delete `staging.db` migrations** — the schema is small but evolving; if you must change it, ALTER, do not DROP.
- **Do not edit the existing decks (`.pptx`)** or the pitch/demo markdowns at the repo root (`Pitch_Script_GrandFinale.md`, `Demo_Recording_Script.md`, `GRAND_FINALE_PITCH_PREP.md`). I edit those.

# Build order (suggested)

1. Fix the `watch` ImportError and wire `features.add_watch_path` to the `FileSystemSource` registry instance. Verify step 2-4 of the demo flow work.
2. Fix `inbox --approve` (use staged content, remove double-insert, add task extraction, handle deleted events). Verify steps 5-6.
3. Implement `inbox --reject` and `inbox --all`. Verify step 8.
4. Add preview column to `inbox` listing.
5. Add `author` frontmatter parsing in `LocalLoader`, `user_name` in `config`, and the style-filtering in `write`. Verify step 7.
6. Add the three new tests.
7. Run the full demo flow end-to-end from scratch. Then run `pytest -q` and confirm no regressions.

# Final report (what to tell me when done)

When you finish, post a single message containing:

- A one-line summary per feature ("watch: fixed ImportError, wired to FileSystemSource, demo step 2-4 verified").
- The before/after `pytest -q` counts.
- Any new files created (paths only).
- Any deviation from this prompt and why.
- The exact demo flow commands that you verified, copy-pasteable.
- Any concern about the demo holding up under jury scrutiny — be honest. If the LLM-generated `write` output is shaky on certain topics, say so and recommend a topic that produces a reliable demo answer.

Do not summarise what you did beyond that. The diff is the source of truth.

---

# Notes for you (Maddy) — not part of the prompt

A few things worth flagging before you hand this to Claude Code:

**On the LLM dependency for `write`.** The voice-synthesis feature is the weakest of the three because it depends on (a) the local LLM behaving consistently and (b) having actual self-authored content tagged correctly. For the live demo on Slide 6, you might want to fall back to a pre-curated `write` prompt that you know produces a clean answer on your rehearsal laptop, rather than improvising on stage. The prompt above tells Claude Code to be honest about which topics are reliable — pay attention to that part of its report.

**On the `watchdog` library.** The current polling watcher is fine but uses 2-second polling. If Claude Code suggests replacing it with `watchdog` (native FS events), that's a strict improvement and worth a small added dependency. The prompt allows it but asks Claude Code to flag it.

**On test coverage.** The repo has 18 test files per Slide 14's claim, but several (`test_ambient.py`, `test_watcher_advanced.py`) may have been written against the broken stubs. Tell Claude Code to fix the tests if they fail because the stub was wrong, not because the new code is wrong — they should articulate the distinction in the final report.

**On scope creep.** Three features in one prompt is on the upper end of what Claude Code can do reliably in a single session. If it gets stuck, split: run the prompt three times, once per feature, in the order listed (watch → inbox → write), and only run the next when the previous demo step is green. The end-to-end flow at the bottom of the prompt is the integration gate.
