"""Interactive TUI explorers (extracted from main.py)."""

from __future__ import annotations

import json
import pathlib
import time
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
from rich.table import Table

from ucli.analyzers.registry import build_repo_map
from ucli.lens.lens import lens_from_seeds, rank_by_error_proximity, write_tour_md
from ucli.metrics.ttu import record as ttu_record


def show_function_list(console: Console, functions: dict[str, Any]) -> None:
    """Show paginated function list with enhanced formatting."""
    console.print("\n[bold cyan]Function List[/bold cyan]")

    page_size = 20
    total_pages = (len(functions) + page_size - 1) // page_size
    page = 0

    while True:
        start_idx = page * page_size
        end_idx = min(start_idx + page_size, len(functions))

        table = Table(title=f"Functions (Page {page + 1} of {total_pages})")
        table.add_column("Index", justify="center", style="cyan", width=5)
        table.add_column("Function", style="cyan", no_wrap=True)
        table.add_column("Complexity", justify="center", style="magenta", width=10)
        table.add_column("Side Effects", justify="center", style="yellow", width=12)
        table.add_column("Lines", justify="center", style="green", width=6)

        for i, (func_name, func_data) in enumerate(list(functions.items())[start_idx:end_idx]):
            complexity = func_data.get("complexity", 0)
            side_effects = func_data.get("side_effects", [])
            lines = func_data.get("lines", 0)

            complexity_str = str(complexity)
            if complexity > 5:
                complexity_str = f"[red]{complexity}[/red]"
            elif complexity > 3:
                complexity_str = f"[yellow]{complexity}[/yellow]"

            effects_str = str(len(side_effects)) if side_effects else "0"
            if side_effects:
                effects_str = f"[yellow]{len(side_effects)}[/yellow]"

            table.add_row(
                str(start_idx + i + 1), func_name, complexity_str, effects_str, str(lines)
            )

        console.print(table)

        console.print("\n[dim]Commands: n=next, p=previous, q=quit[/dim]")
        cmd = typer.prompt("", default="q")

        if cmd.lower() == "q":
            break
        elif cmd.lower() == "n" and page < total_pages - 1:
            page += 1
        elif cmd.lower() == "p" and page > 0:
            page -= 1
        else:
            console.print("[red]Invalid command. Use n, p, or q.[/red]")


def show_metrics(console: Console, result: dict[str, Any]) -> None:
    """Show codebase metrics and statistics."""
    functions = result.get("functions", {})

    if not functions:
        console.print("[yellow]No functions to analyze metrics for.[/yellow]")
        return

    total_functions = len(functions)
    high_complexity = sum(1 for f in functions.values() if f.get("complexity", 0) > 5)
    with_side_effects = sum(1 for f in functions.values() if f.get("side_effects", []))
    avg_complexity = sum(f.get("complexity", 0) for f in functions.values()) / total_functions
    total_lines = sum(f.get("lines", 0) for f in functions.values())
    missing_docs = sum(1 for f in functions.values() if f.get("has_docstring") is False)
    missing_types = sum(1 for f in functions.values() if f.get("has_type_hints") is False)

    metrics_table = Table(title="Codebase Metrics")
    metrics_table.add_column("Metric", style="cyan")
    metrics_table.add_column("Value", style="green")
    metrics_table.add_column("Percentage", style="yellow")

    metrics_table.add_row("Total Functions", str(total_functions), "100%")
    metrics_table.add_row(
        "High Complexity", str(high_complexity), f"{high_complexity / total_functions * 100:.1f}%"
    )
    metrics_table.add_row(
        "With Side Effects",
        str(with_side_effects),
        f"{with_side_effects / total_functions * 100:.1f}%",
    )
    metrics_table.add_row(
        "Missing Docstrings",
        str(missing_docs),
        f"{missing_docs / total_functions * 100:.1f}%",
    )
    metrics_table.add_row(
        "Missing Type Hints",
        str(missing_types),
        f"{missing_types / total_functions * 100:.1f}%",
    )
    metrics_table.add_row("Average Complexity", f"{avg_complexity:.1f}", "-")
    metrics_table.add_row("Total Lines", str(total_lines), "-")

    console.print(metrics_table)

    complexity_dist: dict[str, int] = {}
    for f in functions.values():
        complexity = f.get("complexity", 0)
        if complexity <= 2:
            complexity_dist["Low (1-2)"] = complexity_dist.get("Low (1-2)", 0) + 1
        elif complexity <= 5:
            complexity_dist["Medium (3-5)"] = complexity_dist.get("Medium (3-5)", 0) + 1
        else:
            complexity_dist["High (6+)"] = complexity_dist.get("High (6+)", 0) + 1

    console.print("\n[bold cyan]Complexity Distribution[/bold cyan]")
    for level, count in complexity_dist.items():
        percentage = count / total_functions * 100
        console.print(f"  {level}: {count} functions ({percentage:.1f}%)")

    top_complex = sorted(functions.items(), key=lambda x: x[1].get("complexity", 0), reverse=True)[
        :5
    ]
    if top_complex:
        console.print("\n[bold cyan]Top 5 Most Complex Functions[/bold cyan]")
        for i, (name, data) in enumerate(top_complex, 1):
            complexity = data.get("complexity", 0)
            console.print(f"  {i}. {name} (complexity: {complexity})")


