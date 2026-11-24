import typer
import uuid
import logging
import os
import sys
from typing import Optional
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from upii.core.config import config
from upii.core.types import Document, RankedChunk

logger = logging.getLogger("upii.cli")

app = typer.Typer()
console = Console()

# Local MCP server subcommands (`upii mcp serve|enable|disable|status`).
from upii.mcp.cli import mcp_app
app.add_typer(mcp_app, name="mcp")


def _source_paths(results) -> dict:
    """doc_hash -> document path as stored at ingest, for display. Read-only: never
    creates a store (an empty folder stays empty); unknown hashes are left out."""
    paths = {}
    if not os.path.exists(config.db_path):
        return paths
    try:
        from upii.storage.db import DB
        db = DB()
        for h in {r.doc_hash for r in results}:
            doc = db.get_document_by_id(h)
            if doc and doc.get("source_path"):
                paths[h] = doc["source_path"]
    except Exception:
        pass
    return paths


def _display_path(path: str) -> str:
    """Relative to the current folder when inside it, else with ~ for the home folder."""
    try:
        rel = os.path.relpath(path)
        if not rel.startswith(".."):
            return rel
    except ValueError:  # another drive on Windows
        pass
    home = os.path.expanduser("~")
    return "~" + path[len(home):] if path.startswith(home + os.sep) else path


def _source_label(r, paths: dict) -> str:
    return _display_path(paths[r.doc_hash]) if r.doc_hash in paths else r.doc_hash


UNCITED_LABEL = "Closest passage (not cited by the model)"


def display_answer(text) -> str:
    """Answer text as shown to a person: Markdown bold markers removed ("**x**" -> "x").

    Some models bold key facts. The terminal and the overlay show plain text, so the
    asterisks would appear literally. Citations such as [1] are kept; the model's raw
    answer (HTTP /ask, MCP) is not changed.
    """
    return (text or "").replace("**", "")


def _excerpt(text, width: int = 240) -> str:
    flat = " ".join((text or "").split())
    return flat if len(flat) <= width else flat[: width - 1].rstrip() + "…"


def _print_fusion_debug(results, weights: Optional[dict]) -> None:
    """Render the per-signal fusion breakdown for `upii ask --debug`.

    Shows, for each retrieved chunk, the fused score and how much each signal
    (semantic / temporal / relational) contributed to it, so it's obvious *why* a
    chunk ranked where it did.
    """
    from upii.analysis.rehydration import SIGNALS

    w = config.fusion_weights()
    if weights:
        w.update({k: v for k, v in weights.items() if v is not None})

    console.print("\n[bold cyan]Fusion Ranking Analysis[/bold cyan]")
    console.print(
        "[dim]weights: " + ", ".join(f"{s}={w[s]:g}" for s in SIGNALS) + "[/dim]"
    )

    # The signal columns carry the point of this view, so pin them no_wrap and let
    # the free-text Chunk column give up width instead (Rich otherwise starves the
    # numeric columns to ellipses to fit a long, no_wrap chunk).
    table = Table(show_lines=False)
    table.add_column("#", style="dim", justify="right", no_wrap=True)
    table.add_column("Fused", style="bold", justify="right", no_wrap=True)
    for s in SIGNALS:
        table.add_column(s.capitalize(), justify="right", no_wrap=True)
    table.add_column("Dominant", style="green", no_wrap=True)
    table.add_column("Chunk", style="italic", overflow="ellipsis", max_width=34)

    for i, r in enumerate(results):
        if not isinstance(r, RankedChunk):
            table.add_row(str(i + 1), "N/A", "-", "-", "-", "-", (r.text or "")[:50])
            continue
        cells = [str(i + 1), f"{r.score:.3f}"]
        for s in SIGNALS:
            sig = r.signals.get(s, 0.0)
            contrib = r.contributions.get(s, 0.0)
            # "signal->contribution": raw normalised score and its weighted share.
            cells.append(f"{sig:.2f}->{contrib:.2f}" if sig else "·")
        cells.append(r.source_signal)
        cells.append(" ".join((r.text or "").split())[:50])
        table.add_row(*cells)

    console.print(table)

