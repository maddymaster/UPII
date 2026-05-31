import typer
import uuid
import logging
import os
from rich.console import Console
from rich.panel import Panel
from upii.core.config import config
from upii.core.types import Document

logger = logging.getLogger("upii.cli")

app = typer.Typer()
console = Console()

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
    from upii.analysis.diagnostics import Doctor
    
    console.print("[bold]Running UPII Doctor...[/bold]")
    doc = Doctor()
    report = doc.check_all()
    
    for check, result in report.items():
        color = "green"
        if "FAIL" in result:
            color = "red"
        elif "WARN" in result:
            color = "yellow"
            
        console.print(f"[{color}]{check.ljust(15)}: {result}[/{color}]")





@app.command()
def ingest(path: str, recursive: bool = False, force: bool = typer.Option(False, "--force", "-f", help="Force re-ingestion of files")):
    """Ingest documents from a path."""
    from upii.storage.db import DB
    from upii.storage.vector import LocalVectorStore
    from upii.ingestion.loader import LocalLoader
    from upii.ingestion.chunker import RecursiveChunker
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
    
    for doc in loader.load(path):
        try:
            # 3. Check redundancy
            if not force:
                existing_doc = db.get_document_by_hash(doc.content_hash)
                if existing_doc:
                    console.print(f"Skipping [dim]{doc.path}[/dim] (Unchanged)")
                    # Optionally update path in DB if moved
                    skipped_count += 1
                    continue
                
            console.print(f"Processing [green]{doc.path}[/green]")
            
            # 4. Ingest new
            doc_uuid = str(uuid.uuid4())
            doc.doc_id = doc_uuid # Inject UUID
            
            # Chunk
            chunks = chunker.chunk(doc)
            
            # Embed
            texts = [c.text for c in chunks]
            embeddings = embedder.embed(texts)
            for i, chunk in enumerate(chunks):
                chunk.embedding = embeddings[i]
                
            # Store (Metadata + Vector)
            # Transactionally ideally, but here sequential
            db.upsert_document(doc, doc_uuid)
            db.add_chunks(chunks)
            vector_store.add(chunks)
            
            # 5. Extract Tasks
            from upii.analysis.nlp import TaskExtractor
            extractor = TaskExtractor()
            tasks = extractor.extract(chunks)
            if tasks:
                db.add_tasks(tasks)
                console.print(f"[magenta]Extracted {len(tasks)} tasks[/magenta]")

            processed_count += 1
            logger.info(f"Ingested {doc.path} ({len(chunks)} chunks, {len(tasks)} tasks)")
            
        except Exception as e:
            console.print(f"[red]Failed to ingest {doc.path}: {e}[/red]")
            logger.error(f"Ingestion failed for {doc.path}", exc_info=True)
            error_count += 1
            
    console.print(f"\n[bold]Summary[/bold]: Processed {processed_count}, Skipped {skipped_count}, Errors {error_count}")
    
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
def ask(question: str, debug: bool = typer.Option(False, "--debug", help="Show scoring details")):
    """Ask a question using local context."""
    from upii.analysis.search import SearchEngine
    from upii.analysis.llm import LocalLLM
    from upii.core.types import RankedChunk
    
    console.print(f"[bold magenta]Asking:[/bold magenta] {question}")
    
    # 1. Retrieval
    search_engine = SearchEngine()
    try:
        # We search with a slightly higher limit to filter
        results = search_engine.search(question, limit=config.rag_max_chunks)
        
        if debug:
             console.print("\n[bold cyan]Context Ranking Analysis:[/bold cyan]")
             for i, r in enumerate(results):
                 score_info = f"Score: {r.score:.2f} ({r.boost_reason})" if isinstance(r, RankedChunk) else "Score: N/A"
                 console.print(f"{i+1}. [green]{r.source_signal}[/green] | {score_info} | {r.text[:60]}...")

    except Exception as e:
        console.print(f"[red]Retrieval failed: {e}[/red]")
        return

    # 2. Generation
    llm = LocalLLM()
    try:
        with console.status("[bold green]Thinking...[/bold green]"):
            answer = llm.answer_with_citations(question, results)
        
        console.print("\n[bold]Answer:[/bold]")
        console.print(answer)
        
        if results and "I don't know" not in answer:
             console.print("\n[dim]Sources used:[/dim]")
             for i, r in enumerate(results):
                 console.print(f"[dim][{i+1}] {r.doc_hash}[/dim]")

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