def search_functions(console: Console, functions: dict[str, Any]) -> None:
    """Search functions by name or complexity with enhanced formatting."""
    console.print("\n[bold cyan]Function Search[/bold cyan]")
    console.print("Search by function name or complexity threshold\n")

    query = typer.prompt("Enter search term (function name or complexity threshold)")

    if query.isdigit():
        threshold = int(query)
        matches = [
            (name, data)
            for name, data in functions.items()
            if data.get("complexity", 0) >= threshold
        ]

        if matches:
            console.print(
                Panel.fit(
                    f"[green]Found {len(matches)} functions with complexity >= {threshold}[/green]",
                    title="Search Results",
                    border_style="green",
                )
            )

            table = Table(title=f"Functions with complexity >= {threshold}")
            table.add_column("Function", style="cyan", no_wrap=True)
            table.add_column("Complexity", justify="center", style="magenta", width=10)
            table.add_column("Side Effects", justify="center", style="yellow", width=12)
            table.add_column("Lines", justify="center", style="green", width=6)

            for name, data in matches:
                complexity = data.get("complexity", 0)
                side_effects = data.get("side_effects", [])
                lines = data.get("lines", 0)

                complexity_str = str(complexity)
                if complexity > 5:
                    complexity_str = f"[red]{complexity}[/red]"
                elif complexity > 3:
                    complexity_str = f"[yellow]{complexity}[/yellow]"

                effects_str = str(len(side_effects)) if side_effects else "0"
                if side_effects:
                    effects_str = f"[yellow]{len(side_effects)}[/yellow]"

                table.add_row(name, complexity_str, effects_str, str(lines))

            console.print(table)
        else:
            console.print(
                Panel.fit(
                    f"[yellow]No functions found with complexity >= {threshold}[/yellow]",
                    title="No Matches",
                    border_style="yellow",
                )
            )
    else:
        matches = [
            (name, data) for name, data in functions.items() if query.lower() in name.lower()
        ]

        if matches:
            console.print(
                Panel.fit(
                    f"[green]Found {len(matches)} functions matching '{query}'[/green]",
                    title="Search Results",
                    border_style="green",
                )
            )

            table = Table(title=f"Functions matching '{query}'")
            table.add_column("Function", style="cyan", no_wrap=True)
            table.add_column("Complexity", justify="center", style="magenta", width=10)
            table.add_column("Side Effects", justify="center", style="yellow", width=12)
            table.add_column("Lines", justify="center", style="green", width=6)

            for name, data in matches:
                complexity = data.get("complexity", 0)
                side_effects = data.get("side_effects", [])
                lines = data.get("lines", 0)

                complexity_str = str(complexity)
                if complexity > 5:
                    complexity_str = f"[red]{complexity}[/red]"
                elif complexity > 3:
                    complexity_str = f"[yellow]{complexity}[/yellow]"

                effects_str = str(len(side_effects)) if side_effects else "0"
                if side_effects:
                    effects_str = f"[yellow]{len(side_effects)}[/yellow]"

                table.add_row(name, complexity_str, effects_str, str(lines))

            console.print(table)
        else:
            console.print(
                Panel.fit(
                    f"[yellow]No functions found matching '{query}'[/yellow]\n\n"
                    "Try:\n"
                    "• A different search term\n"
                    "• A partial function name\n"
                    "• A complexity threshold (number)",
                    title="No Matches",
                    border_style="yellow",
                )
            )


