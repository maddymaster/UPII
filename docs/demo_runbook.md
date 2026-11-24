# Demo runbook: `upii ask` and the desktop overlay

A step-by-step run of UPII on real files through the normal pipeline, from source, on macOS.
Nothing here is scripted. Every answer comes from the files you ingest and the local model,
so wording varies between runs. The runbook gives no benchmark numbers; do not quote any in
the demo.

The demo shows five things:
1. ingest real files;
2. ask, and get an answer with its sources;
3. a question that is not in memory, so UPII says so;
4. Wi-Fi off, then ask again;
5. the same memory in the overlay.

**Memory folder rule.** `upii` reads and writes the memory (`upii.db`, `upii_vectors/`,
`staging.db`) in the **current folder**. Before every command, `cd` into the memory folder
(`~/upii-demo` below). In any other folder, `upii ask` finds no memory.

## 0. One-time setup (the day before)

**Demo code: freeze commit `3db9efc`** (`3db9efc18f4b8f588b4cc1b84b52b0ad2b534c7b`, main on
2026-11-24 with T-060, T-061, T-064 and T-065). Run the demo and both dry runs from this commit, not
from main: later merges are not tested for the demo. `git log -1 --format=%h` in `~/Developer/UPII`
must print `3db9efc`.

Needs internet. Run from a terminal you will also use in the demo. That terminal app must get the
macOS Accessibility permission (step 6).

```bash
# Ollama with the demo answer model (about 17 GB; needs about 18 GB of free memory when loaded)
ollama pull qwen3.8:27b

# A fresh venv from source. UPII needs Python 3.10-3.12: call python3.12 explicitly
# (the default python3 on this Mac is newer and is not supported).
cd ~/Developer/UPII
git fetch origin
git checkout 3db9efc18f4b8f588b4cc1b84b52b0ad2b534c7b   # the demo freeze commit
python3.12 -m venv ~/upii-demo-venv
source ~/upii-demo-venv/bin/activate
pip install -e ".[overlay]"
```

Prepare the memory folder. The first ingest downloads the embedding model once (about 90 MB);
after that everything runs offline.

```bash
rm -rf ~/upii-demo && mkdir ~/upii-demo
cd ~/upii-demo
echo "llm_model: qwen3.8:27b" > .upii_config.yaml
upii ingest ~/Developer/UPII/demo_dataset
upii doctor
```

`.upii_config.yaml` in the memory folder sets the answer model for this folder only. The default
model (llama3.2) is unchanged everywhere else.

`upii doctor` must end with `doctor: PASS`. `model` and `embedding` must be `OK`. If not, follow
the hint printed under the line and run `upii doctor` again.

Then reset the memory, so the demo shows the ingest from an empty folder (the embedding model
stays cached):

```bash
cd ~ && rm -rf ~/upii-demo && mkdir ~/upii-demo
echo "llm_model: qwen3.8:27b" > ~/upii-demo/.upii_config.yaml
```

## 1. Before the audience arrives

Keep the answer model loaded for the whole session. By default Ollama unloads a model after 5
idle minutes, and the next answer then takes about 35 seconds while it loads again. Set the
keep-alive, then restart Ollama so it takes effect (the setting lasts until you log out or restart
the Mac, so do this on the day):

```bash
launchctl setenv OLLAMA_KEEP_ALIVE 3h
```

Quit Ollama from its menu-bar icon (Quit Ollama), then open it again from Applications.

After Ollama restarts, open its settings and check that the **Claude** toggle under **Apps** is off.
Restarting Ollama once switched the Claude desktop app to Ollama's gateway; with the toggle off,
the Claude app keeps its own settings. This step does not affect UPII.

```bash
source ~/upii-demo-venv/bin/activate
cd ~/upii-demo
cat .upii_config.yaml  # llm_model: qwen3.8:27b
upii doctor            # doctor: PASS
ollama list            # qwen3.8:27b is listed
```

Warm up the model: the first answer after Ollama starts takes about 35 seconds while the model
loads. Do it now, not in front of the audience:

```bash
upii ask 'What is the daily meal allowance when travelling?'
ollama ps              # qwen3.8:27b, UNTIL "3 hours from now" (not "5 minutes from now")
```

If `ollama ps` says "5 minutes from now", the keep-alive is not set: repeat the `launchctl` line and
restart Ollama.

Close other apps that use a lot of memory. Wi-Fi is on.

## 2. Ingest

```bash
cd ~/upii-demo
upii ingest ~/Developer/UPII/demo_dataset
```

It reports `Processed 42`: meeting notes, project briefs, policies, finance, support and
engineering notes for one invented company. Say: these are ordinary files on this laptop. They are
chunked, embedded and stored here. Nothing is uploaded.

## 3. Ask, with sources

```bash
cd ~/upii-demo
upii ask "Who fixed the memory leak?"
```

Look for:
- an answer that cites `[1]`;
- `Answered by: qwen3.8:27b (ollama, local)`;
- under **Sources used**, the file (`team_sync.md`) and an excerpt of the passage.

Only cited sources are listed. A second question, where two documents disagree:

```bash
upii ask 'What is the current monthly cloud hosting budget?'
```

Look for: $11,500, citing `finance/hosting_budget_revised_2025-10.md`. An older budget
(`finance/hosting_budget_2025-08.md`) says $9,000; the answer takes the revision.

The demo questions. Each one answered correctly with a citation 5 times out of 5 with qwen3.8:27b
on this dataset. Use single quotes in the terminal: in double quotes the shell replaces `$1` in
"$1,000" with nothing.