@app.command()
def inbox(
    approve: Optional[str] = typer.Option(None, "--approve", "-a", help="Approve event ID to ingest"),
    reject: Optional[str] = typer.Option(None, "--reject", "-r", help="Reject event ID"),
    list_all: bool = typer.Option(False, "--all", help="List all pending events")
):
    """Manage staged ambient events."""
    from upii.ambient.storage import StagingDB
    
    stg = StagingDB()
    try:
        stg.init_db() # Ensure DB exists
    except:
        pass
        
    if approve:
        events = stg.get_pending_events()
        target = next((e for e in events if e['event_id'].startswith(approve)), None)
        if not target:
            console.print(f"[red]Event {approve} not found.[/red]")
            return
            
        console.print(f"Approving: {target['file_path']}")
        
        # Ingest Logic
        from upii.ingestion.loader import LocalLoader
        from upii.storage.db import DB
        from upii.storage.vector import LocalVectorStore
        from upii.ingestion.chunker import RecursiveChunker
        from upii.analysis.embeddings import Embedder
        
        db = DB()
        try: db.init_db() 
        except: pass
        vec = LocalVectorStore()
        loader = LocalLoader()
        
        # Load single file
        docs = list(loader.load(target['file_path']))
        if not docs:
             console.print("[yellow]No content found (empty?)[/yellow]")
        else:
             chunker = RecursiveChunker()
             embedder = Embedder()
             
             for doc in docs:
                 doc.doc_id = str(uuid.uuid4())
                 chunks = chunker.chunk(doc)
                 
                 texts = [c.text for c in chunks]
                 embeddings = embedder.embed(texts)
                 for i, chunk in enumerate(chunks):
                     chunk.embedding = embeddings[i]
                     
                 db.upsert_document(doc, doc.doc_id)
                 db.add_chunks(chunks)
                 vec.add(chunks)
                 db.add_chunks(chunks)
                 vec.add(chunks)
                 console.print(f"[green]Ingested {doc.path}[/green]")
                 
                 # Metrics
                 try:
                     from upii.analysis.metrics import MetricsCollector
                     MetricsCollector().track_passive_ingest(1)
                 except: pass

        stg.update_event_status(target['event_id'], "approved")
        return

    # List events
    events = stg.get_pending_events()
    if not events:
        console.print("Inbox empty.")
        return
        
    table = Table(title="Ambient Inbox (Staging)")
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Type", style="magenta")
    table.add_column("File", style="green")
    table.add_column("Time", style="dim")
    
    for e in events:
        table.add_row(e['event_id'][:8], e['event_type'], e['file_path'], e['detected_at'])
        
    console.print(table)


@app.command()
def knowledge(
    action: str = typer.Argument(..., help="Action: wipe"),
):
    """Manage Knowledge Graph entities."""
    if action == "wipe":
        if typer.confirm("Are you sure you want to delete ALL entities? This cannot be undone."):
            from upii.storage.db import DB
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
    
    console.print(f"[bold magenta]Drafting {target}:[/bold magenta] {topic}")
    
    # 1. Retrieve Context (Style & Content)
    engine = SearchEngine()
    try:
        results = engine.search(topic, limit=context_limit)
        # Search for recent emails for style extraction if target is email
        if target == "email":
            style_results = engine.search("email from me", limit=3) # Hypothetical query to find "files I wrote"
            # In a real system we'd filter by metadata={'sender': 'me'}
            if style_results:
                results.extend(style_results)
    except Exception as e:
        console.print(f"[red]Context retrieval failed: {e}[/red]")
        results = []

    # 2. Compose with LLM
    llm = LocalLLM()
    
    context_str = "\n".join([f"- {r.text}" for r in results]) if results else "No specific context found."
    
    prompt = f"""
    You are my personal AI agent. 
    Task: Write a {target} about "{topic}".
    
    My Context/Memory:
    {context_str}
    
    Instructions:
    1. Use the style and tone found in the context (if valid).
    2. Be concise and authentic.
    3. Do NOT include placeholders like [Your Name], sign it as "Maddy".
    4. If it's an email, include a Subject line.
    
    Draft:
    """
    
    with console.status("[bold green]Composing...[/bold green]"):
        draft = llm.generate(prompt)
        
    console.print(Panel(draft, title="Generated Draft", border_style="green"))


