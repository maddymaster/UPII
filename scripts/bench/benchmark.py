#!/usr/bin/env python3
"""Phase 1 benchmark: ingestion throughput and retrieval latency.

Targets
-------
    ingestion       >= 500 docs/min
    retrieval p50   <  300 ms   (on a ~100k-chunk corpus)

Both are measured against the REAL stack: the production ingest pipeline with the
real SentenceTransformer embedder, and the same ``SearchEngine().search()`` call
that ``upii ask`` / ``upii search`` use (semantic + temporal + relational fusion).

A metric below target is reported as MISS but does NOT fail the run — the exit
code stays 0. A baseline measured on hardware other than the target machine is
information, not an error; the report records the machine so the number is always
read in context.

One-time costs are excluded from the throughput number and stated in the report:
the embedding model is loaded (and a warm-up query is run) before any timer starts,
because model load is a startup cost, not a per-document one.

Examples
--------
    python scripts/bench/benchmark.py --corpus /tmp/corpus
    python scripts/bench/benchmark.py --corpus /tmp/corpus --workdir /tmp/store --keep
"""

import argparse
import os
import platform
import statistics
import subprocess
import sys
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from upii.core import config as _config_mod

TARGET_DOCS_PER_MIN = 500.0
TARGET_P50_MS = 300.0


# --- machine info -------------------------------------------------------------

def _sh(cmd) -> str:
    try:
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return ""


def machine_info() -> dict:
    """Best-effort CPU/RAM description, so a number is never read without its machine."""
    cpu = ""
    ram_gb = None
    if platform.system() == "Darwin":
        cpu = _sh(["sysctl", "-n", "machdep.cpu.brand_string"])
        mem = _sh(["sysctl", "-n", "hw.memsize"])
        if mem.isdigit():
            ram_gb = int(mem) / 1024 ** 3
        model = _sh(["sysctl", "-n", "hw.model"])
        if model:
            cpu = f"{cpu} ({model})" if cpu else model
    elif platform.system() == "Linux":
        try:
            for line in Path("/proc/cpuinfo").read_text().splitlines():
                if line.startswith("model name"):
                    cpu = line.split(":", 1)[1].strip()
                    break
            for line in Path("/proc/meminfo").read_text().splitlines():
                if line.startswith("MemTotal"):
                    ram_gb = int(line.split()[1]) / 1024 ** 2
                    break
        except Exception:
            pass
    if not cpu:
        cpu = platform.processor() or platform.machine()
    if ram_gb is None:
        try:
            import psutil

            ram_gb = psutil.virtual_memory().total / 1024 ** 3
        except Exception:
            pass

    os_name = platform.system()
    if os_name == "Darwin":
        os_name = f"macOS {platform.mac_ver()[0]}"
    else:
        os_name = f"{os_name} {platform.release()}"

    return {
        "cpu": cpu,
        "cores": os.cpu_count(),
        "ram_gb": f"{ram_gb:.0f}" if ram_gb else "unknown",
        "os": os_name,
        "arch": platform.machine(),
        "python": platform.python_version(),
        "embedding_model": getattr(_config_mod.config, "embedding_model", "?"),
    }


# --- stores -------------------------------------------------------------------

def build_stores(workdir: str):
    os.makedirs(workdir, exist_ok=True)
    _config_mod.config.db_path = os.path.join(workdir, "upii.db")
    _config_mod.config.vector_store_path = os.path.join(workdir, "vectors")
    from upii.storage.db import DB
    from upii.storage.vector import LocalVectorStore

    db = DB()
    db.init_db()
    return db, LocalVectorStore()


def db_counts(db):
    conn = db.get_connection()
    cur = conn.cursor()
    docs = cur.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    chunks = cur.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    conn.close()
    return docs, chunks


# --- phases -------------------------------------------------------------------

def _rss_mb():
    """Resident memory, if psutil is available (dev extra). None otherwise."""
    try:
        import psutil

        return psutil.Process().memory_info().rss / 1024 ** 2
    except Exception:
        return None


