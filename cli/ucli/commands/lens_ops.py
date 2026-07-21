"""Lens command implementations (extracted from main.py)."""

from __future__ import annotations

import json
import os
import pathlib
import traceback
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.prompt import Prompt
from rich.table import Table

from ucli.config import load_config, load_preset
from ucli.lens.ingest import seeds_from_github_log, seeds_from_jira
from ucli.lens.lens import (
    explain_node,
    lens_from_issue,
    lens_from_seeds,
    merge_trace_into_lens,
    rank_by_error_proximity,
)
from ucli.metrics.ttu import record as ttu_record


def run_lens_from_issue(issue_md: str, map_path: str, o: str) -> None:
    with open(map_path, encoding="utf-8") as f:
        repo_map = json.load(f)
    lens = lens_from_issue(issue_md, repo_map)
    rank_by_error_proximity(lens)
    os.makedirs(pathlib.Path(o).parent, exist_ok=True)
    with open(o, "w", encoding="utf-8") as f:
        json.dump(lens, f, indent=2)
    from rich import print as rprint

    rprint(f"[green]Wrote[/green] {o}")


def run_lens_from_seeds(
    seed: list[str],
    map_path: str,
    o: str,
    *,
    interactive: bool = False,
    verbose: bool = False,
    exact: bool = False,
) -> None:
    """Create understanding lens from seed functions with enhanced TUI."""
    console = Console()

    try:
        with open(map_path, encoding="utf-8") as f:
            repo_map = json.load(f)

        seeds = seed.copy() if seed else []

        if interactive:
            console.print(
                Panel(
                    "[bold blue]🔍 Interactive Seed Selection[/bold blue]\n"
                    "Select functions to include in your understanding lens.\n"
                    "This will help focus your analysis on specific areas of the codebase.",
                    title="Lens Creation",
                    border_style="blue",
                )
            )

            functions = list(repo_map.get("functions", {}).keys())
            if not functions:
                console.print("[red]No functions found in map. Run 'u scan' first.[/red]")
                raise typer.Exit(1) from None

            func_table = Table(title="Available Functions", show_header=True)
            func_table.add_column("Index", style="cyan", width=6)
            func_table.add_column("Function", style="white")
            func_table.add_column("File", style="dim")
            func_table.add_column("Complexity", style="yellow")

            for i, func_name in enumerate(functions, 1):
                func_data = repo_map["functions"][func_name]
                complexity = func_data.get("complexity", 0)
                file_path = func_data.get("file", "unknown")
                func_table.add_row(str(i), func_name, file_path, str(complexity))

            console.print(func_table)
            console.print()

            while True:
                choice = Prompt.ask("Select function index (or 'done' to finish)", default="done")

                if choice.lower() == "done":
                    break

                try:
                    index = int(choice) - 1
                    if 0 <= index < len(functions):
                        selected_func = functions[index]
                        if selected_func not in seeds:
                            seeds.append(selected_func)
                            console.print(f"[green]✓ Added[/green] {selected_func}")
                        else:
                            console.print(f"[yellow]⚠ Already selected[/yellow] {selected_func}")
                    else:
                        console.print("[red]Invalid index. Please try again.[/red]")
                except ValueError:
                    console.print("[red]Please enter a valid number or 'done'.[/red]")

            if not seeds:
                console.print("[yellow]No seeds selected. Using first 5 functions.[/yellow]")
                seeds = functions[:5]

        config_table = Table(title="Lens Configuration", show_header=False)
        config_table.add_column("Setting", style="cyan")
        config_table.add_column("Value", style="white")
        config_table.add_row("Map File", map_path)
        config_table.add_row("Seeds", f"{len(seeds)} selected")
        config_table.add_row("Output File", o)

        console.print(config_table)
        console.print()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            lens_task = progress.add_task("Creating understanding lens...", total=100)
            progress.update(lens_task, advance=30)

            lens = lens_from_seeds(seeds, repo_map, exact=exact)
            rank_by_error_proximity(lens)

            progress.update(lens_task, advance=70)

            os.makedirs(pathlib.Path(o).parent, exist_ok=True)
            with open(o, "w", encoding="utf-8") as f:
                json.dump(lens, f, indent=2)

            progress.update(lens_task, advance=100)

        lens_functions = len(lens.get("functions", {}))

        results_panel = Panel(
            f"[green]✓ Lens created successfully![/green]\n\n"
            f"📊 [bold]Lens Summary:[/bold]\n"
            f"   • Functions in lens: {lens_functions}\n"
            f"   • Seeds used: {len(seeds)}\n"
            f"   • Output file: {o}\n\n"
            f"🎯 [bold]Next steps:[/bold]\n"
            f"   • Run [cyan]u tour {o}[/cyan] to generate an understanding tour\n"
            f"   • Run [cyan]u trace module <file> <function>[/cyan] to add runtime traces",
            title="Lens Creation Results",
            border_style="green",
        )

        console.print(results_panel)

        ttu_record(
            "lens_created",
            {
                "seeds_count": len(seeds),
                "lens_functions": lens_functions,
                "interactive": interactive,
            },
        )

    except Exception as e:
        console.print(f"[red]Error creating lens:[/red] {str(e)}")
        if verbose:
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1) from None


def run_lens_merge_trace(lens_json: str, trace_json: str, o: str) -> None:
    with open(lens_json, encoding="utf-8") as f:
        lens = json.load(f)
    with open(trace_json, encoding="utf-8") as f:
        trace = json.load(f)
    merged = merge_trace_into_lens(lens, trace)
    rank_by_error_proximity(merged)
    os.makedirs(pathlib.Path(o).parent, exist_ok=True)
    with open(o, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)
    from rich import print as rprint

    rprint(f"[green]Wrote[/green] {o}")


def run_lens_preset(label: str, map_path: str, o: str) -> None:
    cfg = load_config()
    seeds = load_preset(label)
    hops = cfg.get("hops", 2)
    with open(map_path, encoding="utf-8") as f:
        repo_map = json.load(f)
    lens = lens_from_seeds(seeds, repo_map, hops=hops)
    with open(o, "w", encoding="utf-8") as wf:
        json.dump(lens, wf, indent=2)
    from rich import print as rprint

    rprint(f"[green]Lens written[/green] {o}")


def run_ingest_github(log_path: str) -> None:
    seeds = seeds_from_github_log(log_path)
    from rich import print as rprint

    rprint(json.dumps({"seeds": seeds}, indent=2))


def run_ingest_jira(jira_path: str) -> None:
    seeds = seeds_from_jira(jira_path)
    from rich import print as rprint

    rprint(json.dumps({"seeds": seeds}, indent=2))


def run_lens_explain(
    qname: str,
    lens: str,
    repo: str,
    *,
    json_out: bool = False,
) -> None:
    with open(lens, encoding="utf-8") as f:
        lens_data = json.load(f)
    with open(repo, encoding="utf-8") as f:
        repo_map = json.load(f)
    info = explain_node(qname, lens_data, repo_map)
    from rich import print as rprint

    if json_out:
        rprint(json.dumps(info, indent=2))
        return
    rprint(info.get("qname"))
    rprint("  reason:")
    for r in info.get("reason", []):
        k, v = next(iter(r.items()))
        rprint(f"    - {k}: {v}")
    edges: dict[str, Any] = info.get("edges", {})
    rprint("  edges:")
    rprint("    callers:", ", ".join(edges.get("callers", [])))
    rprint("    callees:", ", ".join(edges.get("callees", [])))
