# UPII · 90-Second Demo Recording Script

**Target:** the `demo.mp4` referenced on Slide 6 of `DataFrontier_UPII_GrandFinale_Deck.pptx`.
**Duration:** 90 seconds, six on-screen beats matching the slide timeline:

| Beat | Slide cue | Time on screen |
|---|---|---|
| 1 | `doctor` — Health check, fully offline | 00:00 – 00:08 |
| 2 | `ingest` — Sensitive Ambee docs in | 00:08 – 00:24 |
| 3 | `ask` — ICEYE resolution recalled | 00:24 – 00:42 |
| 4 | `synth` — Cross-doc PACE + roadmap | 00:42 – 01:00 |
| 5 | `honest` — "I don't know" — no hallucination | 01:00 – 01:18 |
| 6 | `audit` — Boost reason: temporal+entity | 01:18 – 01:30 |

The pitch script narrates over a muted playback. Audio in the recording is therefore optional — record without narration; let the on-stage delivery carry it.

All commands below are sourced from `src/upii/cli.py`. The installed binary is `upii` (confirmed via `src/upii.egg-info/entry_points.txt`). If `upii` is not on PATH inside the recording shell, substitute `python -m upii.cli` everywhere — output is identical.

---

## T-15 min · Environment prep

Open a fresh Terminal window (iTerm2 preferred for crisp font rendering). Maximise. Then configure once and leave it:

```bash
# Font: 18 pt minimum so the back row of the auditorium reads cleanly.
#   iTerm2 → Preferences → Profiles → Text → JetBrains Mono / Menlo, 18-20 pt
# Theme: high-contrast light (Solarized Light) or pure dark (Dracula).
#   Avoid translucent panes — they ghost on stage projectors.
# Window: 110 cols × 32 rows. Anything wider wraps awkwardly in 16:9 export.

cd /Users/maddy/Documents/UPII-master
source venv/bin/activate

# Verify the binary resolves
which upii         # expect: …/venv/bin/upii
upii --help        # confirms typer help text loads (also warms imports)
```

If `upii --help` is slow on the first call, that is the lazy-import penalty — re-run once before recording so the cold-start delay does not eat into the take.

---

## T-5 min · Reset state to a clean DB

The repo ships a one-shot reset script that wipes the LTM store and re-ingests `demo_data_v2/` fresh. **Do not run this during the take** — it takes ~30 s and the embedder noise shows in the output. Run it once, before you hit record:

```bash
python scripts/reset_demo_env.py
# Expect: ">>> 1. Cleaning up Databases..."
# Expect: "Found 4 files to ingest" (cto_personal_tasks, ambee_strategic_roadmap,
#         meeting_nasa_pace_integration, meeting_iceye_partnership)
# Expect: ">>> DEMO RESET COMPLETE. <<<"
```

> **Note on the file count.** The deck narration on Slide 6 says *"5 sensitive Ambee docs in"* — but the current `demo_data_v2/` contains 4 markdown files. Either (a) add one more file (e.g. an email or NDA snippet) so the count matches the narration, or (b) change the deck/narration to "4 docs." Pick one before recording; the inconsistency will read as sloppy if a jury member counts.

Then, immediately before recording, **delete the LTM again** so the demo can show `ingest` populating it live:

```bash
rm -f upii.db upii.log
rm -rf upii_vectors
```

Leave the `staging.db` alone — `doctor` will report on whatever exists.

---

## Recording tool — pick one

**Option A — QuickTime Player (simplest, ships with macOS).**
- `Cmd+Shift+5` → "Record Selected Portion" → drag a tight box around the Terminal window only.
- Saves `.mov` to Desktop. Convert to `.mp4` with `ffmpeg -i input.mov -c:v libx264 -preset slow -crf 18 demo.mp4`.
- Pros: zero setup. Cons: no scene control, manual trim afterwards.

**Option B — OBS Studio (recommended).**
- Single "Terminal Window Capture" source. Output: 1920×1080, 30 fps, MP4, H.264, CBR 8000 kbps.
- Pros: scriptable scene size, exact 1080p, no post-recording resize. Cons: 5-minute first-time setup.

**Option C — asciinema → svg-term-cli → ffmpeg (purest terminal aesthetic).**
- `brew install asciinema && npm install -g svg-term-cli`
- `asciinema rec demo.cast`, then `cat demo.cast | svg-term --out demo.svg --window`, then convert.
- Pros: vector-crisp text at any zoom. Cons: no real-time clock, harder to hit the 90-s budget exactly.