@app.callback()
def main(debug: bool = typer.Option(False, "--debug", help="Enable debug logging")):
    """
    UPII: Local-first personal memory substrate.
    """
    from upii.core.logger import setup_logging
    setup_logging(debug)
    if debug:
         logger.info("Debug mode enabled")

@app.command()
def doctor():
    """Run system health checks."""
    from upii.analysis.diagnostics import Doctor, remediation

    console.print("[bold]Running UPII Doctor...[/bold]")
    doc = Doctor()
    report = doc.check_all()

    fail_count = 0

    for check, result in report.items():
        color = "green"
        if result.startswith("FAIL"):
            color = "red"
            fail_count += 1
        elif result.startswith("WARN"):
            color = "yellow"
        elif result.startswith("READY"):
            color = "cyan"

        console.print(f"[{color}]{check.ljust(15)}: {result}[/{color}]")
        hint = remediation(check, result)
        if hint and result.startswith(("WARN", "FAIL")):
            console.print(f"  [dim]-> {hint}[/dim]")

    if fail_count > 0:
        console.print(f"\n[bold red]doctor: FAIL ({fail_count} checks)[/bold red]")
        raise typer.Exit(1)
    else:
        console.print("\n[bold green]doctor: PASS[/bold green]")





OVERLAY_MODULES = {"webview": "pywebview", "pynput": "pynput"}


@app.command()
def overlay(
    debug: bool = typer.Option(False, "--debug", help="Turn on the web inspector (development only)."),
):
    """Open the desktop overlay: ask your memory from any app (needs: pip install "upii\\[overlay]")."""
    import importlib.util

    missing = [pkg for mod, pkg in OVERLAY_MODULES.items() if importlib.util.find_spec(mod) is None]
    if missing:
        console.print(f"[red]The overlay needs the optional extra (missing: {', '.join(missing)}):[/red] "
                      'pip install "upii\\[overlay]"   (from source: pip install -e ".\\[overlay]")')
        raise typer.Exit(code=1)
    console.print(f"Memory folder: {os.getcwd()}")
    if sys.platform == "darwin":
        console.print("[dim]macOS: the Cmd+Shift+K hotkey needs this terminal app allowed in System Settings "
                      "> Privacy & Security > Accessibility.[/dim]")
    from upii.overlay.daemon import run_overlay
    run_overlay(debug=debug)


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", "--host", help="Interface to bind (default: localhost only)"),
    port: int = typer.Option(8765, "--port", help="Port to listen on"),
    data_dir: Optional[str] = typer.Option(
        None, "--data-dir",
        help="Memory folder (upii.db, vectors, staging.db, .upii_config.yaml). Default: current folder",
    ),
):
    """Run the local HTTP API (needs: pip install "upii\\[api]")."""
    try:
        import uvicorn
        from upii.api.server import LOOPBACK_HOSTS, create_app, use_data_dir
    except ImportError:
        console.print('[red]The HTTP API needs the optional extra:[/red] pip install "upii\\[api]"')
        raise typer.Exit(code=1)

    root = use_data_dir(data_dir or os.getcwd())

    extra_hosts = []
    if host not in LOOPBACK_HOSTS:
        if host not in ("0.0.0.0", "::"):
            extra_hosts.append(host)
        else:
            console.print("[yellow]Bound to all interfaces: list the hostnames clients will use in "
                          "UPII_ALLOWED_HOSTS, or their requests are rejected.[/yellow]")
        if not os.environ.get("UPII_API_KEY"):
            console.print(f"[bold yellow]Warning:[/bold yellow] serving on {host} without UPII_API_KEY. "
                          "Anyone who can reach this port can read your memory.")

    console.print(f"[bold green]UPII API[/bold green] on http://{host}:{port}  "
                  f"(API key: {'on' if os.environ.get('UPII_API_KEY') else 'off'}, "
                  f"answer model: local by default, configured provider '{config.llm_provider}')")
    console.print(f"Memory folder: {root}")
    with console.status("Loading embedding model..."):
        # Load once up front: concurrent first requests would otherwise race to load it.
        from upii.analysis.embeddings import Embedder
        Embedder.get_instance()
    uvicorn.run(create_app(allowed_hosts=extra_hosts), host=host, port=port, log_level="info")


