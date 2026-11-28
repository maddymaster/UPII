# Memory benchmark method (draft)

Status: **draft for red-team review (T-015)**. Internal. No number produced here leaves the repo
without the G1 benchmark gate.

## What is measured

Long-conversation memory: given a long chat history, can a system answer questions about it?
The pinned harness ingests each conversation into a memory backend, searches it for every question,
has an **answerer** model answer from what the search returned, and has a **judge** model mark each
answer CORRECT or WRONG against the gold answer. The score is the share marked CORRECT.

- **LoCoMo** (main benchmark): 10 conversations, 1,540 questions in categories 1–4 (single-hop,
  multi-hop, temporal, open-domain). Category 5 (adversarial, 446 questions) is excluded, as in the
  harness and the Mem0 paper.
- **LongMemEval-S**: wired up and smoke-tested only; no runs yet.

## Pinned inputs (`HARNESS.lock`)

| Input | Pin |
|---|---|
| Harness | [mem0ai/memory-benchmarks](https://github.com/mem0ai/memory-benchmarks) `4b61c5d31b9c668a12b4f5e78064248a02c82d2b` (2026-05-13), Apache-2.0 |
| LoCoMo | `snap-research/locomo` commit `cbfbc1dba6bc53d00625212a0f22d55ffee7c1fc`, `locomo10.json`, sha256 `79fa87e9…a698ff4` |
| LongMemEval-S | `xiaowu0162/longmemeval-cleaned` revision `98d7416c24c778c2fee6e6f3006e7a073259d48f`, sha256 `d6f21ea9…c3a442` |
| Python packages | `requirements.txt` (separate venv; nothing here is an upii dependency) |
| Models | recorded per run in `REPORT.md` with their Ollama build digests |

`fetch.py` clones the harness at that commit and downloads each dataset from its commit-pinned URL.
It refuses a checksum mismatch, and `run.py` refuses to start on unverified inputs. The harness itself
downloads LoCoMo from the moving `main` branch; we never use that path.

## Licences and where results may appear

**Decision (human, on legal advice, 2026-11-24):** LoCoMo results may be published in the public
UPII repository only, never in Smritium product, sales, investor or website material. Public
material may link to the repository's benchmark but must not quote LoCoMo figures (G5 note in
GATES.md).

