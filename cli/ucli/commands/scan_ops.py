"""Scan command implementation (extracted from main.py)."""

from __future__ import annotations

import json
import pathlib
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
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from ucli.analyzers.registry import (
    build_repo_map,
    format_unsupported_summary,
    supported_extensions,
    supported_languages,
)
from ucli.metrics.ttu import record as ttu_record


def _complexity_value(raw: Any) -> int:
    if isinstance(raw, dict):
        return int(raw.get("cyclomatic", 0) or 0)
    try:
        return int(raw or 0)
    except (TypeError, ValueError):
        return 0


def _complexity_kind_label(result: dict[str, Any]) -> str:
    """Honest human label for scan UI (keyword vs structural)."""
    kind = str(result.get("complexity_kind") or "")
    analyzer = str(result.get("analyzer") or "")
    if kind == "mccabe":
        return "McCabe (Python AST)"
    if kind == "ast-cyclomatic" or (analyzer.endswith("-ast") and analyzer != "python-ast"):
        return "ast-cyclomatic (JS/TS/Go structural decision points — not Python McCabe)"
    if kind == "keyword-heuristic" or "best-effort" in analyzer:
        return "keyword-heuristic (JS/TS/Go/Java regex — not structural AST)"
    if kind == "mixed":
        return "mixed (do not compare across languages as one scale)"
    if kind == "none":
        return "n/a"
    return kind or "unknown"


