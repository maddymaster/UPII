#!/usr/bin/env python3
"""Measure where the time goes in one ``upii ask``.

Two measurements, both against the real stack (real embedding model, real store, the
configured answer model):

1. ``cli``: wall time of ``upii ask QUESTION`` (``python -m upii.cli``, this interpreter) run as a new process, ``--runs`` times.
   This is what a user waits for at the terminal.
2. ``phases``: one fresh process that times each step of the same question in turn:
   import torch, import the search stack (sentence-transformers, transformers, lancedb),
   load the embedding model, first encode, search, import the answer model client,
   answer. Then ``--warm`` more questions in that same process, which is what a process
   that stays running (the overlay) pays per question.

Run it from the memory folder (the folder holding ``upii.db``), after ``upii ingest``.
Numbers depend on the machine and on the file cache: the first run after a reboot is
slower. The report prints the machine so the numbers are read in context. This script
only measures; it changes nothing.

Example
-------
    cd ~/upii-demo
    python ~/Developer/UPII/scripts/bench/ask_startup.py --runs 5
"""

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import time

QUESTION = "Who fixed the memory leak?"

PHASES_CODE = r"""
import json, sys, time
q, warm = sys.argv[1], int(sys.argv[2])
out = []
t = time.perf_counter()
def step(name):
    global t
    now = time.perf_counter(); out.append([name, now - t]); t = now
import torch; step("import torch")
from upii.analysis.search import SearchEngine; step("import search stack")
from upii.analysis.embeddings import Embedder
Embedder.get_instance(); step("load embedding model")
Embedder().embed([q]); step("first encode")
from upii.core.config import config
se = SearchEngine(); r = se.search(q, limit=config.rag_max_chunks); step("search")
from upii.analysis.llm import LocalLLM; llm = LocalLLM(); step("import answer client")
llm.answer(q, r); step("answer")
w = []
for _ in range(warm):
    s = time.perf_counter(); llm.answer(q, se.search(q, limit=config.rag_max_chunks)); w.append(time.perf_counter() - s)
print("PHASES_JSON " + json.dumps({"phases": out, "warm": w}))
"""


def upii_cmd():
    """This interpreter's ``upii``: another ``upii`` on PATH could be a different install."""
    return [sys.executable, "-m", "upii.cli"]


def time_cli(question, runs):
    times = []
    for _ in range(runs):
        start = time.perf_counter()
        r = subprocess.run(upii_cmd() + ["ask", question], capture_output=True, text=True)
        times.append(time.perf_counter() - start)
        if r.returncode != 0:
            sys.exit("upii ask failed (exit %d):\n%s" % (r.returncode, r.stderr[-2000:]))
    return times


def time_phases(question, warm):
    r = subprocess.run([sys.executable, "-c", PHASES_CODE, question, str(warm)],
                       capture_output=True, text=True)
    for line in r.stdout.splitlines():
        if line.startswith("PHASES_JSON "):
            return json.loads(line[len("PHASES_JSON "):])
    sys.exit("phase run failed (exit %d):\n%s" % (r.returncode, r.stderr[-2000:]))


def summary(times):
    """median / min / max in seconds."""
    return {"median": statistics.median(times), "min": min(times), "max": max(times), "n": len(times)}


def report(cli, phases):
    lines = ["machine: %s %s, Python %s" % (platform.system(), platform.machine(),
                                            platform.python_version()),
             "folder: %s" % os.getcwd(), ""]
    if cli:
        s = summary(cli)
        lines.append("upii ask, new process, %d runs: median %.2f s (min %.2f, max %.2f)"
                     % (s["n"], s["median"], s["min"], s["max"]))
        lines.append("  each run (s): " + ", ".join("%.2f" % t for t in cli))
        lines.append("")
    if phases:
        lines.append("one process, step by step:")
        for name, secs in phases["phases"]:
            lines.append("  %8.0f ms  %s" % (secs * 1000, name))
        if phases["warm"]:
            s = summary(phases["warm"])
            lines.append("same process, %d more questions (search + answer): median %.0f ms, max %.0f ms"
                         % (s["n"], s["median"] * 1000, s["max"] * 1000))
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--question", default=QUESTION)
    p.add_argument("--runs", type=int, default=5, help="new-process `upii ask` runs (0 to skip)")
    p.add_argument("--warm", type=int, default=5, help="extra questions in the warm process")
    p.add_argument("--no-phases", action="store_true", help="skip the step-by-step run")
    a = p.parse_args(argv)
    if not os.path.exists("upii.db"):
        sys.exit("No upii.db here. cd into the memory folder (after `upii ingest`) and run again.")
    cli = time_cli(a.question, a.runs) if a.runs else []
    phases = None if a.no_phases else time_phases(a.question, a.warm)
    print(report(cli, phases))


if __name__ == "__main__":
    main()