def run_ingest(paths, db, vec, embedder, chunker, progress_every=250, max_seconds=0.0,
               batch_chunks=2000):
    """Ingest with periodic checkpoints and an optional wall-clock budget.

    Checkpoints record the *window* rate (docs/min since the last checkpoint), not
    just the average, because the interesting question is whether throughput decays
    as the index grows — an average hides that.

    ``max_seconds`` stops ingestion early and reports what was achieved. A run that
    is killed teaches nothing; a truncated run that still writes an honest report
    teaches us where the wall is.
    """
    from upii.ingestion.loader import LocalLoader
    from upii.ingestion.pipeline import ingest_documents

    loader = LocalLoader()
    state = {"n": 0, "truncated": False}
    checkpoints = []
    t0 = time.perf_counter()
    last_t, last_n = t0, 0

    def docs():
        """Yield documents, stopping at the wall-clock budget."""
        for p in paths:
            if max_seconds and (time.perf_counter() - t0) > max_seconds:
                state["truncated"] = True
                print(f"  [budget] stopping at {state['n']:,} docs after "
                      f"{time.perf_counter() - t0:.0f}s", flush=True)
                return
            for d in loader.load(p):
                yield d

    def on_result(_res):
        nonlocal last_t, last_n
        state["n"] += 1
        n_docs = state["n"]
        now = time.perf_counter()
        if progress_every and n_docs % progress_every == 0:
            elapsed = now - t0
            window_s = now - last_t
            win_rate = ((n_docs - last_n) / (window_s / 60.0)) if window_s > 0 else 0.0
            overall = n_docs / (elapsed / 60.0) if elapsed > 0 else 0.0
            rss = _rss_mb()
            checkpoints.append(
                {"docs": n_docs, "elapsed_s": elapsed, "window_docs_min": win_rate,
                 "overall_docs_min": overall, "rss_mb": rss}
            )
            rss_s = f"{rss:,.0f} MB" if rss else "n/a"
            print(
                f"  {n_docs:>6,} docs | {elapsed:6.0f}s | now {win_rate:7,.0f} docs/min"
                f" | avg {overall:7,.0f} | RSS {rss_s}",
                flush=True,
            )
            last_t, last_n = now, n_docs

    # Vector writes are amortised across a batch (see pipeline.ingest_documents) rather
    # than one LanceDB append per document; ingest_documents always flushes before it
    # returns, so the store is complete when this call finishes.
    ingest_documents(docs(), db, vec, embedder, chunker,
                     batch_chunks=batch_chunks, on_result=on_result)

    return state["n"], time.perf_counter() - t0, checkpoints, state["truncated"]


def run_queries(queries, limit, warmup=True):
    from upii.analysis.search import SearchEngine

    # Construct once: `upii search` pays this once per process, so folding it into
    # every query would overstate steady-state retrieval latency.
    engine = SearchEngine()
    if warmup and queries:
        engine.search(queries[0], limit=limit)  # excluded: first call warms caches

    latencies = []
    for q in queries:
        t0 = time.perf_counter()
        engine.search(q, limit=limit)
        latencies.append((time.perf_counter() - t0) * 1000.0)
    return latencies


def pct(values, p):
    if not values:
        return 0.0
    s = sorted(values)
    k = max(0, min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1)))))
    return s[k]


# --- report -------------------------------------------------------------------