Recommendation: **Option B (OBS) for the final cut.** It gives you 1080p out-of-the-box and a clean window crop without post-processing artifacts.

---

## The take — exact commands, expected output, timing

Hit record. Wait one full second on a clean prompt. Then execute the six beats below. **Type each command live** (do not paste) — the visible typing reinforces "this is a real CLI, not a video edit."

### Beat 1 · 00:00 → 00:08 · `doctor`

```bash
upii doctor
```

Expected on screen (colours per `cli.py` `doctor()`):
```
Running UPII Doctor...
ollama         : OK (model: ...)
embedder       : OK
db             : OK
vector_store   : OK
config         : OK
```

If any line reports WARN/FAIL on the rehearsal: fix it before recording. A FAIL line on stage is unrecoverable.

### Beat 2 · 00:08 → 00:24 · `ingest`

```bash
upii ingest demo_data_v2/ --force
```

Expected on screen:
```
Ingesting from demo_data_v2/ (Recursive: False, Force: True)
Processing demo_data_v2/cto_personal_tasks.md
Processing demo_data_v2/ambee_strategic_roadmap.md
Extracted N tasks
Processing demo_data_v2/meeting_nasa_pace_integration.md
Processing demo_data_v2/meeting_iceye_partnership.md
Extracted N tasks

Summary: Processed 4, Skipped 0, Errors 0
```

The magenta "Extracted N tasks" lines are the visible proof of the auto-task-extraction beat — those are what the on-stage narration "audit-logged capture" is pointing to.

### Beat 3 · 00:24 → 00:42 · `ask` (ICEYE recall)

```bash
upii ask "What was the resolution and latency agreed upon with ICEYE?"
```

Expected on screen (per `meeting_iceye_partnership.md` ground truth):
```
Asking: What was the resolution and latency agreed upon with ICEYE?
⠋ Thinking...
Answer:
The agreed latency is < 3 hours from request to image delivery,
with 50 cm resolution GeoTIFF images via ICEYE's v3/tasking API.

Sources used:
[1] <doc_hash>
```

If the answer is too short or omits the 50 cm / 3 h numbers, re-seed and re-record. The numbers are what the on-stage narration is asking the jury to notice.

### Beat 4 · 00:42 → 01:00 · `ask` (cross-doc synthesis)

```bash
upii ask "How does the NASA PACE calibration issue affect our roadmap?"
```

Expected on screen (synthesising `meeting_nasa_pace_integration.md` + `ambee_strategic_roadmap.md`):
```
Asking: How does the NASA PACE calibration issue affect our roadmap?
⠋ Thinking...
Answer:
The 'Blue Band' sensor on PACE needs recalibration, which affects
AOD calculations by ~5%. Engineering will prioritise UV-band ingest
for pollen detection and fall back to Sentinel-5P for blue-light
aerosol data until the Nov 15 NASA patch.

Sources used:
[1] <doc_hash>
[2] <doc_hash>
```

Two source hashes is the visible proof of cross-document synthesis — the deck cue *"Cross-doc PACE + roadmap"* lands on that line.

### Beat 5 · 01:00 → 01:18 · `ask` (honest "I don't know")

```bash
upii ask "What is the launch date for Project Alpha?"
```

Expected on screen:
```
Asking: What is the launch date for Project Alpha?
⠋ Thinking...
Answer:
I don't know. There is no information about a "Project Alpha"
launch date in my context.
```

The absence of a `Sources used:` block is the proof — the `cli.py` `ask()` function explicitly suppresses it when the answer contains "I don't know" (see lines 194-197 of `src/upii/cli.py`). The on-stage narration *"honest — no hallucination"* lands on the missing-sources line.

If the LLM hallucinates a date here, the demo is broken. Re-run; if it persists, lower the LLM temperature in `upii/analysis/llm.py` or switch the local model to something less creative.

### Beat 6 · 01:18 → 01:30 · `ask --debug` (auditable boost reason)

```bash
upii ask "Why are we moving to a Stream-First architecture?" --debug
```

Expected on screen (the `--debug` branch in `cli.py` prints the boost reason per chunk):
```
Asking: Why are we moving to a Stream-First architecture?

Context Ranking Analysis:
1. file://demo_data_v2/ambee_strategic_roadmap.md | Score: 0.87 (vector+entity) | Migrate from current batch processing to `Stream-First` archi...
2. file://demo_data_v2/meeting_nasa_pace_integration.md | Score: 0.71 (temporal) | The new hyperspectral feed is massive. 200 bands vs the 7...
3. file://demo_data_v2/ambee_strategic_roadmap.md | Score: 0.65 (vector) | Hire 2 Sr. Geospatial Engineers...

⠋ Thinking...
Answer:
Ambee is moving to Stream-First (Kafka + Flink) to reduce AQI
latency from 60 minutes to 15 minutes and to handle the 10 TB/day
volume from NASA PACE.
```