@app.command()
def ingest(path: str, recursive: bool = False, force: bool = typer.Option(False, "--force", "-f", help="Force re-ingestion of files")):
    """Ingest documents from a path."""
    from upii.storage.db import DB
    from upii.storage.vector import LocalVectorStore
    from upii.ingestion.loader import LocalLoader
    from upii.ingestion.chunker import RecursiveChunker
    from upii.ingestion.pipeline import ingest_documents
    from upii.analysis.embeddings import Embedder

    console.print(f"[bold blue]Ingesting[/bold blue] from {path} (Recursive: {recursive}, Force: {force})")
    
    # 1. Init resources
    db = DB()
    try:
        db.init_db()
    except Exception as e:
        console.print(f"[red]DB Init failed: {e}[/red]")
        return

    vector_store = LocalVectorStore()
    loader = LocalLoader()
    chunker = RecursiveChunker()
    embedder = Embedder() # Lazy load model

    # 2. Walk parsing
    processed_count = 0
    skipped_count = 0
    error_count = 0
    
    # We collect all docs first or yield them? 
    # For a CLI progress bar, yielding is better but we don't know total upfront easily without double scan.
    # Let's just process in stream and print status.
    
    updated_count = 0

    from upii.analysis.nlp import TaskExtractor
    extractor = TaskExtractor()

    def _on_result(result):
        nonlocal processed_count, skipped_count, updated_count
        path_ = result.doc_path or result.doc_id

        if result.status == "skipped":
            console.print(f"Skipping [dim]{path_}[/dim] (Unchanged)")
            skipped_count += 1
            return

        if result.status == "updated":
            console.print(
                f"Updating [green]{path_}[/green] "
                f"[dim](purged {result.removed_chunks} stale chunks)[/dim]"
            )
            updated_count += 1
        else:
            console.print(f"Processing [green]{path_}[/green]")

        chunks = result.chunks or []

        # Extract Tasks
        tasks = extractor.extract(chunks)
        if tasks:
            db.add_tasks(tasks)
            console.print(f"[magenta]Extracted {len(tasks)} tasks[/magenta]")

        processed_count += 1
        logger.info(f"Ingested {path_} ({len(chunks)} chunks, {len(tasks)} tasks)")

    def _on_error(doc, exc):
        nonlocal error_count
        console.print(f"[red]Failed to ingest {doc.path}: {exc}[/red]")
        logger.error(f"Ingestion failed for {doc.path}", exc_info=exc)
        error_count += 1

    # 3-4. Deterministic ingest: dedup (no-op on unchanged), edit cleanup, chunk/embed/
    #      store — all via the shared pipeline. Batched so vectors are written once per
    #      batch rather than once per document, which is what keeps throughput flat as
    #      the index grows.
    ingest_documents(
        loader.load(path), db, vector_store, embedder, chunker,
        force=force, on_result=_on_result, on_error=_on_error,
    )

    console.print(
        f"\n[bold]Summary[/bold]: Processed {processed_count} "
        f"(of which {updated_count} updated), Skipped {skipped_count}, Errors {error_count}"
    )
    
    # Metrics
    try:
        from upii.analysis.metrics import MetricsCollector
        if processed_count > 0:
            MetricsCollector().track_explicit_ingest(processed_count)
    except: pass

@app.command()
def search(query: str, limit: int = 5, time: str = typer.Option(None, help="Time filter: last_week, last_month")):
    """Search for relevant documents."""
    from upii.analysis.search import SearchEngine
    
    console.print(f"[bold green]Searching[/bold green] for: '{query}' (Time: {time})")
    
    engine = SearchEngine()
    try:
        results = engine.search(query, time_filter=time, limit=limit)
        
        if not results:
            console.print("[yellow]No results found.[/yellow]")
            return

        for i, chunk in enumerate(results):
            # We assume chunk text is available
            console.print(f"\n[bold]{i+1}.[/bold] [blue]{chunk.doc_hash}[/blue] (Score: N/A)")
            console.print(f"[italic]...{chunk.text.strip()}...[/italic]")
            
    except Exception as e:
        console.print(f"[red]Search failed: {e}[/red]")