def run_scan(
    path: str,
    o: str,
    *,
    verbose: bool = False,
    debug: bool = False,
    interactive: bool = False,
    lang: str | None = None,
) -> None:
    """Scan codebase and build repository map with enhanced progress tracking."""
    console = Console()

    try:
        p = pathlib.Path(path)
        lang_filter = [x.strip() for x in lang.split(",")] if lang else None

        # Validate input path
        if not p.exists():
            console.print(f"[red]❌ Error:[/red] Path '{path}' does not exist")
            console.print(
                "[yellow]💡 Tip:[/yellow] Use [cyan]u init[/cyan] to set up a new project"
            )
            raise typer.Exit(1) from None

        exts = supported_extensions()
        has_supported = False
        if p.is_file():
            has_supported = p.suffix.lower() in exts
        else:
            for ext in exts:
                if any(p.rglob(f"*{ext}")):
                    has_supported = True
                    break
        if not has_supported:
            console.print(
                f"[yellow]⚠️  Warning:[/yellow] No supported source files found in '{path}'"
            )
            console.print(
                f"[dim]Supported extensions: {', '.join(sorted(exts))} "
                f"(languages: {', '.join(supported_languages())})[/dim]"
            )
            if not Confirm.ask("Continue anyway?"):
                raise typer.Exit(0) from None

        # Interactive mode enhancements
        if interactive:
            console.print("\n[bold cyan]🔧 Interactive Scan Configuration[/bold cyan]\n")

            # Ask for scan options
            Confirm.ask("Include test files?", default=True)
            Confirm.ask("Include documentation files?", default=True)
            IntPrompt.ask("Maximum analysis depth (1-10)", default=5)

            # Update output path if needed
            custom_output = Prompt.ask("Output file path", default=o)
            if custom_output != o:
                o = custom_output

        # Load project config if available
        config_file = p / "understand-first.json"
        config = {}
        if config_file.exists():
            try:
                with open(config_file, encoding="utf-8") as f:
                    config = json.load(f)
                if verbose:
                    console.print(f"[dim]Loaded configuration from {config_file}[/dim]")
            except Exception as e:
                console.print(f"[yellow]Warning:[/yellow] Could not load config: {e}")

        # Show scan configuration
        config_table = Table(title="📋 Scan Configuration", show_header=False, box=None)
        config_table.add_column("Setting", style="cyan", width=20)
        config_table.add_column("Value", style="white")
        config_table.add_row("Target Path", str(p.absolute()))
        config_table.add_row("Output File", o)
        config_table.add_row("Verbose Mode", "✅ Enabled" if verbose else "❌ Disabled")
        config_table.add_row("Debug Mode", "✅ Enabled" if debug else "❌ Disabled")
        config_table.add_row(
            "Language filter",
            ",".join(lang_filter) if lang_filter else "all registered",
        )

        if config:
            config_table.add_row("Project", config.get("project", {}).get("name", "Unknown"))
            config_table.add_row(
                "Language", config.get("project", {}).get("language", "Auto-detect")
            )

        console.print(config_table)
        console.print()

        # Enhanced progress tracking with better error handling
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            # Task 1: Discover files
            discover_task = progress.add_task("🔍 Discovering source files...", total=100)

            try:
                from ucli.analyzers.registry import (
                    discover_source_inventory,
                    normalize_lang_filter,
                )

                by_lang, unsupported = discover_source_inventory(p)
                if lang_filter:
                    wanted = normalize_lang_filter(lang_filter) or set()
                    total_files = sum(
                        len(files) for lang_id, files in by_lang.items() if lang_id in wanted
                    )
                else:
                    total_files = sum(len(files) for files in by_lang.values())

                if total_files == 0:
                    console.print(
                        "[red]❌ No analyzable source files found for the current filter.[/red]\n"
                        f"[dim]Registered languages: {', '.join(supported_languages())}. "
                        "Unsupported extensions are reported, not faked.[/dim]"
                    )
                    if unsupported:
                        console.print(f"[dim]{format_unsupported_summary(unsupported)}[/dim]")
                    raise typer.Exit(1) from None

                progress.update(discover_task, advance=100)

                if verbose:
                    for lang_id, files in by_lang.items():
                        if files:
                            console.print(f"[dim]{lang_id}: {len(files)} file(s)[/dim]")
                    if unsupported:
                        console.print(f"[dim]{format_unsupported_summary(unsupported)}[/dim]")

            except typer.Exit:
                raise
            except Exception as e:
                progress.update(discover_task, advance=100)
                if debug:
                    console.print(f"[red]File discovery error:[/red] {e}")
                else:
                    console.print(
                        "[yellow]⚠️  File discovery encountered issues, continuing...[/yellow]"
                    )

            # Task 2: Parse and analyze
            parse_task = progress.add_task("🧠 Analyzing code structure...", total=100)

            try:
                if verbose:
                    console.print("[dim]Building repository map via language adapters...[/dim]")

                result = build_repo_map(p, languages=lang_filter)

                if not result or not result.get("functions"):
                    console.print("[yellow]⚠️  Analysis completed but no functions found[/yellow]")
                    console.print(
                        "[dim]Check path, --lang filter, and that files match a registered adapter[/dim]"
                    )

                progress.update(parse_task, advance=100)

            except Exception as e:
                progress.update(parse_task, advance=100)
                console.print(f"[red]❌ Analysis failed:[/red] {str(e)}")
                if debug:
                    import traceback

                    console.print(f"[dim]{traceback.format_exc()}[/dim]")
                raise typer.Exit(1) from None

            # Task 3: Write output
            write_task = progress.add_task("💾 Writing analysis results...", total=100)

            try:
                output_path = pathlib.Path(o)
                output_path.parent.mkdir(parents=True, exist_ok=True)

                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(result, f, indent=2)

                progress.update(write_task, advance=100)

                if verbose:
                    console.print(f"[dim]Results written to {output_path.absolute()}[/dim]")

            except Exception as e:
                progress.update(write_task, advance=100)
                console.print(f"[red]❌ Failed to write output:[/red] {str(e)}")
                raise typer.Exit(1) from None

        # Show results summary with enhanced information
        functions_count = len(result.get("functions", {}))
        modules_count = len(
            set(func.get("file", "") for func in result.get("functions", {}).values())
        )
        analyzed_langs = result.get("languages_analyzed") or []
        unsupported = result.get("unsupported") or {}

        # Average complexity only over analyzed functions (never invent for unsupported langs)
        complexities = [
            _complexity_value(func.get("complexity", 0))
            for func in result.get("functions", {}).values()
        ]
        avg_complexity = sum(complexities) / len(complexities) if complexities else None
        high_complexity_count = sum(1 for c in complexities if c > 7)

        fidelity = result.get("analyzer_fidelity") or {}
        fidelity_bits = ", ".join(f"{k}={v}" for k, v in fidelity.items()) or "n/a"
        analyzer_id = result.get("analyzer") or "n/a"
        complexity_label = _complexity_kind_label(result)
        avg_line = (
            f"   • Average complexity (analyzed funcs): {avg_complexity:.1f}\n"
            if avg_complexity is not None
            else "   • Average complexity: n/a (no analyzed functions)\n"
        )
        unsup_line = ""
        if unsupported:
            unsup_line = f"   • {format_unsupported_summary(unsupported)}\n"

        results_panel = Panel(
            f"[green]✅ Scan completed successfully![/green]\n\n"
            f"📊 [bold]Analysis Results:[/bold]\n"
            f"   • Languages analyzed: {', '.join(analyzed_langs) or 'none'}\n"
            f"   • Analyzer: {analyzer_id}\n"
            f"   • Analyzer fidelity: {fidelity_bits}\n"
            f"   • Complexity kind: {complexity_label}\n"
            f"   • Functions analyzed: {functions_count}\n"
            f"   • Modules processed: {modules_count}\n"
            f"{avg_line}"
            f"   • High complexity functions: {high_complexity_count}\n"
            f"{unsup_line}"
            f"   • Output file: [cyan]{o}[/cyan]\n\n"
            f"🎯 [bold]Recommended Next Steps:[/bold]\n"
            f"   • [cyan]u lens from-seeds --map {o} --seed <function>[/cyan] - Create focused analysis\n"
            f"   • [cyan]u tour {o.replace('.json', '_lens.json')}[/cyan] - Generate understanding tour\n"
            f"   • [cyan]u report {o}[/cyan] - Generate detailed report\n"
            f"   • [cyan]u map {o}[/cyan] - Create visual graph",
            title="🎉 Scan Results",
            border_style="green",
        )

        console.print(results_panel)

        # Show warnings if any
        if high_complexity_count > 0:
            console.print(
                f"\n[yellow]⚠️  Found {high_complexity_count} high-complexity functions (>7)[/yellow]"
            )
            console.print("[dim]Consider reviewing these for refactoring opportunities[/dim]")

        # Track TTU metric
        try:
            ttu_record(
                "scan_completed",
                {
                    "path": str(p),
                    "functions_count": functions_count,
                    "modules_count": modules_count,
                    "avg_complexity": avg_complexity,
                    "high_complexity_count": high_complexity_count,
                    "languages_analyzed": analyzed_langs,
                },
            )
        except Exception as e:
            if debug:
                console.print(f"[dim]Failed to track metrics: {e}[/dim]")

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Scan cancelled by user[/yellow]")
        raise typer.Exit(0) from None
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]❌ Error during scan:[/red] {str(e)}")

        # Provide helpful error messages
        if "Permission denied" in str(e):
            console.print(
                "[yellow]💡 Tip:[/yellow] Check file permissions or try running with different privileges"
            )
        elif "No such file" in str(e):
            console.print("[yellow]💡 Tip:[/yellow] Verify the path exists and is accessible")
        elif "JSON" in str(e):
            console.print("[yellow]💡 Tip:[/yellow] Check if the output directory is writable")

        if debug:
            import traceback

            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1) from None
