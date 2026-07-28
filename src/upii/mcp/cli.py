"""``upii mcp`` subcommands: serve / enable / disable / status.

The server is off by default; ``enable`` flips the persisted flag in ``mcp.yaml``
(next to the database) and ``serve`` refuses to start until it is on.
"""
import typer
from rich.console import Console
from rich.table import Table

from upii.mcp.config import MCPConfig

mcp_app = typer.Typer(help="Local MCP server: expose UPII memory to MCP clients (read-only).")
console = Console()


@mcp_app.command()
def serve():
    """Run the MCP server on stdio (blocks). Configure your client to spawn this."""
    cfg = MCPConfig.load()
    if not cfg.enabled:
        console.print(
            "[red]MCP server is disabled.[/red] Run [bold]upii mcp enable[/bold] first "
            "(it is off by default)."
        )
        raise typer.Exit(code=1)
    try:
        from upii.mcp.server import serve as _serve
    except ImportError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1)
    _serve(mcp_config=cfg)


@mcp_app.command()
def enable():
    """Turn the MCP server on (persisted to mcp.yaml)."""
    cfg = MCPConfig.load()
    cfg.enabled = True
    path = cfg.save()
    console.print(f"[green]MCP server enabled.[/green] Config: {path}")
    console.print("Start it with [bold]upii mcp serve[/bold], or point your MCP client at it.")


@mcp_app.command()
def disable():
    """Turn the MCP server off."""
    cfg = MCPConfig.load()
    cfg.enabled = False
    path = cfg.save()
    console.print(f"[yellow]MCP server disabled.[/yellow] Config: {path}")


@mcp_app.command()
def status():
    """Show the current MCP config: enabled state, per-tool scopes, exposure."""
    cfg = MCPConfig.load()
    console.print(
        f"MCP server: {'[green]enabled[/green]' if cfg.enabled else '[red]disabled[/red]'}"
    )
    table = Table(title="Tool scopes")
    table.add_column("Tool", style="cyan")
    table.add_column("Exposed", style="magenta")
    for name, on in cfg.tools.items():
        table.add_row(name, "[green]yes[/green]" if on else "[red]no[/red]")
    console.print(table)
    exposed = cfg.expose_sources
    console.print(f"expose_sources: [bold]{exposed}[/bold]")
    console.print(f"max_chunks_per_call: [bold]{cfg.max_chunks_per_call}[/bold]")