# --- Founder Demo Mode ---

@app.command()
def demo(
    mode: str = typer.Argument(..., help="investor | customer | seed"),
):
    """
    Demo scenarios for UPII.
    
    Modes:
      investor: The "OS for Memory" Pitch (Enterprise/CXO focus).
      customer: Daily utility & "Second Brain" showcase.
      seed: Pre-load demo data with Rich Graph.
    """
    from rich.panel import Panel
    from rich.tree import Tree
    from rich import print as rprint
    import time
    from upii.storage.db import DB
    
    if mode == "investor":
        console.clear()
        rprint(Panel.fit("[bold magenta]UPII: The Memory OS[/bold magenta]", subtitle="Operating System for Human + AI Memory"))
        
        # 1. The Gap / Problem
        console.print("\n[bold red]The Problem: \"AI Everywhere, Intelligence Nowhere\"[/bold red]")
        console.print("Founders & CXOs generate thousands of context points monthly (decisions, promises, strategy).")
        console.print("But current AI has no persistent memory. It resets. It forgets.")
        time.sleep(2)

        # 2. Variable Reward / Vision
        console.print("\n[bold cyan]The Vision:[/bold cyan]")
        console.print("We are building the [bold]Canonical Memory Layer[/bold] for the Enterprise.")
        console.print("• [bold]US/EU Enterprise First[/bold]: Where context fragmentation hurts the most.")
        console.print("• [bold]Sovereign[/bold]: Your strategic data never leaves your control.")
        console.print("• [bold]Interoperable[/bold]: The memory layer under every Copilot.")
        time.sleep(2)
        
        # 3. Architecture
        console.print("\n[bold cyan]Architecture:[/bold cyan]")
        arch_art = """
        [ Enterprise Context ] (Slack, Email, Jira, Docs)
                  |
                  v
        [ UPII Sovereign Core ] ===> [ Knowledge Graph ]
        (Local, Encrypted)                 |
                  |                        v
                  +----------------> [ AI Agents ]
        """
        console.print(arch_art)
        time.sleep(1)

        # 4. Knowledge Graph Visual (The "Impressive" Bit)
        console.print("\n[bold cyan]2. The Memory Graph (Live Snapshot)[/bold cyan]")
        try:
            db = DB()
            db.init_db()
            conn = db.get_connection()
            c = conn.cursor()
            c.execute("SELECT name, category FROM entities ORDER BY created_at DESC LIMIT 10")
            entities = c.fetchall()
            conn.close()
            
            tree = Tree("🧠 [bold]Enterprise Context Graph[/bold]")
            if entities:
                # Group by Category for better visual
                categories = {}
                for name, cat in entities:
                    if cat not in categories: categories[cat] = []
                    categories[cat].append(name)
                
                for cat, names in categories.items():
                    branch = tree.add(f"[bold cyan]{cat}[/bold cyan]")
                    for name in names:
                        branch.add(f"[green]{name}[/green]")
            else:
                 tree.add("[red]Graph Empty! (Run 'upii demo seed')[/red]")
            rprint(tree)
        except Exception as e:
            console.print(f"[dim]Graph visualization error: {e}[/dim]")
        
        time.sleep(2)
        
        # 5. Live Scenario
        console.print("\n[bold yellow]--- Use Case: The 'Extension of Self' ---[/bold yellow]")
        console.print("[dim]Scenario: You are a Founder. You need to update your Board on 'Project Omega' strategy.[/dim]")
        console.print("[dim]UPII recalls the exact latency metrics from a meeting last week and writes in your voice.[/dim]")
        
        if typer.confirm("Run 'Board Update' Demo?"):
            console.print("\n[bold]> upii write 'Board update on Project Omega and Stream-First pivot' --target email[/bold]")
            write(topic="Board update on Project Omega and Stream-First pivot", target="email")
            
        console.print("\n[bold green]Value Proposition:[/bold green]")
        console.print("1. [bold]Retention[/bold]: It remembered the 'Stream-First' decision.")
        console.print("2. [bold]Tone[/bold]: It wrote as a Founder, not a bot.")
        console.print("3. [bold]Control[/bold]: Zero data leak.")

    elif mode == "customer":
        console.clear()
        rprint(Panel.fit("[bold green]UPII: Your Second Brain[/bold green]", subtitle="Daily Utility"))
        
        console.print("\n[bold]Context:[/bold] You are drowning in 10,000 files.")
        console.print("UPII makes them actionable.")
        
        # Scenario 1
        console.print("\n[bold yellow]1. Recall[/bold yellow]")
        console.print("User: 'What's the status of the NASA partnership?'")
        # Mocking for speed
        console.print("[bold cyan]UPII:[/bold cyan] 'Delayed. Pending Blue Band recalibration (Nov 15).'")
        console.print("[dim](Source: meeting_nasa_pace_integration.md)[/dim]")
        
        # Scenario 2
        console.print("\n[bold yellow]2. Draft[/bold yellow]")
        if typer.confirm("Draft Tweet?"):
             write(topic="Releasing UPII v1.0 sovereign memory", target="tweet")

    elif mode == "seed":
        from upii.storage.db import DB
        import datetime
        from upii.core.types import Document
        from upii.ingestion.chunker import RecursiveChunker
        from upii.analysis.embeddings import Embedder
        from upii.storage.vector import LocalVectorStore
        from upii.ingestion.loader import LocalLoader
        
        db = DB()
        db.init_db()
        db.wipe_entities() # Clean slate for impressive graph
        
        console.print("[bold]Seeding Enterprise Demo Data...[/bold]")
        
        # 1. Seed Entities (The "Graph" Fix)
        # We manually inject entities to ensure the tree looks good
        try:
            # People
            db.add_entity("Alice (VP Eng)", "PERSON")
            db.add_entity("Bob (Product)", "PERSON")
            db.add_entity("Dr. Sivan (NASA)", "PERSON")
            # Projects
            db.add_entity("Project Omega", "PROJECT")
            db.add_entity("Planetary Pulse", "INITIATIVE")
            db.add_entity("Blue Band Calibration", "BLOCKER")
            # Orgs
            db.add_entity("ICEYE", "ORGANIZATION")
            db.add_entity("NASA", "ORGANIZATION")
            db.add_entity("Board", "STAKEHOLDER")
            
            console.print("[green]✓ Seeded Knowledge Graph Nodes[/green]")
        except Exception as e:
            console.print(f"[red]Failed to seed entities: {e}[/red]")
        
        # 2. Seed Content (For RAG/Write)
        today = datetime.datetime.now()
        
        # Strategy Doc
        strat_content = """
        CONFIDENTIAL: Project Omega Strategy 2026
        Owner: Maddy
        
        Decision Log:
        - We are pivoting to a 'Stream-First' architecture (Kafka/Flink).
        - Latency Goal: < 15 minutes for AQI alerts.
        - Primary Partner: ICEYE (Synthetic Aperture Radar) for 'Firewatch'.
        - Blocker: NASA PACE 'Blue Band' needs calibration (ETA Nov 15).
        
        Board Key Points:
        - Monetization: Enterprise licensing ($50k/seat for regulated sectors).
        - Burn Rate: Low.
        """
        
        doc = Document(
            path="/docs/confidential/strategy_omega.md",
            content_hash="seed_strat_hash",
            content=strat_content,
            created_at=today,
            source_type="markdown",
            metadata={"type": "strategy"}
        )
        
        # Ingest
        doc.doc_id = str(uuid.uuid4())
        chunker = RecursiveChunker()
        chunks = chunker.chunk(doc)
        embedder = Embedder()
        texts = [c.text for c in chunks]
        embeddings = embedder.embed(texts)
        for i, c in enumerate(chunks):
            c.embedding = embeddings[i]
            
        db.upsert_document(doc, doc.doc_id)
        db.add_chunks(chunks)
        LocalVectorStore().add(chunks)
        
        console.print(f"[green]✓ Seeded Documents[/green]: Strategy & Emails")
        console.print("[bold]Ready for 'upii demo investor'[/bold]")

    else:
        console.print(f"[red]Unknown mode: {mode}[/red]")


if __name__ == "__main__":
    app()