@app.command()
def ask(
    question: str,
    debug: bool = typer.Option(False, "--debug", help="Show per-signal fusion scoring"),
    no_answer: bool = typer.Option(
        False, "--no-answer",
        help="Skip LLM generation; show only retrieval (deterministic, reproducible)",
    ),
    w_semantic: Optional[float] = typer.Option(None, "--w-semantic", help="Override semantic fusion weight"),
    w_temporal: Optional[float] = typer.Option(None, "--w-temporal", help="Override temporal fusion weight"),
    w_relational: Optional[float] = typer.Option(None, "--w-relational", help="Override relational fusion weight"),
):
    """Ask a question using local context (v2 semantic+temporal+relational fusion)."""
    from upii.analysis.search import SearchEngine
    from upii.analysis.llm import LocalLLM
    from upii.core.types import RankedChunk

    console.print(f"[bold magenta]Asking:[/bold magenta] {question}")

    # Per-call weight overrides (None -> fall back to config).
    weights = {"semantic": w_semantic, "temporal": w_temporal, "relational": w_relational}
    weights = {k: v for k, v in weights.items() if v is not None} or None

    # 1. Retrieval
    search_engine = SearchEngine()
    try:
        # Only chunks at or above rag_min_similarity reach the answer; none -> not found.
        results = search_engine.search(question, limit=config.rag_max_chunks, weights=weights,
                                       min_similarity=config.rag_min_similarity)

        if debug:
            _print_fusion_debug(results, weights)

    except Exception as e:
        console.print(f"[red]Retrieval failed: {e}[/red]")
        return

    # Retrieval-only: skip the (stochastic) LLM and print the cited chunks the
    # answer would have drawn from. Everything above this point is deterministic,
    # so `--no-answer` gives byte-identical output run to run.
    if no_answer:
        if not results:
            console.print("\n[yellow]No relevant context found.[/yellow]")
            return
        console.print("\n[bold]Retrieved context[/bold] [dim](generation skipped)[/dim]:")
        paths = _source_paths(results)
        for i, r in enumerate(results):
            console.print(f"\n[dim]\\[{i+1}][/dim] [blue]{escape(_source_label(r, paths))}[/blue]")
            console.print(f"[italic]{escape(_excerpt(r.text))}[/italic]")
        return

    if not results:
        # Nothing relevant enough: say so instead of asking the model to improvise.
        console.print(f"\n[yellow]Not found in your memory[/yellow] [dim](no passage reached "
                      f"rag_min_similarity {config.rag_min_similarity:.2f}; no model was called)[/dim]")
        return

    # 2. Generation
    try:
        llm = LocalLLM()
        with console.status("[bold green]Thinking...[/bold green]"):
            answer = llm.answer(question, results)

        console.print("\n[bold]Answer:[/bold]")
        console.print(display_answer(answer.text))
        console.print(f"\n[dim]Answered by: {llm.model_label()}[/dim]")

        # Only the sources the answer actually cites; none for a not-found answer.
        if answer.found and answer.cited:
            console.print("\n[dim]Sources used:[/dim]")
            paths = _source_paths([results[n - 1] for n in answer.cited])
            for n in answer.cited:
                r = results[n - 1]
                console.print(f"\\[{n}] {escape(_source_label(r, paths))}")
                console.print(f"    [dim]{escape(_excerpt(r.text))}[/dim]")
        elif answer.found:
            # The model answered but cited nothing. Never invent a citation: show the
            # passage retrieval ranked first, labelled as not cited.
            r = results[0]
            paths = _source_paths([r])
            console.print(f"\n[dim]{UNCITED_LABEL}:[/dim]")
            console.print(f"{escape(_source_label(r, paths))}")
            console.print(f"    [dim]{escape(_excerpt(r.text))}[/dim]")

    except Exception as e:
        console.print(f"[red]Generation failed: {e}[/red]")