**The line the jury must see** is the `(vector+entity)` and `(temporal)` boost-reason tags. End the recording one beat after that line appears. Cut to black at exactly 01:30.

---

## Post-production · trim to 90.0 seconds

The raw take will run 100–120 seconds because of the LLM "Thinking..." spinners on beats 3–6. Compress them, don't delete them — the spinner is the visible proof of local inference. Two options:

**(a) Speed up dead time only.** In iMovie / Final Cut / DaVinci Resolve, select the spinner segments and apply 3× speed. The command typing and the answer text stay at 1× so they remain readable. This is what the deck timeline assumes.

**(b) Hard cut between command and answer.** A jump-cut from the command line to the answer block — fast, but reads as edited and undercuts the "live CLI" credibility. Avoid unless (a) cannot get under 95 s.

Then:

- Add a top-left overlay with the beat label (`doctor`, `ingest`, `ask`, `synth`, `honest`, `audit`) matching the deck timestamps. 24 pt sans-serif, white on black 60% opacity, 4-px corner radius.
- Add a thin bottom progress bar — 1080 px wide, 4 px tall, fills left-to-right over 90 s. The jury subconsciously tracks it.
- No background music. The video is muted for the live narration.
- Export: `1920×1080`, `H.264`, `CRF 18`, `30 fps`, `mp4` container. Target file size 15–25 MB.
- Filename: `demo.mp4`. Place at the repo root so the pitch deck embed resolves.

---

## Embed the file into the deck

PowerPoint on macOS:
1. Open `DataFrontier_UPII_GrandFinale_Deck.pptx` → navigate to Slide 6.
2. Insert → Video → Movie from File → select `demo.mp4`.
3. Resize the video to fill the inner panel of the slide (leave the deck's frame and timestamp strip visible).
4. **Playback tab** → Start: `Automatically` → Volume: `Mute` → Hide While Not Playing: unchecked → Play Full Screen: unchecked.
5. Test: enter Slideshow mode and advance to Slide 6. Video should auto-play from frame 0.

---

## Fallback · live CLI if the video fails on stage

If the video does not auto-play (file path moved, codec rejected by the venue laptop, projector renegotiates resolution mid-pitch), execute the same six commands live. The pitch script already references this fallback — do not apologise, narrate calmly.

Pre-warmed shell history, in order — recall with up-arrow:

```bash
upii doctor
upii ingest demo_data_v2/ --force
upii ask "What was the resolution and latency agreed upon with ICEYE?"
upii ask "How does the NASA PACE calibration issue affect our roadmap?"
upii ask "What is the launch date for Project Alpha?"
upii ask "Why are we moving to a Stream-First architecture?" --debug
```

Before going on stage, run all six in order once so each is in `history` and one `↑↑↑↑↑↑` press recalls them backwards. Also clear the screen with `clear` between rehearsals so the live take looks fresh.

---

## Pre-record QA checklist

- [ ] `upii doctor` returns all-OK on the rehearsal laptop (no WARN, no FAIL).
- [ ] `scripts/reset_demo_env.py` runs clean end-to-end and reports the expected file count.
- [ ] `demo_data_v2/` file count matches the on-stage narration ("4 docs" or "5 docs" — pick one and align both deck and dataset).
- [ ] All six commands return the expected answers on the rehearsal laptop, not just the dev laptop.
- [ ] The `--debug` boost reasons include at least one non-vector tag (`temporal`, `entity`, `vector+entity`). If they are all `vector`, the audit beat falls flat.
- [ ] Terminal font is ≥ 18 pt. Window is 110 cols × 32 rows. Background is solid, not translucent.
- [ ] WiFi is **off** during the take. The whole point of the demo is offline operation — visible network activity in the menu bar undermines it.
- [ ] Final `demo.mp4` is exactly 90.0 s (± 0.5 s), 1080p, H.264, ≤ 25 MB.
- [ ] Video plays from the pitch laptop (not just the recording laptop) — copy the deck to the venue machine and re-test before stage call.

---

## One-line summary for your future self

> Reset the env, kill the WiFi, hit record, type the six commands in order, trim the spinners, label each beat to match the deck timestamps, mute the audio, embed into Slide 6 with auto-play. Total elapsed: about 90 minutes including post.
