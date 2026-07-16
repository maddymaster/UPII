# UPII — tester walkthrough (v0.6.0)

A ~20-minute smoke test from a fresh `git pull`. It sets up the tool, exercises
the main commands on sample data, runs the automated suite, and reproduces the
two headline numbers. **Please read "What you should see" under each step** — some
things that look wrong are known and expected (they're flagged 👀), and knowing
which is which is exactly what we need from this pass.

You do **not** need an API key, a GPU, or an internet connection beyond one small
model download on first run. Everything runs on your machine.

---

## 0. Prerequisites

- **Python 3.10, 3.11, or 3.12.** Check with `python3 --version`. (3.13 is not yet
  supported — a dependency isn't ready for it.)
- **git**, and ~500 MB free disk (most of it the one-time model download).
- **Ollama is optional.** With it, `upii ask` uses a real local LLM; without it,
  answers fall back to a deterministic mock and the tool still works end-to-end.
  If you want the real thing: install from https://ollama.com, then
  `ollama pull llama3.2`.

---

## 1. Get the code and set up an isolated environment

```bash
git pull                                   # you may already have done this
cd UPII                                     # the repo root (where pyproject.toml is)

python3 -m venv venv
source venv/bin/activate                    # Windows: venv\Scripts\activate

pip install -e ".[dev]"                     # installs UPII + test tooling
```

**What you should see:** `pip` finishes without errors and the `upii` command is
now on your PATH.

**Quick check:**
```bash
upii --help
```
You should get a list of commands (`ingest`, `search`, `ask`, `doctor`, …).

> 💡 First run of any real command downloads the embedding model
> `all-MiniLM-L6-v2` (~90 MB) once. It'll pause the first time, then be instant
> after. If your network is flaky and it hangs, set `export HF_HUB_OFFLINE=1`
> after the first successful download to force it to use the cache.

---

## 2. Health check

```bash
upii doctor
```

**What you should see:** a checklist covering the database, vector store,
embedding model, and disk — all green/OK. This confirms the local stack is wired
up. (It's fine if it reports the store is empty — you haven't ingested anything
yet.)

---

## 3. Ingest a sample corpus

The repo ships a small synthetic corpus at `demo_dataset/`. Build memory from it:

```bash
upii ingest ./demo_dataset --recursive
```

**What you should see:** a line per file (`Processing …`) and a summary like
`Processed N, Skipped 0, Errors 0`.

**Now prove ingestion is idempotent — run the exact same command again:**
```bash
upii ingest ./demo_dataset --recursive
```
**What you should see:** every file reported as `Skipping … (Unchanged)` and
`Processed 0, Skipped N`. Re-ingesting identical content is a no-op — that's the
deterministic-ingestion property, working.

---

## 4. Search and ask

```bash
upii search "budget"
```
**What you should see:** ranked chunks from the sample docs, most relevant first.

```bash
upii ask "What is the Q3 budget?"
```
**What you should see:** a written answer that **cites its sources** by chunk ID.
- If you installed Ollama, it's a real generated answer.
- If not, you'll see a note that it's a simulated/mock response — **this is
  expected**, not a failure. The retrieval underneath is real either way.

---

## 5. Look inside the fusion ranking (the interesting one)

```bash
upii ask "What is the Q3 budget?" --debug
```

**What you should see:** a table with one row per retrieved chunk and columns
**Semantic, Temporal, Relational, Dominant**.

👀 **Expected, NOT a bug:** the **Relational** column is `·` (zero) on every row,
the **Temporal** column is the same value on every row, and **Dominant** is always
`semantic`. In this version, ranking is driven by the semantic (vector) signal
alone. The other two signals are built and visible but not yet fed by data — that
work (extracting a knowledge graph during ingestion) is the next milestone. So if
you see all-zero Relational, that's the current state, working as documented.

> Make your terminal reasonably wide (~100 columns) so the number columns aren't
> squeezed.

> 💡 Add `--no-answer` to see the retrieval + fusion table **without** the LLM
> answer (`upii ask "…" --debug --no-answer`). That output is fully deterministic
> — identical every run — which is what the Phase 3 demo uses.

---

## 6. Knowledge graph

```bash
upii knowledge --graph --out graph.html
```

👀 **Expected, NOT a bug:** on this sample corpus the graph will be **empty** (or
nearly so). Same reason as step 5 — ingestion doesn't populate the entity graph
yet. The command should still run and write `graph.html` without error. (If you
want to see a populated graph, `upii demo seed` seeds some example entities.)

---

## 7. Run the automated test suite

```bash
pytest tests/ -q
```

**What you should see:** **`93 passed`** (one harmless SSL/urllib3 warning on some
setups is fine). If anything **fails**, that's the most valuable thing you can
report — copy the full output.

---

## 8. Reproduce the two headline numbers (optional, ~5–30 min)

These are the performance and quality claims. Both are one command.

**Retrieval quality** (fast, ~1 min):
```bash
bash scripts/demo/phase3_demo.sh
```
**What you should see:** it ends with `Recall@10: 0.958   (target ≥ 0.85)  -> PASS`.
This demo also walks through the fusion table and a control run — it's the clearest
picture of what the retrieval layer does and doesn't do today.

**Ingestion throughput + latency** (slower — builds a ~100k-chunk index):
```bash
# Full run is ~15–30 min. For a 2-minute smoke instead:
DOCS=300 bash scripts/demo/phase1_demo.sh
```
**What you should see:** ingestion docs/min and retrieval p50 ms, each marked
PASS/MISS against its target. On a smaller/older machine the throughput number
will be lower than our reference (627 docs/min on an M5 laptop) — that's fine and
useful; **please report your machine and the number you got.**

---

## What to report back

For each of these, a one-liner is plenty:

1. **Your setup:** OS, `python3 --version`, and whether you installed Ollama.
2. **Steps 1–7:** did each behave as "What you should see" describes? Anything
   that errored, hung, or looked off (that *isn't* one of the 👀 expected items)?
3. **Step 7:** the pytest summary line (e.g. `93 passed`) — and full output if
   anything failed.
4. **Step 8 (if you ran it):** the numbers you got, and your machine.
5. **Anything confusing** — unclear output, a command that did something
   surprising, wording in this guide that didn't match reality.

The 👀-flagged items (empty knowledge graph, all-zero Relational column, mock LLM
answer without Ollama) are **known and expected** — no need to report those unless
they behave differently than described here.

Thank you 🙏 — a fresh pair of eyes on a clean machine catches things we can't.