@app.command()
def sources(
    action: str = typer.Argument(..., help="Action: list, enable, disable, audit"),
    name: str = typer.Argument(None, help="Source name (for enable/disable)")
):
    """Manage passive ingestion sources."""
    # Ensure all sources are registered
    import upii.ambient.watcher 
    import upii.ambient.dummy_sources
    from upii.ambient.sources import registry, logger
    
    if action == "list":
        sources = registry.get_all()
        table = Table(title="Passive Sources")
        table.add_column("Name", style="cyan")
        table.add_column("Enabled", style="magenta")
        table.add_column("Running", style="green")
        table.add_column("Description", style="dim")
        
        for s in sources:
            enabled_str = "[green]Yes[/green]" if s['enabled'] else "[red]No[/red]"
            running_str = "Yes" if s['running'] else "No"
            table.add_row(s['name'], enabled_str, running_str, s['description'])
        console.print(table)
        
    elif action == "enable":
        if not name:
            console.print("[red]Please specify a source name.[/red]")
            return
        
        # Special case for filesystem config
        if name == "filesystem":
             path = typer.prompt("Path to watch?")
             # We need to access the source instance to configure it
             # Registry doesn't expose convenient config update manually here yet
             # So we'll grab it
             source = registry.sources.get(name)
             if source:
                 source.configure({"watch_paths": [os.path.abspath(path)]})
        
        try:
            registry.enable(name)
            console.print(f"[green]Enabled {name}[/green]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            
    elif action == "disable":
        if not name:
            console.print("[red]Please specify a source name.[/red]")
            return
        try:
            registry.disable(name)
            console.print(f"[yellow]Disabled {name}[/yellow]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            
    elif action == "audit":
        from upii.ambient.storage import StagingDB
        db = StagingDB()
        try:
            db.init_db()
            logs = db.get_audit_logs()
            if not logs:
                console.print("No audit logs found.")
                return
            
            table = Table(title="Passive Ingestion Audit Log")
            table.add_column("Time", style="dim")
            table.add_column("Source", style="cyan")
            table.add_column("Action", style="bold")
            table.add_column("Details")
            
            for log in logs:
                table.add_row(log['timestamp'], log['source_name'], log['action'], str(log['details']))
            console.print(table)
        except Exception as e:
            console.print(f"[red]Audit log error: {e}[/red]")
            
    else:
        console.print(f"[red]Unknown action: {action}[/red]")

@app.command()
def tasks(
    action: str = typer.Argument("list", help="Action: list, search, done"), 
    arg: str = typer.Argument("", help="Search term or Task ID")
):
    """
    Manage tasks.
    Usage:
      upii tasks list
      upii tasks search "query"
      upii tasks done <task_id>
    """
    from upii.storage.db import DB
    db = DB()
    
    if action == "list":
        tasks = db.get_tasks(status="pending")
        if not tasks:
            console.print("No pending tasks.")
            return
        for t in tasks:
            console.print(f"[bold]{t.task_id[:8]}[/bold]: {t.description} [dim](from {t.source_doc_id[:8]})[/dim]")
            
    elif action == "search":
        tasks = db.get_tasks(search=arg)
        for t in tasks:
            status_color = "green" if t.status == "done" else "yellow"
            console.print(f"[{status_color}]{t.status.upper()}[/{status_color}] [bold]{t.task_id[:8]}[/bold]: {t.description}")
            
    elif action == "done":
        # Argument is ID prefix
        all_pending = db.get_tasks(status="pending")
        # Simple prefix match
        target = next((t for t in all_pending if t.task_id.startswith(arg)), None)
        if target:
            db.update_task_status(target.task_id, "done")
            console.print(f"Marked task [bold]{target.description}[/bold] as done.")
        else:
            console.print(f"[red]Task starting with {arg} not found.[/red]")
            
    else:
        console.print(f"[red]Unknown action: {action}[/red]")

# --- v1.0 Ambient Commands ---
@app.command()
def watch(path: str = typer.Argument(..., help="Path to watch")):
    """Add a directory to ambient monitoring (Opt-in)."""
    from upii.core.features import features
    from upii.ambient.watcher import PollingWatcher
    
    abs_path = os.path.abspath(path)
    if not os.path.exists(abs_path):
        console.print(f"[red]Path not found:[/red] {abs_path}")
        return

    # Enable if not already
    if not features.is_enabled("ambient_memory"):
        if typer.confirm("Ambient Memory is disabled. Enable it?"):
            features.enable("ambient_memory")
        else:
            console.print("Aborted.")
            return

    features.add_watch_path(abs_path)
    console.print(f"[green]Added to watch list:[/green] {abs_path}")
    console.print("Starting watcher in background... (Ctrl+C to stop)")
    
    # For CLI usage, we might want a 'run' command or just run here blocking
    watcher = PollingWatcher()
    watcher.start()
    try:
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        watcher.stop()
        console.print("Watcher stopped.")

from typing import Optional
from rich.table import Table

def _preview(text: Optional[str], width: int = 120) -> str:
    """First `width` chars of text, truncated cleanly on a word boundary."""
    if not text:
        return ""
    flat = " ".join(text.split())  # collapse whitespace/newlines
    if len(flat) <= width:
        return flat
    cut = flat[:width]
    # Back off to the last space so we don't slice a word in half.
    if " " in cut:
        cut = cut[:cut.rfind(" ")]
    return cut + "…"  # ellipsis


@app.command()
def inbox(
    approve: Optional[str] = typer.Option(None, "--approve", "-a", help="Approve event ID to ingest"),
    reject: Optional[str] = typer.Option(None, "--reject", "-r", help="Reject event ID"),
    list_all: bool = typer.Option(False, "--all", help="List pending + approved + rejected events")
):
    """Manage staged ambient events."""
    from upii.ambient import inbox as inbox_ops
    from upii.ambient.storage import StagingDB

    stg = StagingDB()
    try:
        stg.init_db()  # Ensure DB exists
    except Exception:
        pass

    # --- APPROVE -----------------------------------------------------------
    if approve:
        target = inbox_ops.find_event(stg, approve)
        if not target:
            console.print(f"[red]Event {approve} not found.[/red]")
            return

        short = target['event_id'][:8]
        if target['status'] not in ('approved', 'rejected') and target['event_type'] != 'deleted':
            console.print(f"Approving staged content: [green]{target['file_path']}[/green]")
        res = inbox_ops.approve_event(stg, target)

        if res.outcome == inbox_ops.ALREADY_APPROVED:
            console.print(f"[yellow]Event {short} already approved (no-op).[/yellow]")
        elif res.outcome == inbox_ops.WAS_REJECTED:
            console.print(f"[yellow]Event {short} was rejected; not promoting.[/yellow]")
        elif res.outcome == inbox_ops.DELETION_ACKNOWLEDGED:
            console.print(f"[yellow]Cannot approve a deletion event ({os.path.basename(target['file_path'])}).[/yellow]")
        elif res.outcome == inbox_ops.NO_CONTENT:
            console.print("[yellow]No staged content found for this event.[/yellow]")
        else:
            if res.tasks:
                console.print(f"[magenta]Extracted {res.tasks} task(s)[/magenta]")
            console.print(f"[green]Promoted to long-term memory[/green] ({res.chunks} chunk(s))")
        return

    # --- REJECT ------------------------------------------------------------
    if reject:
        target = inbox_ops.find_event(stg, reject)
        if not target:
            console.print(f"[red]Event {reject} not found.[/red]")
            return
        res = inbox_ops.reject_event(stg, target)
        if res.outcome == inbox_ops.ALREADY_REJECTED:
            console.print(f"[yellow]Event {target['event_id'][:8]} already rejected (no-op).[/yellow]")
        elif res.outcome == inbox_ops.WAS_APPROVED:
            console.print(f"[yellow]Event {target['event_id'][:8]} was already approved into LTM; refusing to reject.[/yellow]")
        else:
            console.print(f"[yellow]Rejected[/yellow] {os.path.basename(target['file_path'])} (kept for audit, not in LTM).")
        return

    # --- LIST --------------------------------------------------------------
    events = stg.get_all_events() if list_all else stg.get_pending_events()
    if not events:
        console.print("Inbox empty." if not list_all else "No events recorded.")
        return

    title = "Ambient Inbox (All)" if list_all else "Ambient Inbox (Pending)"
    table = Table(title=title)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Type", style="magenta")
    if list_all:
        table.add_column("Status", style="bold")
    table.add_column("File", style="green")
    table.add_column("Preview", style="dim", max_width=60)
    table.add_column("Time", style="dim")

    for e in events:
        sdoc = stg.get_staging_doc_by_event(e['event_id'])
        if e['event_type'] == 'deleted':
            preview = "[deleted]"
        else:
            preview = _preview(sdoc.get('parsed_content') if sdoc else None)
        row = [e['event_id'][:8], e['event_type']]
        if list_all:
            row.append(e['status'])
        row += [os.path.basename(e['file_path']), preview, str(e['detected_at'])]
        table.add_row(*row)

    console.print(table)


@app.command()
def knowledge(
    action: str = typer.Argument("show", help="Action: wipe, show"),
    graph: bool = typer.Option(False, "--graph", help="Render the knowledge graph to a self-contained HTML file"),
    out: str = typer.Option("graph.html", "--out", help="Output path for --graph HTML"),
):
    """Manage / visualise Knowledge Graph entities."""
    from upii.storage.db import DB

    if graph:
        from upii.analysis.graph import write_graph

        db = DB()
        db.init_db()
        data = write_graph(out, db=db)
        n, e = len(data["nodes"]), len(data["links"])
        console.print(
            f"[green]Rendered knowledge graph[/green] to [bold]{out}[/bold] "
            f"[dim]({n} entities, {e} co-occurrence edges)[/dim]"
        )
        if n == 0:
            console.print("[yellow]Graph is empty — ingest documents to populate entities.[/yellow]")
        return

    if action == "wipe":
        if typer.confirm("Are you sure you want to delete ALL entities? This cannot be undone."):
            db = DB()
            db.init_db()
            db.wipe_entities()
            console.print("[green]Knowledge Graph wiped.[/green]")
    else:
        console.print(f"[red]Unknown action: {action}[/red]")



# --- Metrics (Local Telemetry) ---

@app.command()
def metrics(
    action: str = typer.Argument(..., help="show | export"),
    json_out: bool = typer.Option(False, "--json", help="Output JSON format"),
    export_file: str = typer.Option("upii_metrics_dump.json", "--out", help="Output file for export")
):
    """
    Local telemetry insights.
    
    Examples:
        upii metrics show
        upii metrics export --out report.json
    """
    import json
    from rich.table import Table
    from upii.analysis.metrics import MetricsCollector
    
    collector = MetricsCollector()
    
    # Snapshot current DB stats before showing
    collector.update_db_snapshot()
    
    if action == "show":
        rows = collector.get_history()
        if json_out:
            console.print(json.dumps([dict(r) for r in rows], indent=2, default=str))
        else:
            table = Table(title="Daily Metrics (Last 7 Days)")
            table.add_column("Date", style="cyan")
            table.add_column("Queries", justify="right")
            table.add_column("Ingest (Explicit)")
            table.add_column("Ingest (Passive)")
            table.add_column("Total Docs")
            table.add_column("DB Size (MB)")
            
            for r in rows:
                table.add_row(
                    str(r["date"]),
                    str(r["queries_count"]),
                    str(r["explicit_ingest_count"]),
                    str(r["passive_ingest_count"]),
                    str(r["total_docs_count"]),
                    f"{r['db_size_mb']:.2f}"
                )
            console.print(table)

            # MCP egress audit: recent tool calls MCP clients made (local-only log).
            mcp_calls = collector.get_mcp_calls(limit=10)
            if mcp_calls:
                mtable = Table(title="Recent MCP tool calls (egress audit)")
                mtable.add_column("Time", style="dim")
                mtable.add_column("Tool", style="cyan")
                mtable.add_column("Query")
                mtable.add_column("Chunks", justify="right")
                for c in mcp_calls:
                    q = (c.get("query") or "")
                    q = (q[:40] + "…") if len(q) > 40 else q
                    mtable.add_row(str(c["ts"]), c["tool"], q, str(c["result_count"]))
                console.print(mtable)

    elif action == "export":
        rows = collector.export_all()
        data = [dict(r) for r in rows]
        with open(export_file, "w") as f:
            json.dump(data, f, indent=2, default=str)
        console.print(f"[green]Exported transparency report to {export_file}[/green]")
    else:
        console.print(f"[red]Unknown action: {action}[/red]")



# --- Founder Demo Mode ---

@app.command()
def write(
    topic: str = typer.Argument(..., help="What to write about"),
    target: str = typer.Option("email", help="Format: email, tweet, linkedin"),
    context_limit: int = 5
):
    """
    Draft content in your style using personal context.
    
    Example: upii write "Project Omega update to Alice"
    """
    from upii.analysis.search import SearchEngine
    from upii.analysis.llm import LocalLLM
    from upii.storage.db import DB

    user = getattr(config, "user_name", "Maddy")
    console.print(f"[bold magenta]Drafting {target}:[/bold magenta] {topic}")

    # 1. Retrieve content context (what to say) via semantic search.
    engine = SearchEngine()
    try:
        results = engine.search(topic, limit=context_limit)
    except Exception as e:
        console.print(f"[red]Context retrieval failed: {e}[/red]")
        results = []

    # 2. Retrieve STYLE context (how I say it) from my own writing only.
    style_examples = []
    try:
        db = DB(); db.init_db()
        style_examples = db.get_chunks_by_author(user, limit=3)
    except Exception:
        style_examples = []
    if not style_examples:
        logger.warning("no style examples found; using neutral tone")
        console.print("[dim]No self-authored style examples found; using a neutral tone.[/dim]")

    # 3. Compose with LLM
    from upii.core.errors import ModelError
    try:
        llm = LocalLLM()
    except ModelError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)
    context_str = "\n".join([f"- {r.text}" for r in results]) if results else "No specific context found."
    style_str = "\n".join([f"- {s}" for s in style_examples]) if style_examples else "(no self-authored samples)"

    fmt_hint = {
        "email": "Start with 'Subject: <subject>' on its own line, then a blank line, then the body.",
        "tweet": "A single tweet, under 280 characters, punchy, no hashtags-spam.",
        "linkedin": "A LinkedIn post under 1300 characters. Open with a single-line hook, then the body.",
    }.get(target, "Write clearly and concisely.")

    prompt = f"""
    You are {user}'s personal writing agent. Write as {user}, in the first person.
    Task: Write a {target} about "{topic}".

    Facts / context from my memory (ground the content in these):
    {context_str}

    Samples of my own writing (match this voice and tone):
    {style_str}

    Instructions:
    1. {fmt_hint}
    2. Be concise and authentic; sound like me, not a generic AI.
    3. Do NOT include placeholders like [Your Name]. Sign off as "{user}".
    4. Output ONLY the {target} text, nothing else.

    Draft:
    """

    with console.status("[bold green]Composing...[/bold green]"):
        draft = llm.generate(prompt)

    draft = _postprocess_draft(draft, target, user, llm)
    console.print(Panel(draft, title=f"Generated Draft ({target})", border_style="green",
                        subtitle=f"Answered by: {llm.model_label()}"))


def _postprocess_draft(draft: str, target: str, user: str, llm) -> str:
    """Deterministically shape the LLM draft to the target's contract."""
    import re
    draft = (draft or "").strip()

    if target == "email":
        # Guarantee a 'Subject: ...' first line followed by a blank line + body.
        m = re.search(r"(?im)^\s*subject\s*:\s*(.+)$", draft)
        if m:
            subject = m.group(1).strip()
            body = (draft[:m.start()] + draft[m.end():]).strip()
        else:
            # Synthesize a subject from the first non-empty line.
            first = next((l.strip() for l in draft.splitlines() if l.strip()), "Quick note")
            subject = first[:78]
            body = draft
        return f"Subject: {subject}\n\n{body}".strip()

    if target == "tweet":
        # Re-prompt up to twice to get under 280 chars, then hard-truncate.
        attempts = 0
        while len(draft) > 280 and attempts < 2:
            attempts += 1
            draft = (llm.generate(
                f"Rewrite this as a single tweet under 280 characters. "
                f"Output only the tweet:\n\n{draft}"
            ) or draft).strip()
        if len(draft) > 280:
            cut = draft[:279]
            if " " in cut:
                cut = cut[:cut.rfind(" ")]
            draft = cut + "…"
        return draft

    if target == "linkedin":
        attempts = 0
        while len(draft) > 1300 and attempts < 2:
            attempts += 1
            draft = (llm.generate(
                f"Shorten this LinkedIn post to under 1300 characters, keeping the opening hook. "
                f"Output only the post:\n\n{draft}"
            ) or draft).strip()
        if len(draft) > 1300:
            draft = draft[:1299] + "…"
        return draft

    return draft



if __name__ == "__main__":
    app()