def generate_lens_interactive(
    console: Console, functions: dict[str, Any], result: dict[str, Any]
) -> None:
    """Generate lens interactively."""
    console.print("\n[bold]Generate Understanding Lens[/bold]")

    console.print("Select seed functions (comma-separated numbers):")
    func_list = list(functions.items())
    for i, (name, data) in enumerate(func_list[:20]):
        complexity = data.get("complexity", 0)
        console.print(f"  {i + 1:2d}. {name} (complexity: {complexity})")

    if len(func_list) > 20:
        console.print(f"  ... and {len(func_list) - 20} more")

    selection = typer.prompt("Enter function numbers (e.g., 1,3,5)", default="1,2,3")

    try:
        indices = [int(x.strip()) - 1 for x in selection.split(",")]
        seeds = [func_list[i][0] for i in indices if 0 <= i < len(func_list)]

        if not seeds:
            console.print("[red]No valid functions selected[/red]")
            return

        console.print(f"[green]Selected seeds: {seeds}[/green]")

        with console.status("[bold green]Generating lens..."):
            lens = lens_from_seeds(seeds, result)
            rank_by_error_proximity(lens)

        lens_functions = lens.get("functions", {})
        console.print(f"[green]Generated lens with {len(lens_functions)} functions[/green]")

        console.print("\nLens functions (ranked by importance):")
        for i, (name, data) in enumerate(lens_functions.items(), 1):
            complexity = data.get("complexity", 0)
            console.print(f"  {i:2d}. {name} (complexity: {complexity})")

    except (ValueError, IndexError) as e:
        console.print(f"[red]Invalid selection: {e}[/red]")


def view_function_details(console: Console, functions: dict[str, Any]) -> None:
    """View detailed function information."""
    console.print("\n[bold]Function Details[/bold]")

    func_name = typer.prompt("Enter function name")

    if func_name not in functions:
        console.print(f"[red]Function '{func_name}' not found[/red]")
        return

    data = functions[func_name]
    console.print(f"\n[bold]{func_name}[/bold]")
    console.print(f"  Complexity: {data.get('complexity', 0)}")
    console.print(f"  Side effects: {', '.join(data.get('side_effects', []) or [])}")
    console.print(f"  Has docstring: {data.get('has_docstring', 'n/a')}")
    console.print(f"  Has type hints: {data.get('has_type_hints', 'n/a')}")
    callers = data.get("callers") or []
    calls = data.get("calls") or []
    if callers:
        console.print(f"  Callers: {', '.join(callers)}")
    if calls:
        console.print(f"  Calls: {', '.join(str(c) for c in calls)}")


def generate_tour_interactive(
    console: Console, functions: dict[str, Any], result: dict[str, Any]
) -> None:
    """Generate tour interactively."""
    console.print("\n[bold]Generate Understanding Tour[/bold]")

    seeds_raw = typer.prompt("Enter seed functions (comma-separated)", default="")

    if not seeds_raw:
        console.print("[yellow]No seeds provided. Using first 3 functions.[/yellow]")
        seeds = list(functions.keys())[:3]
    else:
        seeds = [s.strip() for s in seeds_raw.split(",")]
        valid_seeds = [s for s in seeds if s in functions]
        if not valid_seeds:
            console.print("[red]No valid seeds found[/red]")
            return
        seeds = valid_seeds

    console.print(f"[green]Using seeds: {seeds}[/green]")

    with console.status("[bold green]Generating tour..."):
        lens = lens_from_seeds(seeds, result)
        rank_by_error_proximity(lens)

        if lens.get("functions"):
            tour_md = write_tour_md(lens)
            tour_path = "understanding_tour.md"
            with open(tour_path, "w", encoding="utf-8") as f:
                f.write(tour_md)
            console.print(f"[green]Tour generated: {tour_path}[/green]")
        else:
            console.print("[yellow]No functions in lens for tour generation[/yellow]")


def export_data_interactive(console: Console, result: dict[str, Any]) -> None:
    """Export data interactively."""
    console.print("\n[bold]Export Data[/bold]")
    console.print("1. Export as JSON")
    console.print("2. Export as Markdown")
    console.print("3. Export as SVG")

    choice = typer.prompt("Select format", type=int, default=1)

    if choice == 1:
        output_path = "analysis.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        console.print(f"[green]Exported to {output_path}[/green]")
    elif choice == 2:
        output_path = "analysis.md"
        functions = result.get("functions", {})
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("# Code Analysis Report\n\n")
            f.write(f"Functions analyzed: {len(functions)}\n\n")
            f.write("## Functions\n\n")
            for name, data in functions.items():
                complexity = data.get("complexity", 0)
                side_effects = data.get("side_effects", [])
                f.write(f"- **{name}** (complexity: {complexity})\n")
                if side_effects:
                    f.write(f"  - Side effects: {', '.join(side_effects)}\n")
        console.print(f"[green]Exported to {output_path}[/green]")
    elif choice == 3:
        console.print("[yellow]SVG export not implemented in TUI mode[/yellow]")
    else:
        console.print("[red]Invalid choice[/red]")