def write_report(path, info, args, n_docs, n_chunks, t_ingest, docs_per_min, lat, note,
                 checkpoints=None, truncated=False, requested_docs=None):
    p50 = pct(lat, 50)
    ing_ok = docs_per_min >= TARGET_DOCS_PER_MIN
    ret_ok = p50 < TARGET_P50_MS
    verdict = lambda ok: "✅ PASS" if ok else "⚠️ MISS"
    at_target_scale = n_chunks >= 100_000

    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = [
        "# Phase 1 Benchmark — ingestion throughput & retrieval latency",
        "",
        f"**Run:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Headline",
        "",
        "| Metric | Measured | Target | Result |",
        "|---|---|---|---|",
        f"| Ingestion throughput | **{docs_per_min:,.0f} docs/min** | ≥ 500 docs/min | {verdict(ing_ok)} |",
        f"| Retrieval latency (p50) | **{p50:,.0f} ms** | < 300 ms | {verdict(ret_ok)} |",
        "",
    ]
    if not at_target_scale:
        lines += [
            f"> ⚠️ **Scale caveat — read before citing these numbers.** This run indexed "
            f"**{n_chunks:,} chunks**, below the **100,000-chunk** corpus the retrieval "
            f"target is defined against. Retrieval latency grows with index size, so the "
            f"p50 above is **not** the number the target asks for. Ingestion throughput is "
            f"scale-sensitive too (see the curve below).",
            "",
        ]
    if truncated:
        lines += [
            f"> ⚠️ **Truncated run.** Ingestion stopped at a wall-clock budget "
            f"(`--max-seconds {args.max_seconds:.0f}`) after {n_docs:,} of "
            f"{requested_docs:,} requested documents. The numbers describe what was "
            f"actually ingested.",
            "",
        ]
    if note:
        lines += [f"> **Note:** {note}", ""]
    lines += [
        "## Machine",
        "",
        "| | |",
        "|---|---|",
        f"| CPU | {info['cpu']} |",
        f"| Cores | {info['cores']} |",
        f"| RAM | {info['ram_gb']} GB |",
        f"| OS | {info['os']} ({info['arch']}) |",
        f"| Python | {info['python']} |",
        f"| Embedding model | {info['embedding_model']} |",
        "",
        "## Corpus",
        "",
        f"- Documents: **{n_docs:,}**  |  Chunks: **{n_chunks:,}**  |  Paragraphs/doc: {args.paras}",
        f"- Corpus: `{args.corpus}` (deterministic, seed fixed by `make_corpus.py`)",
        f"- Ingest wall time: {t_ingest:,.1f}s  ({n_chunks / t_ingest:,.0f} chunks/s)",
        "",
    ]

    if checkpoints:
        lines += [
            "## Ingestion throughput vs. index size",
            "",
            "`now` is the rate over the window since the previous checkpoint; `avg` is",
            "cumulative. A falling `now` column means throughput degrades as the index",
            "grows — which is the engineering finding, not the endpoint average.",
            "",
            "| Docs ingested | Elapsed | Rate now (docs/min) | Rate avg (docs/min) | RSS |",
            "|---|---|---|---|---|",
        ]
        for c in checkpoints:
            rss = f"{c['rss_mb']:,.0f} MB" if c.get("rss_mb") else "n/a"
            lines.append(
                f"| {c['docs']:,} | {c['elapsed_s']:,.0f}s | {c['window_docs_min']:,.0f} |"
                f" {c['overall_docs_min']:,.0f} | {rss} |"
            )
        lines.append("")

    lines += [
        "## Retrieval",
        "",
        f"- Queries: **{len(lat)}** (one warm-up query excluded)  |  limit={args.limit}",
        f"- Path: `SearchEngine().search()` — the same call `upii ask` / `upii search` use",
        "",
        "| Percentile | Latency |",
        "|---|---|",
        f"| p50 (median) | **{p50:,.0f} ms** |",
        f"| p95 | {pct(lat, 95):,.0f} ms |",
        f"| p99 | {pct(lat, 99):,.0f} ms |",
        f"| mean | {statistics.mean(lat):,.0f} ms |",
        f"| min / max | {min(lat):,.0f} / {max(lat):,.0f} ms |",
        "",
        "## Method",
        "",
        "- Real stack throughout: the production ingest pipeline with the real",
        f"  SentenceTransformer (`{info['embedding_model']}`), and the live fusion",
        "  retrieval path — no mocks, no fake embedder.",
        "- The embedding model is loaded before any timer starts, so the one-time",
        "  model-load cost is excluded from throughput (it is a startup cost, not a",
        "  per-document one).",
        "- Ingestion writes vectors **once per document** "
        "  (`LocalVectorStore.add` -> `open_table` + `table.add` per doc), so each",
        "  document appends a new LanceDB version. Both the per-append cost and",
        "  resident memory grow with the number of documents already indexed; that is",
        "  the mechanism behind any decay in the curve above.",
        "- Reproduce with one command: `bash scripts/demo/phase1_demo.sh`",
        "",
    ]
    Path(path).write_text("\n".join(lines), encoding="utf-8")