| # | Question | Answer | Source |
|---|---|---|---|
| 1 | Who fixed the memory leak? | Sarah | `team_sync.md` |
| 2 | What is the current monthly cloud hosting budget? | $11,500 (replaces $9,000) | `finance/hosting_budget_revised_2025-10.md` |
| 3 | Who is the escalation owner for the Marrowbank Clinics account? | Grace Liu | `meetings/2025-09-15_customer_call_marrowbank.md` |
| 4 | When is firmware 2.0 generally available? | 15 December 2025 | `projects/project_ember_status_2025-11.md` and/or `meetings/2025-11-10_engineering_sync.md` |
| 5 | What is the standard price per hub? | $14 per hub per month, annual contract | `meetings/2025-11-17_sales_pipeline_review.md` |
| 6 | Who approves expenses over $1,000? | the Head of Finance (Lena Fischer) | `policies/expense_policy.md` |
| 7 | What was the root cause of the 14 October outage? | the TLS certificate on the device gateway expired | `engineering/postmortem_2025-10-14_outage.md` |
| 8 | What was the top complaint in the Q3 customer survey? | pairing new hubs takes too long | `support/customer_survey_q3.md` |
| 9 | How long does a Kestrin hub keep readings when it is offline? | up to 72 hours | `support/faq_hub_offline.md` (may also cite the Marrowbank call) |
| 10 | When does the Lumenvale Hosting contract end? | 31 March 2026 | `finance/vendor_contracts_summary.md` |

Spares, also 5 out of 5, for when someone wants to ask their own question: offer one of these.

| Question | Answer | Source |
|---|---|---|
| What is the hotel limit per night when travelling? | $180, or $250 in major cities | `policies/travel_policy.md` |
| How long is production access granted for? | 8 hours at a time | `policies/it_access_policy.md` |
| Which Wrenfield version fixed the CSV export bug? | Wrenfield 3.2 | `support/release_notes_wrenfield_3.2.md` (may also cite engineering syncs) |

A question nobody tested may answer without a citation, or not at all: if someone insists on their
own, say so before asking it.

Every `upii ask` takes 10-20 seconds: a few seconds to start (each one is a new process that loads
the machine-learning libraries again), then the model's answer. For several questions in a row, use
the overlay (step 6): it loads the libraries once at start, so only the model's time remains.

## 4. A question that is not in memory

```bash
cd ~/upii-demo
upii ask "What is the capital of Australia?"
```

Look for: **Not found in your memory**, and no sources. Say: the answer is not in these files, so
UPII says so instead of answering from general knowledge or guessing. (Also tested, same result:
"Who won the football match on Sunday?")

## 5. Wi-Fi off, ask again

Turn Wi-Fi off from the menu bar, then:

```bash
cd ~/upii-demo
upii ask "Who fixed the memory leak?"
```

The answer and its source come back as before: the embedding model, the store and the answer
model (Ollama) are all on this Mac. Leave Wi-Fi off for step 6.

## 6. The same memory in the overlay

```bash
cd ~/upii-demo
upii overlay
```

- First time only: macOS asks to allow the terminal app under System Settings > Privacy &
  Security > Accessibility (for the Cmd+Shift+K hotkey). Allow it, then run `upii overlay`
  again.
- The window opens on top. Ask "Who fixed the memory leak?": same memory, same source
  (`demo_dataset/team_sync.md`). Under the answer: "Smritium · answered on this device" and
  "Model: qwen3.8:27b, running locally. Nothing left this Mac."
- Ask "What is the capital of Australia?": not found, no sources.
- Escape hides the window; Cmd+Shift+K shows it again (and hides it).
- To quit, press Ctrl+C in the terminal.

The overlay loads the embedding model when it starts (allow 15-20 seconds). Start it before
you need it.

Turn Wi-Fi back on.

## If something goes wrong

| Symptom | Check |
|---|---|
| `Not found` for a question that should answer | You are not in `~/upii-demo` (`pwd`), or the ingest did not run there. |
| `Answered by: mock` | Ollama is not running: open the Ollama app, then `ollama list`. |
| `Answered by: llama3.2` | `.upii_config.yaml` is missing from `~/upii-demo` (the reset deleted it): recreate it (step 0). |
| An answer takes about 35 seconds | The model was unloaded: check `ollama ps` and the keep-alive (step 1). |
| `**` around words in an answer | Wrong checkout: it must be `3db9efc` (step 0). |
| `upii overlay` says the extra is missing | `pip install -e ".[overlay]"` in the demo venv. |
| Hotkey does nothing | Accessibility permission for the terminal app (step 6). |
| Escape does nothing | Wrong checkout: `git -C ~/Developer/UPII log -1 --format=%h` must print `3db9efc` (step 0). |
| `upii doctor` shows FAIL | Follow the hint under that line. |
| **Closest passage (not cited by the model)** instead of **Sources used** | The model answered without citing. Ask the same question again. |
| Overlay says "answered via ... (remote)" | The answer model is not on this Mac (`llm_provider: remote`, or `OLLAMA_HOST` points elsewhere). Unset it and restart the overlay. |

## Dry-run log

Acceptance for T-044: two full runs, from a fresh venv, each with `upii doctor` passing.

| Date | Fresh venv | doctor PASS | Steps 2-6 | Notes |
|---|---|---|---|---|
| 2026-11-24 | yes | yes | all passed | Commit 3db9efc, qwen3.8:27b. All ten questions gave the expected answer with a source. Overlay showed the Smritium line, hid on Escape, came back on Cmd+Shift+K. Warm-up as written (`ollama ps`: "3 hours from now"). |
| 2026-11-24 | yes | yes | all passed | Same as run 1. Screen-recorded. |