def run_tui(scan_path: str) -> None:
    """Launch interactive Text User Interface for code understanding."""
    console = Console()

    try:
        console.print(
            Panel.fit(
                "[bold blue]Understand-First TUI[/bold blue]\n\n"
                "Interactive exploration of your codebase.\n"
                "Navigate through functions, understand relationships,\n"
                "and generate personalized learning paths.",
                title="Welcome",
                border_style="blue",
            )
        )
        console.print("[dim]Press Ctrl+C to exit at any time[/dim]\n")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            load_task = progress.add_task("Loading codebase...", total=100)
            progress.update(load_task, advance=30)
            time.sleep(0.2)
            progress.update(load_task, advance=40)
            result = build_repo_map(pathlib.Path(scan_path))
            progress.update(load_task, advance=30)

        functions = result.get("functions", {})

        if functions:
            high_complexity = sum(1 for f in functions.values() if f.get("complexity", 0) > 5)
            with_side_effects = sum(1 for f in functions.values() if f.get("side_effects", []))

            console.print(
                Panel.fit(
                    f"[green]Codebase loaded successfully![/green]\n\n"
                    f"• [bold]{len(functions)}[/bold] functions available\n"
                    f"• [bold]{high_complexity}[/bold] high complexity functions\n"
                    f"• [bold]{with_side_effects}[/bold] functions with side effects",
                    title="Ready to Explore",
                    border_style="green",
                )
            )
        else:
            console.print(
                Panel.fit(
                    "[yellow]No functions found in the specified path[/yellow]\n\n"
                    "This could mean:\n"
                    "• The path doesn't contain Python files\n"
                    "• The files don't have function definitions\n"
                    "• There's an issue with the file permissions",
                    title="No Functions Found",
                    border_style="yellow",
                )
            )
            return

        while True:
            console.print("\n[bold cyan]Main Menu[/bold cyan]")

            menu_table = Table(show_header=False, box=None)
            menu_table.add_column("Option", style="cyan", width=3)
            menu_table.add_column("Description", style="white")

            menu_table.add_row("1", "View function list")
            menu_table.add_row("2", "Search functions")
            menu_table.add_row("3", "Generate understanding lens")
            menu_table.add_row("4", "View function details")
            menu_table.add_row("5", "Generate tour")
            menu_table.add_row("6", "Export data")
            menu_table.add_row("7", "View metrics")
            menu_table.add_row("0", "Exit")

            console.print(menu_table)

            try:
                choice = typer.prompt("\nSelect option", type=int, default=0)
            except (ValueError, typer.Abort):
                console.print("[red]Invalid input. Please enter a number.[/red]")
                continue

            if choice == 0:
                console.print(
                    Panel.fit(
                        "[yellow]Thanks for using Understand-First TUI![/yellow]\n\n"
                        "Keep exploring your codebase and building understanding!",
                        title="Goodbye",
                        border_style="yellow",
                    )
                )
                break
            elif choice == 1:
                show_function_list(console, functions)
            elif choice == 2:
                search_functions(console, functions)
            elif choice == 3:
                generate_lens_interactive(console, functions, result)
            elif choice == 4:
                view_function_details(console, functions)
            elif choice == 5:
                generate_tour_interactive(console, functions, result)
            elif choice == 6:
                export_data_interactive(console, result)
            elif choice == 7:
                show_metrics(console, result)
            else:
                console.print(
                    Panel.fit(
                        "[red]Invalid option. Please try again.[/red]\n\n"
                        "Select a number between 0-7",
                        title="Invalid Selection",
                        border_style="red",
                    )
                )

        ttu_record("tui_session", {"functions_loaded": len(functions)})

    except KeyboardInterrupt:
        console.print("\n[yellow]TUI interrupted by user[/yellow]")
        console.print("[dim]You can run 'u tui' again anytime to continue[/dim]")
    except Exception as e:
        console.print(
            Panel.fit(
                f"[red]Error in TUI:[/red] {str(e)}\n\n"
                "This might be due to:\n"
                "• File permission issues\n"
                "• Corrupted code files\n"
                "• Missing dependencies",
                title="TUI Error",
                border_style="red",
            )
        )
        raise typer.Exit(1) from None