| Dataset | Licence | Source and citation | Results quotable outside the repo? |
|---|---|---|---|
| LoCoMo (`locomo10.json`) | CC BY-NC 4.0 (non-commercial) | [snap-research/locomo](https://github.com/snap-research/locomo); Maharana, Lee, Tulyakov, Bansal, Barbieri, Fang, "Evaluating Very Long-Term Conversational Memory of LLM Agents", [arXiv:2402.17753](https://arxiv.org/abs/2402.17753) (2024) | **No**: repo only, per the decision above |
| LongMemEval-S (cleaned) | MIT (dataset card and repository) | [xiaowu0162/LongMemEval](https://github.com/xiaowu0162/LongMemEval); [dataset](https://huggingface.co/datasets/xiaowu0162/longmemeval-cleaned) | Not decided; MIT allows commercial use. Its sessions are partly drawn from other chat datasets: legal to confirm |
| BEAM (not used yet) | CC BY-SA 4.0 | [Mohammadta/BEAM](https://huggingface.co/datasets/Mohammadta/BEAM); Tavakoli et al., "Beyond a Million Tokens: Benchmarking and Enhancing Long-Term Memory in LLMs", [arXiv:2510.27246](https://arxiv.org/abs/2510.27246) (2025) | Not decided; BY-SA allows commercial use with attribution and share-alike: legal to confirm |

Every run report repeats the LoCoMo restriction in its header.

## How the harness is used

`run.py` imports the harness's LoCoMo and LongMemEval modules and calls their own ingest,
question, prompt, judge and metric functions. Only the memory client is ours (`backends/`):

| Backend | What it is |
|---|---|
| `full_history` | Every turn, in conversation order; no retrieval. The baseline. |
| `vector` | Cosine search over raw turns with upii's embedder (all-MiniLM-L6-v2); nothing else. |
| `mem0_oss` | The `mem0ai` open-source library in process: local Ollama for fact extraction, MiniLM embeddings, on-disk Qdrant. Not Mem0's hosted platform. |
| `upii` | One temporary upii store per conversation; each session becomes one document through upii's production ingest path; upii's `SearchEngine.search`. No similarity threshold by default (`--upii-min-similarity` to apply one). |

Where we depart from the harness, and why:

1. **Full history sees everything.** The harness's answer prompt keeps the top 200 memories. A
   LoCoMo conversation has 369–689 turns, so for `full_history` the runner lifts that limit and uses
   one unlimited cutoff. The other backends use the harness's cutoffs (10, 20, 50, 200).
2. **Failed model calls stop the run.** The harness scores an empty answer or a missing judge verdict
   as WRONG, so a dropped connection silently lowers the score (seen in a smoke run). The runner raises
   instead; saved questions are kept and `--resume` continues.
3. **Context guard.** Ollama does not reject a prompt longer than the context it serves: it truncates
   or stalls (seen: a 36k-token prompt on a 32k context stalled the runner for over an hour). Before each
   answer call the runner estimates the prompt (3.0 characters per token, measured 3.04–3.76 here) and
   refuses if it would not fit with 4,096 tokens left for the answer.
4. **Thinking off.** Both local models are reasoning models. Thinking is turned off per request
   (`reasoning_effort: none`), as for a non-reasoning model like gpt-4o-mini; `--thinking` turns it on.
5. **mem0 OSS details.** Its SDK rejects the `timestamp` argument, so the session date is put in front of
   each message and in metadata. Its PostHog telemetry is switched off (`MEM0_TELEMETRY=False`) before
   mem0 is imported, and the embedder loads the cached model offline.
6. Harness ingest checkpoints go to a throwaway folder: backends live in memory, so every run ingests.
7. **Spend guard for paid APIs.** Every call to a paid endpoint is counted from the response's
   `usage` and priced from `PRICES_PER_M` (OpenAI list prices; an unlisted paid model is refused).
   The running estimate is printed after every question and kept in `spend.json` across `--resume`.
   The run stops when the estimate reaches `--max-spend-usd` (default US$15); the stop cannot be
   swallowed by the harness's retry loop. It can overshoot by at most one call (about US$0.004 for a
   full-history LoCoMo question with gpt-4o-mini). Only public benchmark text is sent.

## Models

**Local (default, no cost, nothing leaves our machines):**

| Role | Model | Where | Build digest | Served context |
|---|---|---|---|---|
| Answerer | `qwen3.6:35b-a3b-mtp-q4_K_M` | DGX Spark, Ollama 0.40.16, via SSH tunnel | `096fdbd02fe6…` | 65,536 |
| Judge | `qwen3.8:27b` (nvfp4, MLX) | Mac, Ollama 0.40.16 | `47951e4a6661…` | 32,768 |

The answerer needs the long context: full-history prompts reach about 37k tokens (6 of the 10
conversations exceed 32k). The judge's prompts are short. The answerer and judge are different models,
so neither grades itself. Temperature 0.

**Comparable to published numbers (paid; human-approved per run):** `gpt-4o-mini` as answerer and
judge via `--answerer-url openai --judge-url openai`. This sends the public benchmark text, never our
data, to OpenAI, and costs money: a billing gate for the human. The full-history LoCoMo run cost about US$7.29 at list prices (45.4M input and 0.65M output
tokens); it was approved for the full-history baseline only.

## Published baseline to compare against

Mem0 paper ([arXiv 2504.19413](https://arxiv.org/abs/2504.19413), v1, 28 Apr 2025), Table 2, LoCoMo,
mean of 10 runs:

| Method | Overall J |
|---|---|
| Full-context | 72.90 ± 0.19% (about 26k tokens; total latency p50 9.87 s, p95 17.12 s) |
| Mem0 | 66.88 ± 0.15% |
| Mem0 with graph | 68.44 ± 0.17% |

Limits of that comparison, all to be stated next to any number:

- The paper does not name the answering model for the full-context run or the judge model; Mem0's own
  pipeline used gpt-4o-mini.
- The pinned harness's judge prompt is newer and more lenient than the paper's (Appendix A): partial
  credit if one listed item matches, dates within 14 days, durations within 50%. Our numbers are
  therefore comparable to numbers from this harness, not directly to the paper.
- The paper excludes the adversarial category; its Table 2 caption says "entire" dataset. We score
  categories 1–4.
- One run here versus 10 in the paper.
- Acceptance (T-007): the full-history baseline "within a few points of published baselines" can only
  be judged fairly with the gpt-4o-mini run. The local run checks that the harness works end to end.
- `regrade.py` re-grades a run's saved answers with the Mem0 paper's original judge prompt
  (`prompts/mem0_paper_judge.txt`, copied byte for byte from mem0ai/mem0 at `393a4fd5`, the code
  released with the paper; sha256-pinned), so both scores can be shown side by side without
  re-answering. Only the question, gold answer and saved answer go to the judge. `--estimate` prints
  the cost without calling anything; `--sample N --seed S` writes a fixed random sample of gradings
  as CSV for hand-checking.
- Result of that comparison: full history scores above 90% on this harness, with gpt-4o-mini and
  with the local models, well above the paper's full-context figure and not within a few points. The
  most likely cause is the more lenient judge above; it is unconfirmed until the saved answers are
  re-graded with the paper's judge prompt and a sample of judgements is hand-checked. Until then,
  compare our numbers only with numbers from this harness. T-007 is not accepted yet.
- **Little headroom.** With full history above 90%, accuracy alone cannot show much of a gain for a
  memory backend. Every result must report tokens per answer (context sent to the answerer) beside
  accuracy; a backend's case is the same accuracy for far fewer tokens. The runner records the prompt
  tokens of every answer call as the answering model reports them (`answer_tokens.json`) and gives the
  mean, p50 and p95 in `REPORT.md`.

## Known weaknesses (for the red team)

- Judge leniency, above. A local judge may be more or less lenient than gpt-4o-mini; unmeasured.
- LLM judges can be wrong; no human spot-check yet. Proposal: hand-check 50 random judgements.
- The context guard is an estimate; a run on another tokenizer should re-measure the ratio.
- `mem0_oss` with a 27B local extraction model is very slow (one turn's 8k-token extraction prompt took
  over 5 minutes with thinking on); a full LoCoMo run is not practical this way. Its smoke test uses a
  fake memory; a live call reached Ollama but was not run to completion.
- Reported independent audits of LoCoMo judging (e.g. a Zep audit) are not verified here.

## Rerun

```
python3.12 -m venv bench/memory/.venv
bench/memory/.venv/bin/pip install -e . -r bench/memory/requirements.txt
bench/memory/.venv/bin/python bench/memory/fetch.py
ssh -f -N -L 127.0.0.1:11545:127.0.0.1:11434 spark     # answerer on the Spark
bench/memory/.venv/bin/python bench/memory/run.py --benchmark locomo --backend full_history --name locomo-full-local
bench/memory/.venv/bin/python -m pytest bench/memory/tests -q   # offline tests
```

Each run writes `bench/memory/results/<name>/REPORT.md` and `summary.json`, with the models, build
digests, served contexts, pins, upii commit and package versions. Run output is not committed: it
stays local until the G1 benchmark gate.