# --- main ---------------------------------------------------------------------

def main() -> int:
    default_out = Path(__file__).resolve().parents[2] / "bench" / "results" / "REPORT.md"
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--corpus", required=True, help="corpus dir from make_corpus.py")
    ap.add_argument("--paras", type=int, default=60, help="paragraphs/doc used to build the corpus (reporting only)")
    ap.add_argument("--limit", type=int, default=10, help="results per query")
    ap.add_argument("--out", default=str(default_out))
    ap.add_argument("--workdir", default=None, help="scratch store (default: temp dir, auto-removed)")
    ap.add_argument("--keep", action="store_true", help="keep the scratch store")
    ap.add_argument("--note", default="", help="free-text note recorded in the report")
    ap.add_argument("--progress-every", type=int, default=250, help="checkpoint interval in docs")
    ap.add_argument("--max-seconds", type=float, default=0.0,
                    help="wall-clock budget for ingestion; stop early and report honestly (0 = no limit)")
    args = ap.parse_args()

    corpus = Path(args.corpus)
    paths = sorted(str(p) for p in corpus.glob("*.md"))
    if not paths:
        print(f"error: no .md documents in {corpus} — run make_corpus.py first", file=sys.stderr)
        return 2
    qfile = corpus / "queries.txt"
    queries = [q for q in qfile.read_text().splitlines() if q.strip()] if qfile.exists() else []
    if not queries:
        print(f"error: no queries in {qfile} — run make_corpus.py first", file=sys.stderr)
        return 2

    tmp = os.path.realpath(args.workdir or tempfile.mkdtemp(prefix="upii_bench_"))
    try:
        info = machine_info()
        print(f"Machine : {info['cpu']} | {info['cores']} cores | {info['ram_gb']} GB | {info['os']}")
        print(f"Corpus  : {len(paths):,} docs from {corpus}")

        from upii.analysis.embeddings import Embedder
        from upii.ingestion.chunker import RecursiveChunker

        db, vec = build_stores(os.path.join(tmp, "store"))
        chunker = RecursiveChunker()
        embedder = Embedder()

        print("Loading the embedding model (excluded from timing)...", flush=True)
        t_load = time.perf_counter()
        embedder.embed(["warm up the model so load time is not charged to ingestion"])
        print(f"  model ready in {time.perf_counter() - t_load:.1f}s")

        print(f"Ingesting {len(paths):,} docs through the real pipeline...", flush=True)
        n_docs, t_ingest, checkpoints, truncated = run_ingest(
            paths, db, vec, embedder, chunker,
            progress_every=args.progress_every, max_seconds=args.max_seconds,
        )
        docs_per_min = n_docs / (t_ingest / 60.0) if t_ingest > 0 else 0.0
        _, n_chunks = db_counts(db)
        print(f"  {n_docs:,} docs / {n_chunks:,} chunks in {t_ingest:,.1f}s -> {docs_per_min:,.0f} docs/min")

        print(f"Replaying {len(queries)} queries...", flush=True)
        lat = run_queries(queries, args.limit)
        p50 = pct(lat, 50)
        print(f"  p50 {p50:,.0f} ms | p95 {pct(lat, 95):,.0f} ms")

        write_report(args.out, info, args, n_docs, n_chunks, t_ingest, docs_per_min, lat,
                     args.note, checkpoints=checkpoints, truncated=truncated,
                     requested_docs=len(paths))

        ing_ok = docs_per_min >= TARGET_DOCS_PER_MIN
        ret_ok = p50 < TARGET_P50_MS
        print("")
        print("=" * 62)
        print(f"  Ingestion     : {docs_per_min:>9,.0f} docs/min   (target >= 500)   {'PASS' if ing_ok else 'MISS'}")
        print(f"  Retrieval p50 : {p50:>9,.0f} ms         (target <  300)   {'PASS' if ret_ok else 'MISS'}")
        print("=" * 62)
        print(f"  Corpus: {n_chunks:,} chunks | Report: {args.out}")
        # Always 0: a miss is a measurement, not a failure.
        return 0
    finally:
        if not args.keep and args.workdir is None:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
