"""Interactive wizard command (extracted from main.py)."""

from __future__ import annotations

import pathlib
import time

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


def _complexity_value(raw) -> int:
    if isinstance(raw, dict):
        return int(raw.get("cyclomatic", 0) or 0)
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0


def run_wizard(scan_path: str, *, interactive: bool = True) -> None:
    """Interactive wizard to guide users through understanding analysis."""
    console = Console()

    if not interactive:
        console.print("[yellow]Non-interactive mode - running basic analysis[/yellow]")
        result = build_repo_map(pathlib.Path(scan_path))
        console.print(
            f"[green]Analysis complete. Found {len(result.get('functions', {}))} functions.[/green]"
        )
        return

    console.print(
        Panel.fit(
            "[bold blue]🧙 Welcome to the Understand-First Wizard![/bold blue]\n\n"
            "This wizard will guide you through understanding your codebase step by step.\n"
            "We'll help you identify key functions, understand their relationships,\n"
            "and create a personalized learning path.",
            title="Getting Started",
            border_style="blue",
        )
    )

    try:
        console.print("\n[bold cyan]Step 1: Scanning your codebase...[/bold cyan]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            scan_task = progress.add_task("Analyzing code structure...", total=100)

            progress.update(scan_task, advance=20)
            time.sleep(0.5)

            progress.update(scan_task, advance=30)
            result = build_repo_map(pathlib.Path(scan_path))

            progress.update(scan_task, advance=30)
            time.sleep(0.3)

            progress.update(scan_task, advance=20)

        functions = result.get("functions", {})

        if functions:
            high_complexity = sum(
                1 for f in functions.values() if _complexity_value(f.get("complexity", 0)) > 5
            )
            with_side_effects = sum(1 for f in functions.values() if f.get("side_effects", []))

            console.print(
                Panel.fit(
                    f"[green]✓ Analysis complete![/green]\n\n"
                    f"• [bold]{len(functions)}[/bold] functions found\n"
                    f"• [bold]{high_complexity}[/bold] high complexity functions\n"
                    f"• [bold]{with_side_effects}[/bold] functions with side effects",
                    title="Analysis Results",
                    border_style="green",
                )
            )
        else:
            console.print(
                Panel.fit(
                    "[yellow]⚠ No functions found in the specified path[/yellow]\n\n"
                    "This could mean:\n"
                    "• The path doesn't contain Python files\n"
                    "• The files don't have function definitions\n"
                    "• There's an issue with the file permissions",
                    title="No Functions Found",
                    border_style="yellow",
                )
            )
            return

        console.print("\n[bold cyan]Step 2: Function Overview[/bold cyan]")

        table = Table(title="Functions in your codebase")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Complexity", justify="center", style="magenta")
        table.add_column("Side Effects", justify="center", style="yellow")
        table.add_column("Lines", justify="center", style="green")

        for func_name, func_data in list(functions.items())[:10]:
            complexity = _complexity_value(func_data.get("complexity", 0))
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

            table.add_row(func_name, complexity_str, effects_str, str(lines))

        console.print(table)

        if len(functions) > 10:
            console.print(f"\n[yellow]... and {len(functions) - 10} more functions[/yellow]")

        console.print("\n[bold cyan]Step 3: Select Seed Functions[/bold cyan]")
        console.print(
            "Choose functions to start your understanding journey. These will be your 'seeds'.\n"
            "Seeds help us understand which functions are most important to you.\n"
        )

        seeds: list[str] = []
        while True:
            if seeds:
                console.print(f"[green]Current seeds: {', '.join(seeds)}[/green]")
            else:
                console.print("[yellow]No seeds selected yet[/yellow]")

            choice = typer.prompt(
                "Enter function name to add as seed (or 'done' to continue, 'list' to see all functions, 'help' for tips)",
                default="done",
            )

            if choice.lower() == "done":
                break
            if choice.lower() == "list":
                console.print("\n[bold]All functions:[/bold]")
                for i, func_name in enumerate(functions.keys(), 1):
                    complexity = _complexity_value(functions[func_name].get("complexity", 0))
                    console.print(f"  {i:2d}. {func_name} (complexity: {complexity})")
                console.print()
                continue
            if choice.lower() == "help":
                console.print("\n[bold]Tips for selecting seeds:[/bold]")
                console.print("• Choose functions you're most interested in understanding")
                console.print("• Pick functions that seem central to your codebase")
                console.print("• Consider functions with high complexity or side effects")
                console.print("• You can always add more seeds later\n")
                continue
            if choice in functions:
                if choice not in seeds:
                    seeds.append(choice)
                    console.print(f"[green]✓ Added '{choice}' as seed[/green]")
                else:
                    console.print(f"[yellow]'{choice}' is already a seed[/yellow]")
            else:
                console.print(
                    f"[red]Function '{choice}' not found. Try 'list' to see available functions.[/red]"
                )

        if not seeds:
            seeds = list(functions.keys())[:3]
            console.print(f"[yellow]No seeds selected. Using first 3 functions: {seeds}[/yellow]")
            console.print(
                "[dim]You can always run the wizard again to select different seeds[/dim]"
            )

        console.print(f"\n[green]✓ Selected seeds: {seeds}[/green]\n")

        console.print("[bold cyan]Step 4: Generating Understanding Lens...[/bold cyan]")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            lens_task = progress.add_task("Building understanding lens...", total=100)

            progress.update(lens_task, advance=25)
            time.sleep(0.3)

            progress.update(lens_task, advance=25)
            lens = lens_from_seeds(seeds, result)

            progress.update(lens_task, advance=25)
            rank_by_error_proximity(lens)

            progress.update(lens_task, advance=25)

        lens_functions = lens.get("functions", {})

        console.print(
            Panel.fit(
                f"[green]✓ Generated understanding lens![/green]\n\n"
                f"• [bold]{len(lens_functions)}[/bold] functions in your lens\n"
                f"• Functions ranked by importance and error proximity\n"
                f"• Ready for tour generation",
                title="Lens Generated",
                border_style="green",
            )
        )

        console.print("\n[bold cyan]Step 5: Understanding Lens Results[/bold cyan]")
        console.print("Functions in your understanding lens (ranked by importance):\n")

        lens_table = Table(title="Understanding Lens Functions")
        lens_table.add_column("Rank", justify="center", style="cyan")
        lens_table.add_column("Function", style="cyan", no_wrap=True)
        lens_table.add_column("Complexity", justify="center", style="magenta")
        lens_table.add_column("Side Effects", justify="center", style="yellow")
        lens_table.add_column("Importance", justify="center", style="green")

        for i, (func_name, func_data) in enumerate(lens_functions.items(), 1):
            complexity = _complexity_value(func_data.get("complexity", 0))
            side_effects = func_data.get("side_effects", [])
            importance = func_data.get("importance", 0)

            complexity_str = str(complexity)
            if complexity > 5:
                complexity_str = f"[red]{complexity}[/red]"
            elif complexity > 3:
                complexity_str = f"[yellow]{complexity}[/yellow]"

            effects_str = str(len(side_effects)) if side_effects else "0"
            if side_effects:
                effects_str = f"[yellow]{len(side_effects)}[/yellow]"

            importance_str = f"{importance:.1f}" if importance else "N/A"

            lens_table.add_row(str(i), func_name, complexity_str, effects_str, importance_str)

        console.print(lens_table)

        console.print("\n[bold cyan]Step 6: Generating Understanding Tour...[/bold cyan]")

        if lens_functions:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                tour_task = progress.add_task("Generating understanding tour...", total=100)

                progress.update(tour_task, advance=50)
                tour_md = write_tour_md(lens)

                progress.update(tour_task, advance=30)
                tour_path = "understanding_tour.md"
                with open(tour_path, "w", encoding="utf-8") as f:
                    f.write(tour_md)

                progress.update(tour_task, advance=20)

            console.print(
                Panel.fit(
                    f"[green]✓ Tour generated successfully![/green]\n\n"
                    f"• File: [bold]{tour_path}[/bold]\n"
                    f"• Contains step-by-step guidance\n"
                    f"• Ready for review and learning",
                    title="Tour Generated",
                    border_style="green",
                )
            )
        else:
            console.print(
                Panel.fit(
                    "[yellow]⚠ No functions in lens for tour generation[/yellow]\n\n"
                    "This usually means the selected seeds didn't have enough\n"
                    "connections to other functions in your codebase.",
                    title="No Tour Generated",
                    border_style="yellow",
                )
            )

        console.print("\n[bold green]🎉 Wizard Complete![/bold green]")

        summary_table = Table(title="What you've accomplished")
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Value", style="green")

        summary_table.add_row("Functions analyzed", str(len(functions)))
        summary_table.add_row("Seeds selected", str(len(seeds)))
        summary_table.add_row("Lens functions", str(len(lens_functions)))
        summary_table.add_row("Tour generated", "Yes" if lens_functions else "No")

        console.print(summary_table)

        console.print("\n[bold cyan]Next steps:[/bold cyan]")
        console.print("  • Review the understanding tour to understand your code")
        console.print("  • Use 'u map' to visualize the code structure")
        console.print("  • Use 'u diff' to track changes over time")
        console.print("  • Use 'u ci' to integrate with your CI/CD pipeline")
        console.print("  • Use 'u tui' for an interactive exploration experience")

        ttu_record(
            "wizard_completed",
            {
                "functions_analyzed": len(functions),
                "seeds_selected": len(seeds),
                "lens_functions": len(lens_functions),
                "tour_generated": bool(lens_functions),
            },
        )

    except KeyboardInterrupt:
        console.print("\n[yellow]Wizard interrupted by user[/yellow]")
        console.print("[dim]You can run 'u wizard' again anytime to continue[/dim]")
    except Exception as e:
        console.print(
            Panel.fit(
                f"[red]Error during wizard:[/red] {str(e)}\n\n"
                "This might be due to:\n"
                "• File permission issues\n"
                "• Corrupted code files\n"
                "• Missing dependencies\n\n"
                "Try running with --interactive=false for basic analysis",
                title="Wizard Error",
                border_style="red",
            )
        )
        raise typer.Exit(1) from None
