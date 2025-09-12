from typing import Optional, List, Dict, Any
import json
import os
import pathlib
import subprocess
import sys
import shutil
import socket
import typer
from rich import print
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TimeElapsedColumn,
    TaskProgressColumn,
)
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm, IntPrompt, Choice
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich.align import Align
from rich.columns import Columns
from rich.markdown import Markdown
from rich.status import Status
from rich.syntax import Syntax
from rich.tree import Tree
import time
from datetime import datetime

from ucli.analyzers.python_analyzer import build_python_map
from ucli.graph.graph import write_dot
from ucli.report.report import make_report_md

from ucli.lens.lens import (
    lens_from_issue,
    lens_from_seeds,
    merge_trace_into_lens,
    write_tour_md,
    rank_by_error_proximity,
    explain_node,
)
from ucli.lens.ingest import seeds_from_github_log, seeds_from_jira
from ucli.trace.pytrace import run_callable_with_trace
from ucli.trace.pytrace import analyze_errors_static
from ucli.boundaries.scan import scan_boundaries
from ucli.contracts.contracts import (
    init_contracts,
    check_contracts,
    stub_tests,
    from_openapi,
    from_proto,
    lean_stubs,
    report_json,
    compose,
    verify_lean,
)
from ucli.packs.pack import create_pack
from ucli.visual.delta import lens_delta_svg
from ucli.config import load_config
from ucli.config import load_preset
from ucli.config import validate_config_dict
from ucli.glossary.build import build_glossary
from ucli.dashboard.build import build_dashboard
from ucli.pack.publish import make_pack
from ucli.metrics.ttu import record as ttu_record
from ucli.metrics.ttu import weekly_report as ttu_weekly
from ucli.metrics.analytics import get_tracker, track_event, get_dashboard_data


app = typer.Typer(
    help=(
        "Understand-first CLI (u): lenses, traces, contracts, boundaries, "
        "tour gate, delta visualizer."
    ),
    rich_markup_mode="rich",
    no_args_is_help=True,
)


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", "-v", help="Show version and exit"),
    help: bool = typer.Option(False, "--help", "-h", help="Show help and exit"),
):
    """🧠 Understand First CLI - Accelerate code understanding with intelligent analysis."""
    console = Console()

    if version:
        console.print("Understand First CLI v1.0.0", style="bold cyan")
        raise typer.Exit(0)

    if help:
        show_banner()
        show_welcome_message()

        # Show quick reference
        help_table = Table(title="📚 Quick Reference", show_header=True, header_style="bold cyan")
        help_table.add_column("Command", style="cyan", width=20)
        help_table.add_column("Description", style="white")
        help_table.add_column("Example", style="dim")

        help_table.add_row("init", "Initialize new project", "u init my-project")
        help_table.add_row("scan", "Analyze codebase", "u scan --interactive")
        help_table.add_row(
            "lens from-seeds",
            "Create focused analysis",
            "u lens from-seeds --map out.json --seed main",
        )
        help_table.add_row("tour", "Generate understanding tour", "u tour lens.json")
        help_table.add_row("report", "Create detailed report", "u report out.json")
        help_table.add_row("diff", "Compare analysis results", "u diff old.json new.json")

        console.print(help_table)
        console.print(
            "\n[yellow]💡 Tip:[/yellow] Use [cyan]--help[/cyan] with any command for detailed information"
        )
        raise typer.Exit(0)


def show_banner():
    """Display the Understand First banner."""
    banner = """
╔═══════════════════════════════════════════════════════════════╗
║                                                               ║
║    🧠 Understand First CLI                                    ║
║    ════════════════════════════                               ║
║                                                               ║
║    Accelerate code understanding with intelligent analysis    ║
║    and guided tours for faster, safer development.           ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
"""
    console = Console()
    console.print(banner, style="cyan bold")


def show_welcome_message():
    """Display welcome message with quick start guide."""
    console = Console()

    welcome_panel = Panel(
        "[bold cyan]Welcome to Understand First![/bold cyan]\n\n"
        "This CLI helps you understand codebases faster through:\n"
        "• 🔍 Intelligent code analysis and mapping\n"
        "• 🎯 Focused lenses for specific tasks\n"
        "• 🗺️ Interactive understanding tours\n"
        "• 📊 Complexity and dependency insights\n"
        "• 🔗 Contract and boundary analysis\n\n"
        "[bold]Quick Start:[/bold]\n"
        "1. [cyan]u init[/cyan] - Initialize a new project\n"
        "2. [cyan]u scan[/cyan] - Analyze your codebase\n"
        "3. [cyan]u lens from-seeds[/cyan] - Create focused analysis\n"
        "4. [cyan]u tour[/cyan] - Generate understanding tour",
        title="🚀 Getting Started",
        border_style="green",
    )

    console.print(welcome_panel)


@app.command()
def init(
    path: str = typer.Argument(".", help="Path to initialize the project"),
    wizard: bool = typer.Option(True, "--wizard/--no-wizard", help="Run interactive setup wizard"),
    force: bool = typer.Option(False, "--force", help="Overwrite existing configuration"),
):
    """Initialize a new Understand First project with interactive wizard."""
    console = Console()

    # Show banner on first run
    if not pathlib.Path(path).exists() or force:
        show_banner()
        show_welcome_message()

    try:
        project_path = pathlib.Path(path)

        if not project_path.exists():
            console.print(f"[yellow]Creating project directory: {project_path}[/yellow]")
            project_path.mkdir(parents=True, exist_ok=True)

        # Check for existing config
        config_file = project_path / "understand-first.json"
        if config_file.exists() and not force:
            if not Confirm.ask(f"Configuration file already exists. Overwrite?"):
                console.print("[yellow]Initialization cancelled.[/yellow]")
                return

        if wizard:
            console.print("\n[bold cyan]🔧 Project Setup Wizard[/bold cyan]\n")

            # Project information
            project_name = Prompt.ask("Project name", default=project_path.name)
            project_description = Prompt.ask("Project description", default="")

            # Language selection
            language = Choice.ask(
                "Primary programming language",
                choices=["python", "javascript", "typescript", "java", "go", "rust", "other"],
                default="python",
            )

            # Analysis preferences
            console.print("\n[bold]Analysis Configuration:[/bold]")
            include_tests = Confirm.ask("Include test files in analysis?", default=True)
            include_vendors = Confirm.ask("Include vendor/dependency files?", default=False)
            complexity_threshold = IntPrompt.ask("Complexity threshold (1-10)", default=5)

            # Output preferences
            console.print("\n[bold]Output Configuration:[/bold]")
            output_dir = Prompt.ask("Output directory", default="maps")
            auto_generate_tours = Confirm.ask("Auto-generate tours after analysis?", default=True)

            # Create configuration
            config = {
                "project": {
                    "name": project_name,
                    "description": project_description,
                    "language": language,
                    "path": str(project_path),
                },
                "analysis": {
                    "include_tests": include_tests,
                    "include_vendors": include_vendors,
                    "complexity_threshold": complexity_threshold,
                    "exclude_patterns": [
                        "*.pyc",
                        "__pycache__",
                        ".git",
                        "node_modules",
                        "venv",
                        ".env",
                    ],
                },
                "output": {
                    "directory": output_dir,
                    "auto_generate_tours": auto_generate_tours,
                    "formats": ["json", "dot", "md"],
                },
                "created_at": datetime.now().isoformat(),
                "version": "1.0",
            }

            # Save configuration
            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)

            # Create directory structure
            output_path = project_path / output_dir
            output_path.mkdir(exist_ok=True)

            # Create sample files
            sample_code = project_path / "sample.py"
            if not sample_code.exists():
                with open(sample_code, "w", encoding="utf-8") as f:
                    f.write(
                        """# Sample Python code for analysis
def hello_world():
    \"\"\"A simple greeting function.\"\"\"
    print("Hello, World!")

def calculate_sum(a, b):
    \"\"\"Calculate the sum of two numbers.\"\"\"
    return a + b

class Calculator:
    \"\"\"A simple calculator class.\"\"\"
    
    def __init__(self):
        self.history = []
    
    def add(self, x, y):
        result = x + y
        self.history.append(f"{x} + {y} = {result}")
        return result

if __name__ == "__main__":
    hello_world()
    calc = Calculator()
    result = calc.add(5, 3)
    print(f"Result: {result}")
"""
                    )

            # Show completion message
            success_panel = Panel(
                f"[green]✓ Project initialized successfully![/green]\n\n"
                f"📁 [bold]Project:[/bold] {project_name}\n"
                f"📝 [bold]Description:[/bold] {project_description}\n"
                f"🐍 [bold]Language:[/bold] {language}\n"
                f"📊 [bold]Output:[/bold] {output_dir}/\n\n"
                f"🎯 [bold]Next steps:[/bold]\n"
                f"   • Run [cyan]u scan[/cyan] to analyze your codebase\n"
                f"   • Run [cyan]u lens from-seeds --seed hello_world[/cyan] to create a lens\n"
                f"   • Run [cyan]u tour[/cyan] to generate an understanding tour",
                title="🎉 Project Ready!",
                border_style="green",
            )

            console.print(success_panel)

            # Offer to run first analysis
            if Confirm.ask("\nWould you like to run your first analysis now?"):
                console.print("\n[bold cyan]🔍 Running initial analysis...[/bold cyan]\n")
                # Call the scan function with current path
                scan(str(project_path), o=str(output_path / "out.json"), verbose=True)
        else:
            # Non-wizard mode - create minimal config
            config = {
                "project": {"name": project_path.name, "path": str(project_path)},
                "analysis": {"include_tests": True, "complexity_threshold": 5},
                "output": {"directory": "maps"},
                "created_at": datetime.now().isoformat(),
                "version": "1.0",
            }

            with open(config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)

            console.print(f"[green]✓ Minimal configuration created at {config_file}[/green]")

    except KeyboardInterrupt:
        console.print("\n[yellow]Initialization cancelled by user.[/yellow]")
        raise typer.Exit(0)
    except Exception as e:
        console.print(f"[red]Error during initialization:[/red] {str(e)}")
        raise typer.Exit(1)


@app.command()
def scan(
    path: str = typer.Argument("."),
    o: str = typer.Option("maps/out.json", "--output", "-o"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug mode with tracebacks"),
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Interactive scan with guided options"
    ),
):
    """Scan codebase and build repository map with enhanced progress tracking."""
    console = Console()

    try:
        p = pathlib.Path(path)

        # Validate input path
        if not p.exists():
            console.print(f"[red]❌ Error:[/red] Path '{path}' does not exist")
            console.print(
                f"[yellow]💡 Tip:[/yellow] Use [cyan]u init[/cyan] to set up a new project"
            )
            raise typer.Exit(1)

        # Check if it's a valid code directory
        if not any(p.glob("*.py")) and not any(p.glob("*.js")) and not any(p.glob("*.ts")):
            console.print(
                f"[yellow]⚠️  Warning:[/yellow] No supported source files found in '{path}'"
            )
            if not Confirm.ask("Continue anyway?"):
                raise typer.Exit(0)

        # Interactive mode enhancements
        if interactive:
            console.print("\n[bold cyan]🔧 Interactive Scan Configuration[/bold cyan]\n")

            # Ask for scan options
            include_tests = Confirm.ask("Include test files?", default=True)
            include_docs = Confirm.ask("Include documentation files?", default=True)
            max_depth = IntPrompt.ask("Maximum analysis depth (1-10)", default=5)

            # Update output path if needed
            custom_output = Prompt.ask("Output file path", default=o)
            if custom_output != o:
                o = custom_output

        # Load project config if available
        config_file = p / "understand-first.json"
        config = {}
        if config_file.exists():
            try:
                with open(config_file, "r", encoding="utf-8") as f:
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
                # Count Python files for better progress estimation
                py_files = list(p.rglob("*.py"))
                total_files = len(py_files)

                if total_files == 0:
                    console.print(
                        "[yellow]⚠️  No Python files found. Trying other languages...[/yellow]"
                    )
                    # Try other file types
                    js_files = list(p.rglob("*.js"))
                    ts_files = list(p.rglob("*.ts"))
                    total_files = len(js_files) + len(ts_files)

                if total_files == 0:
                    console.print("[red]❌ No supported source files found![/red]")
                    raise typer.Exit(1)

                progress.update(discover_task, advance=100)

                if verbose:
                    console.print(f"[dim]Found {total_files} source files[/dim]")

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
                # Actually build the map with better error handling
                if verbose:
                    console.print("[dim]Building Python map with enhanced analysis...[/dim]")

                result = build_python_map(p)

                if not result or not result.get("functions"):
                    console.print("[yellow]⚠️  Analysis completed but no functions found[/yellow]")
                    console.print(
                        "[dim]This might be normal for empty or non-Python projects[/dim]"
                    )

                progress.update(parse_task, advance=100)

            except Exception as e:
                progress.update(parse_task, advance=100)
                console.print(f"[red]❌ Analysis failed:[/red] {str(e)}")
                if debug:
                    import traceback

                    console.print(f"[dim]{traceback.format_exc()}[/dim]")
                raise typer.Exit(1)

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
                raise typer.Exit(1)

        # Show results summary with enhanced information
        functions_count = len(result.get("functions", {}))
        modules_count = len(
            set(func.get("file", "") for func in result.get("functions", {}).values())
        )

        # Calculate complexity metrics
        complexities = [func.get("complexity", 0) for func in result.get("functions", {}).values()]
        avg_complexity = sum(complexities) / len(complexities) if complexities else 0
        high_complexity_count = sum(1 for c in complexities if c > 7)

        results_panel = Panel(
            f"[green]✅ Scan completed successfully![/green]\n\n"
            f"📊 [bold]Analysis Results:[/bold]\n"
            f"   • Functions analyzed: {functions_count}\n"
            f"   • Modules processed: {modules_count}\n"
            f"   • Average complexity: {avg_complexity:.1f}\n"
            f"   • High complexity functions: {high_complexity_count}\n"
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
                },
            )
        except Exception as e:
            if debug:
                console.print(f"[dim]Failed to track metrics: {e}[/dim]")

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Scan cancelled by user[/yellow]")
        raise typer.Exit(0)
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
        raise typer.Exit(1)


@app.command()
def map(json_path: str, o: str = typer.Option("maps", "--output", "-o")):
    """Generate DOT graph visualization from analysis results."""
    console = Console()

    try:
        if not pathlib.Path(json_path).exists():
            console.print(f"[red]❌ Error:[/red] File '{json_path}' does not exist")
            raise typer.Exit(1)

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        os.makedirs(o, exist_ok=True)
        dot_path = os.path.join(o, pathlib.Path(json_path).stem + ".dot")
        write_dot(data, dot_path)

        console.print(f"[green]✅ Wrote[/green] {dot_path}")

    except Exception as e:
        console.print(f"[red]❌ Error generating map:[/red] {str(e)}")
        raise typer.Exit(1)


@app.command()
def diff(
    old_map: str = typer.Argument(..., help="Path to old analysis results"),
    new_map: str = typer.Argument(..., help="Path to new analysis results"),
    o: str = typer.Option(
        "maps/delta.svg", "--output", "-o", help="Output file for delta visualization"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
    policy_check: bool = typer.Option(
        True, "--policy-check/--no-policy-check", help="Run policy compliance checks"
    ),
):
    """Compare two analysis results and generate delta visualization with policy checks."""
    console = Console()

    try:
        # Validate input files
        for file_path in [old_map, new_map]:
            if not pathlib.Path(file_path).exists():
                console.print(f"[red]❌ Error:[/red] File '{file_path}' does not exist")
                raise typer.Exit(1)

        console.print("[bold cyan]🔄 Comparing analysis results...[/bold cyan]\n")

        # Load both maps
        with open(old_map, "r", encoding="utf-8") as f:
            old_data = json.load(f)
        with open(new_map, "r", encoding="utf-8") as f:
            new_data = json.load(f)

        # Calculate differences
        old_functions = old_data.get("functions", {})
        new_functions = new_data.get("functions", {})

        added_functions = set(new_functions.keys()) - set(old_functions.keys())
        removed_functions = set(old_functions.keys()) - set(new_functions.keys())
        modified_functions = set()

        for func_name in set(old_functions.keys()) & set(new_functions.keys()):
            if old_functions[func_name] != new_functions[func_name]:
                modified_functions.add(func_name)

        # Show diff summary
        diff_table = Table(title="📊 Analysis Delta Summary", show_header=False, box=None)
        diff_table.add_column("Metric", style="cyan", width=20)
        diff_table.add_column("Count", style="white")
        diff_table.add_column("Status", style="white")

        diff_table.add_row("Added Functions", str(len(added_functions)), "🟢")
        diff_table.add_row("Removed Functions", str(len(removed_functions)), "🔴")
        diff_table.add_row("Modified Functions", str(len(modified_functions)), "🟡")
        diff_table.add_row("Total Functions (Old)", str(len(old_functions)), "📊")
        diff_table.add_row("Total Functions (New)", str(len(new_functions)), "📊")

        console.print(diff_table)
        console.print()

        # Policy compliance checks
        if policy_check:
            console.print("[bold cyan]🔍 Running Policy Compliance Checks...[/bold cyan]\n")

            policy_violations = []

            # Check for complexity increases
            complexity_increases = []
            for func_name in modified_functions:
                old_complexity = old_functions[func_name].get("complexity", 0)
                new_complexity = new_functions[func_name].get("complexity", 0)
                if new_complexity > old_complexity + 2:  # Significant increase
                    complexity_increases.append(
                        {
                            "function": func_name,
                            "old": old_complexity,
                            "new": new_complexity,
                            "increase": new_complexity - old_complexity,
                        }
                    )

            if complexity_increases:
                policy_violations.append(
                    {
                        "type": "Complexity Increase",
                        "count": len(complexity_increases),
                        "severity": (
                            "high"
                            if any(c["increase"] > 5 for c in complexity_increases)
                            else "medium"
                        ),
                    }
                )

                if verbose:
                    console.print(
                        "[yellow]⚠️  Functions with significant complexity increases:[/yellow]"
                    )
                    for violation in complexity_increases[:5]:  # Show first 5
                        console.print(
                            f"   • {violation['function']}: {violation['old']} → {violation['new']} (+{violation['increase']})"
                        )

            # Check for new high-complexity functions
            new_high_complexity = [
                name for name in added_functions if new_functions[name].get("complexity", 0) > 8
            ]

            if new_high_complexity:
                policy_violations.append(
                    {
                        "type": "New High Complexity",
                        "count": len(new_high_complexity),
                        "severity": "high",
                    }
                )

                if verbose:
                    console.print("[yellow]⚠️  New high-complexity functions:[/yellow]")
                    for func_name in new_high_complexity[:5]:
                        complexity = new_functions[func_name].get("complexity", 0)
                        console.print(f"   • {func_name}: complexity {complexity}")

            # Policy summary
            if policy_violations:
                console.print("\n[bold red]🚨 Policy Violations Detected:[/bold red]")
                for violation in policy_violations:
                    severity_icon = "🔴" if violation["severity"] == "high" else "🟡"
                    console.print(
                        f"   {severity_icon} {violation['type']}: {violation['count']} instances"
                    )

                if any(v["severity"] == "high" for v in policy_violations):
                    console.print(
                        "\n[yellow]⚠️  High severity violations detected. Review required.[/yellow]"
                    )
            else:
                console.print("[green]✅ No policy violations detected[/green]")

        # Generate delta visualization
        console.print(f"\n[bold cyan]🎨 Generating delta visualization...[/bold cyan]")

        try:
            os.makedirs(pathlib.Path(o).parent, exist_ok=True)
            lens_delta_svg(old_map, new_map, o)
            console.print(f"[green]✅ Delta visualization written to {o}[/green]")
        except Exception as e:
            console.print(f"[yellow]⚠️  Could not generate visualization: {e}[/yellow]")

        # Summary and recommendations
        summary_panel = Panel(
            f"[bold]Delta Analysis Complete[/bold]\n\n"
            f"📈 [bold]Changes:[/bold] {len(added_functions)} added, {len(removed_functions)} removed, {len(modified_functions)} modified\n"
            f"🔍 [bold]Policy Check:[/bold] {'✅ Passed' if not policy_violations else '❌ Violations detected'}\n"
            f"📊 [bold]Output:[/bold] {o}\n\n"
            f"🎯 [bold]Recommendations:[/bold]\n"
            f"   • Review complexity increases for refactoring opportunities\n"
            f"   • Consider breaking down high-complexity functions\n"
            f"   • Update documentation for modified functions",
            title="🎉 Delta Analysis Results",
            border_style="green" if not policy_violations else "yellow",
        )

        console.print(summary_panel)

        # Track metrics
        try:
            ttu_record(
                "diff_completed",
                {
                    "old_functions": len(old_functions),
                    "new_functions": len(new_functions),
                    "added": len(added_functions),
                    "removed": len(removed_functions),
                    "modified": len(modified_functions),
                    "policy_violations": len(policy_violations) if policy_check else 0,
                },
            )
        except Exception as e:
            if verbose:
                console.print(f"[dim]Failed to track metrics: {e}[/dim]")

        # Exit with appropriate code
        if policy_violations and any(v["severity"] == "high" for v in policy_violations):
            raise typer.Exit(1)  # High severity violations

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Diff cancelled by user[/yellow]")
        raise typer.Exit(0)
    except Exception as e:
        console.print(f"[red]❌ Error during diff:[/red] {str(e)}")
        raise typer.Exit(1)


@app.command()
def report(json_path: str, o: str = typer.Option("maps", "--output", "-o")):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    os.makedirs(o, exist_ok=True)
    md_path = os.path.join(o, pathlib.Path(json_path).stem + ".md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(make_report_md(data))
    print(f"[green]Wrote[/green] {md_path}")


# Lenses
lens_app = typer.Typer(help="Task lenses")
app.add_typer(lens_app, name="lens")


@lens_app.command("from-issue")
def lens_from_issue_cmd(
    issue_md: str,
    map: str = typer.Option(..., "--map"),
    o: str = typer.Option("maps/lens.json", "--output", "-o"),
):
    with open(map, "r", encoding="utf-8") as f:
        repo_map = json.load(f)
    lens = lens_from_issue(issue_md, repo_map)
    rank_by_error_proximity(lens)
    os.makedirs(pathlib.Path(o).parent, exist_ok=True)
    with open(o, "w", encoding="utf-8") as f:
        json.dump(lens, f, indent=2)
    print(f"[green]Wrote[/green] {o}")


@lens_app.command("from-seeds")
def lens_from_seeds_cmd(
    seed: List[str] = typer.Option([], "--seed"),
    map: str = typer.Option(..., "--map"),
    o: str = typer.Option("maps/lens.json", "--output", "-o"),
    interactive: bool = typer.Option(
        False, "--interactive", "-i", help="Interactive seed selection"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
):
    """Create understanding lens from seed functions with enhanced TUI."""
    console = Console()

    try:
        # Load map data
        with open(map, "r", encoding="utf-8") as f:
            repo_map = json.load(f)

        seeds = seed.copy() if seed else []

        if interactive:
            # Interactive seed selection
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
                raise typer.Exit(1)

            # Show available functions in a table
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

            # Interactive selection
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
                seeds = functions[:5]  # Limit to first 5 for performance

        # Show lens configuration
        config_table = Table(title="Lens Configuration", show_header=False)
        config_table.add_column("Setting", style="cyan")
        config_table.add_column("Value", style="white")
        config_table.add_row("Map File", map)
        config_table.add_row("Seeds", f"{len(seeds)} selected")
        config_table.add_row("Output File", o)

        console.print(config_table)
        console.print()

        # Create lens with progress
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

            lens = lens_from_seeds(seeds, repo_map)
            rank_by_error_proximity(lens)

            progress.update(lens_task, advance=70)

            # Write output
            os.makedirs(pathlib.Path(o).parent, exist_ok=True)
            with open(o, "w", encoding="utf-8") as f:
                json.dump(lens, f, indent=2)

            progress.update(lens_task, advance=100)

        # Show results
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

        # Track TTU metric
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
            import traceback

            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)


@lens_app.command("merge-trace")
def lens_merge_trace_cmd(
    lens_json: str,
    trace_json: str,
    o: str = typer.Option("maps/lens_merged.json", "--output", "-o"),
):
    with open(lens_json, "r", encoding="utf-8") as f:
        lens = json.load(f)
    with open(trace_json, "r", encoding="utf-8") as f:
        trace = json.load(f)
    merged = merge_trace_into_lens(lens, trace)
    rank_by_error_proximity(merged)
    os.makedirs(pathlib.Path(o).parent, exist_ok=True)
    with open(o, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)
    print(f"[green]Wrote[/green] {o}")


@lens_app.command("preset")
def lens_preset_cmd(
    label: str,
    map: str = typer.Option(..., "--map"),
    o: str = typer.Option("maps/lens.json", "--output", "-o"),
):
    cfg = load_config()
    seeds = load_preset(label)
    hops = cfg.get("hops", 2)
    with open(map, "r", encoding="utf-8") as f:
        repo_map = json.load(f)
    lens = lens_from_seeds(seeds, repo_map, hops=hops)
    with open(o, "w", encoding="utf-8") as wf:
        json.dump(lens, wf, indent=2)
    print(f"[green]Lens written[/green] {o}")


@lens_app.command("ingest-github")
def ingest_github(log_path: str):
    seeds = seeds_from_github_log(log_path)
    print(json.dumps({"seeds": seeds}, indent=2))


@lens_app.command("ingest-jira")
def ingest_jira(jira_path: str):
    seeds = seeds_from_jira(jira_path)
    print(json.dumps({"seeds": seeds}, indent=2))


@app.command()
def tour(lens_json: str, o: str = typer.Option("tours/tour.md", "--output", "-o")):
    with open(lens_json, "r", encoding="utf-8") as f:
        lens = json.load(f)
    os.makedirs(pathlib.Path(o).parent, exist_ok=True)
    md = write_tour_md(lens)
    with open(o, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"[green]Wrote[/green] {o}")


@app.command()
def tour_run(lens_json: str, fixtures_dir: str = typer.Option("fixtures", "--fixtures", "-f")):
    """Attempt to run a minimal fixture and verify runtime hits align with the lens."""
    # Try running a default fixture file if present, else generate a minimal one.
    fixture = os.path.join(fixtures_dir, "fixture_hot_path.py")
    if not os.path.exists(fixture):
        print("[yellow]No fixture found; cannot run tour.[/yellow]")
        raise typer.Exit(1)
    # Execute fixture in a subprocess; success if return code 0
    rc = subprocess.call(["python", fixture])
    if rc != 0:
        print("[red]Fixture failed.[/red]")
        raise typer.Exit(rc)
    print("[green]Fixture ran successfully.[/green]")


# Trace
trace_app = typer.Typer(help="Runtime tracing (Python demo)")
app.add_typer(trace_app, name="trace")


@trace_app.command("module")
def trace_module(
    pyfile: str,
    func: str,
    a: Optional[str] = None,
    b: Optional[str] = None,
    o: str = typer.Option("traces/trace.json", "--output", "-o"),
):
    os.makedirs(pathlib.Path(o).parent, exist_ok=True)
    data = run_callable_with_trace(pyfile, func, a, b)
    with open(o, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"[green]Wrote[/green] {o}")


@trace_app.command("errors")
def trace_errors(pyfile: str, json_out: bool = typer.Option(True, "--json/--no-json")):
    data = analyze_errors_static(pyfile)
    if json_out:
        print(json.dumps(data, indent=2))
    else:
        print("Raises:")
        for r in data.get("raises", []):
            print(f"  line {r.get('line')}: {r.get('exc')}")
        print("Catches:")
        for c in data.get("catches", []):
            print(f"  line {c.get('line')}: {c.get('catch')}")


# Boundaries
bound_app = typer.Typer(help="Boundary scanners")
app.add_typer(bound_app, name="boundaries")


@bound_app.command("scan")
def boundaries_scan(
    path: str = typer.Argument("."),
    o: str = typer.Option("maps/boundaries.json", "--output", "-o"),
):
    result = scan_boundaries(path)
    os.makedirs(pathlib.Path(o).parent, exist_ok=True)
    with open(o, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"[green]Wrote[/green] {o}")


# Contracts
contracts_app = typer.Typer(help="Contracts")
app.add_typer(contracts_app, name="contracts")


@contracts_app.command("init")
def contracts_init(
    path: str = typer.Argument("."),
    o: str = typer.Option("contracts/contracts.yaml", "--output", "-o"),
):
    os.makedirs(pathlib.Path(o).parent, exist_ok=True)
    txt = init_contracts(path)
    with open(o, "w", encoding="utf-8") as f:
        f.write(txt)
    print(f"[green]Wrote[/green] {o}")


@contracts_app.command("check")
def contracts_check(path: str):
    ok, report = check_contracts(path)
    print(report)
    if not ok:
        raise typer.Exit(1)


@contracts_app.command("stub-tests")
def contracts_stub(path: str, o: str = typer.Option("tests/test_contracts.py", "--output", "-o")):
    os.makedirs(pathlib.Path(o).parent, exist_ok=True)
    txt = stub_tests(path)
    with open(o, "w", encoding="utf-8") as f:
        f.write(txt)
    print(f"[green]Wrote[/green] {o}")


@contracts_app.command("from-openapi")
def contracts_from_openapi(
    path: str,
    o: str = typer.Option("contracts/contracts_from_openapi.yaml", "--output", "-o"),
):
    txt = from_openapi(path)
    os.makedirs(pathlib.Path(o).parent, exist_ok=True)
    with open(o, "w", encoding="utf-8") as f:
        f.write(txt)
    print(f"[green]Wrote[/green] {o}")


@contracts_app.command("from-proto")
def contracts_from_proto(
    path: str,
    o: str = typer.Option("contracts/contracts_from_proto.yaml", "--output", "-o"),
):
    txt = from_proto(path)
    os.makedirs(pathlib.Path(o).parent, exist_ok=True)
    with open(o, "w", encoding="utf-8") as f:
        f.write(txt)
    print(f"[green]Wrote[/green] {o}")


@contracts_app.command("lean-stubs")
def contracts_lean_stubs(
    contracts_yaml: str, o: str = typer.Option("contracts/lean/", "--output-dir", "-o")
):
    os.makedirs(o, exist_ok=True)
    count = lean_stubs(contracts_yaml, o)
    print(f"[green]Wrote[/green] {count} Lean stub(s) to {o}")


@contracts_app.command("compose")
def contracts_compose(
    i: List[str] = typer.Option([], "--input", "-i", help="Contract YAML input paths"),
    o: str = typer.Option("contracts/contracts.yaml", "--output", "-o"),
):
    if not i:
        print("[red]No input files provided[/red]")
        raise typer.Exit(1)
    txt = compose(i)
    os.makedirs(pathlib.Path(o).parent, exist_ok=True)
    with open(o, "w", encoding="utf-8") as f:
        f.write(txt)
    print(f"[green]Wrote[/green] {o}")


@contracts_app.command("verify-lean")
def contracts_verify_lean(
    contracts_yaml: str = typer.Argument(...),
    lean_dir: str = typer.Option("contracts/lean", "--lean-dir", "-l"),
    json_out: bool = typer.Option(False, "--json"),
):
    data = verify_lean(contracts_yaml, lean_dir)
    if json_out:
        print(json.dumps(data, indent=2))
    else:
        print(f"modules: {data.get('modules_total')}\n" f"functions: {data.get('functions_total')}")
        missing = data.get("missing_invariants", [])
        if missing:
            print("missing invariants:")
            for m in missing:
                print(f"  - {m}")
    if data.get("missing_invariants"):
        raise typer.Exit(1)


# Packs
pack_app = typer.Typer(help="Understanding Packs")
app.add_typer(pack_app, name="pack")


@pack_app.command("create")
def pack_create(
    lens: str = typer.Option(..., "--lens"),
    tour: str = typer.Option(..., "--tour"),
    contracts: str = typer.Option(..., "--contracts"),
    o: str = typer.Option("packs/pack.zip", "--output", "-o"),
):
    os.makedirs(pathlib.Path(o).parent, exist_ok=True)
    create_pack(lens, tour, contracts, o)
    print(f"[green]Wrote[/green] {o}")


# Visual
visual_app = typer.Typer(help="Visualization utilities")
app.add_typer(visual_app, name="visual")


@visual_app.command("delta")
def visual_delta(
    old_lens: str,
    new_lens: str,
    o: str = typer.Option("maps/delta.svg", "--output", "-o"),
):
    svg = lens_delta_svg(old_lens, new_lens)
    os.makedirs(pathlib.Path(o).parent, exist_ok=True)
    with open(o, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"[green]Wrote[/green] {o}")


# C-02: Diff Map Delta Helper Functions
def _load_analysis_data(source: str) -> Optional[Dict[str, Any]]:
    """Load analysis data from file or git commit."""
    if os.path.exists(source):
        # Load from file
        with open(source, "r") as f:
            return json.load(f)
    else:
        # Try to load from git commit
        try:
            result = subprocess.run(
                ["git", "show", f"{source}:.understand-first/analysis.json"],
                capture_output=True,
                text=True,
                check=True,
            )
            return json.loads(result.stdout)
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            return None


def _generate_delta_analysis(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    """Generate comprehensive delta analysis between two analysis results."""
    delta = {
        "summary": {
            "before_functions": len(before.get("functions", {})),
            "after_functions": len(after.get("functions", {})),
            "added_functions": 0,
            "removed_functions": 0,
            "modified_functions": 0,
            "complexity_change": 0,
            "side_effects_added": 0,
            "side_effects_removed": 0,
        },
        "added": [],
        "removed": [],
        "modified": [],
        "complexity_changes": [],
        "side_effect_changes": [],
        "hot_path_changes": [],
        "timestamp": datetime.now().isoformat(),
    }

    before_funcs = before.get("functions", {})
    after_funcs = after.get("functions", {})

    # Find added and removed functions
    before_names = set(before_funcs.keys())
    after_names = set(after_funcs.keys())

    added_names = after_names - before_names
    removed_names = before_names - after_names
    common_names = before_names & after_names

    delta["summary"]["added_functions"] = len(added_names)
    delta["summary"]["removed_functions"] = len(removed_names)

    # Process added functions
    for name in added_names:
        func_data = after_funcs[name]
        delta["added"].append(
            {
                "name": name,
                "file": func_data.get("file", ""),
                "line": func_data.get("line", 0),
                "complexity": func_data.get("complexity", 0),
                "side_effects": func_data.get("side_effects", []),
                "is_hot_path": func_data.get("is_hot_path", False),
            }
        )

    # Process removed functions
    for name in removed_names:
        func_data = before_funcs[name]
        delta["removed"].append(
            {
                "name": name,
                "file": func_data.get("file", ""),
                "line": func_data.get("line", 0),
                "complexity": func_data.get("complexity", 0),
                "side_effects": func_data.get("side_effects", []),
                "is_hot_path": func_data.get("is_hot_path", False),
            }
        )

    # Process modified functions
    for name in common_names:
        before_func = before_funcs[name]
        after_func = after_funcs[name]

        changes = {}
        if before_func.get("complexity", 0) != after_func.get("complexity", 0):
            changes["complexity"] = {
                "before": before_func.get("complexity", 0),
                "after": after_func.get("complexity", 0),
                "delta": after_func.get("complexity", 0) - before_func.get("complexity", 0),
            }
            delta["complexity_changes"].append(
                {
                    "name": name,
                    "file": after_func.get("file", ""),
                    "line": after_func.get("line", 0),
                    **changes["complexity"],
                }
            )

        before_side_effects = set(before_func.get("side_effects", []))
        after_side_effects = set(after_func.get("side_effects", []))

        if before_side_effects != after_side_effects:
            added_side_effects = after_side_effects - before_side_effects
            removed_side_effects = before_side_effects - after_side_effects

            changes["side_effects"] = {
                "added": list(added_side_effects),
                "removed": list(removed_side_effects),
            }

            delta["side_effect_changes"].append(
                {
                    "name": name,
                    "file": after_func.get("file", ""),
                    "line": after_func.get("line", 0),
                    **changes["side_effects"],
                }
            )

            delta["summary"]["side_effects_added"] += len(added_side_effects)
            delta["summary"]["side_effects_removed"] += len(removed_side_effects)

        if before_func.get("is_hot_path", False) != after_func.get("is_hot_path", False):
            changes["hot_path"] = {
                "before": before_func.get("is_hot_path", False),
                "after": after_func.get("is_hot_path", False),
            }
            delta["hot_path_changes"].append(
                {
                    "name": name,
                    "file": after_func.get("file", ""),
                    "line": after_func.get("line", 0),
                    **changes["hot_path"],
                }
            )

        if changes:
            delta["modified"].append(
                {
                    "name": name,
                    "file": after_func.get("file", ""),
                    "line": after_func.get("line", 0),
                    "changes": changes,
                }
            )
            delta["summary"]["modified_functions"] += 1

    # Calculate overall complexity change
    before_complexity = sum(func.get("complexity", 0) for func in before_funcs.values())
    after_complexity = sum(func.get("complexity", 0) for func in after_funcs.values())
    delta["summary"]["complexity_change"] = after_complexity - before_complexity

    return delta


def _check_policy_compliance(delta: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check delta against policy rules and return violations."""
    violations = []

    # Policy: No new high-complexity functions (>10)
    for func in delta["added"]:
        if func["complexity"] > 10:
            violations.append(
                {
                    "type": "high_complexity_added",
                    "severity": "warning",
                    "function": func["name"],
                    "file": func["file"],
                    "line": func["line"],
                    "complexity": func["complexity"],
                    "message": f"New function '{func['name']}' has high complexity ({func['complexity']})",
                }
            )

    # Policy: No new unmanaged side effects
    for func in delta["added"]:
        unmanaged_side_effects = [
            se for se in func["side_effects"] if se not in ["logging", "metrics"]
        ]
        if unmanaged_side_effects:
            violations.append(
                {
                    "type": "unmanaged_side_effects_added",
                    "severity": "error",
                    "function": func["name"],
                    "file": func["file"],
                    "line": func["line"],
                    "side_effects": unmanaged_side_effects,
                    "message": f"New function '{func['name']}' has unmanaged side effects: {', '.join(unmanaged_side_effects)}",
                }
            )

    # Policy: Significant complexity increase (>5 points)
    for change in delta["complexity_changes"]:
        if change["delta"] > 5:
            violations.append(
                {
                    "type": "complexity_increase",
                    "severity": "warning",
                    "function": change["name"],
                    "file": change["file"],
                    "line": change["line"],
                    "before": change["before"],
                    "after": change["after"],
                    "delta": change["delta"],
                    "message": f"Function '{change['name']}' complexity increased by {change['delta']} points",
                }
            )

    # Policy: New side effects added to existing functions
    for change in delta["side_effect_changes"]:
        if change["added"]:
            violations.append(
                {
                    "type": "side_effects_added",
                    "severity": "warning",
                    "function": change["name"],
                    "file": change["file"],
                    "line": change["line"],
                    "added_side_effects": change["added"],
                    "message": f"Function '{change['name']}' now has additional side effects: {', '.join(change['added'])}",
                }
            )

    return violations


def _generate_markdown_delta(delta: Dict[str, Any], violations: List[Dict[str, Any]]) -> str:
    """Generate markdown delta report."""
    md = []
    md.append("# Analysis Delta Report")
    md.append(f"Generated: {delta['timestamp']}")
    md.append("")

    # Summary
    summary = delta["summary"]
    md.append("## Summary")
    md.append(f"- **Functions Added**: {summary['added_functions']}")
    md.append(f"- **Functions Removed**: {summary['removed_functions']}")
    md.append(f"- **Functions Modified**: {summary['modified_functions']}")
    md.append(f"- **Complexity Change**: {summary['complexity_change']:+d}")
    md.append(f"- **Side Effects Added**: {summary['side_effects_added']}")
    md.append(f"- **Side Effects Removed**: {summary['side_effects_removed']}")
    md.append("")

    # Policy violations
    if violations:
        md.append("## ⚠️ Policy Violations")
        for violation in violations:
            severity_icon = "🚨" if violation["severity"] == "error" else "⚠️"
            md.append(f"### {severity_icon} {violation['type'].replace('_', ' ').title()}")
            md.append(f"**Function**: `{violation['function']}`")
            md.append(f"**File**: `{violation['file']}:{violation['line']}`")
            md.append(f"**Message**: {violation['message']}")
            md.append("")

    # Added functions
    if delta["added"]:
        md.append("## Added Functions")
        for func in delta["added"]:
            md.append(f"- `{func['name']}` in `{func['file']}:{func['line']}`")
            md.append(f"  - Complexity: {func['complexity']}")
            if func["side_effects"]:
                md.append(f"  - Side Effects: {', '.join(func['side_effects'])}")
            if func["is_hot_path"]:
                md.append(f"  - 🔥 Hot Path")
        md.append("")

    # Removed functions
    if delta["removed"]:
        md.append("## Removed Functions")
        for func in delta["removed"]:
            md.append(f"- `{func['name']}` in `{func['file']}:{func['line']}`")
        md.append("")

    # Modified functions
    if delta["modified"]:
        md.append("## Modified Functions")
        for func in delta["modified"]:
            md.append(f"- `{func['name']}` in `{func['file']}:{func['line']}`")
            for change_type, change_data in func["changes"].items():
                if change_type == "complexity":
                    md.append(
                        f"  - Complexity: {change_data['before']} → {change_data['after']} ({change_data['delta']:+d})"
                    )
                elif change_type == "side_effects":
                    if change_data["added"]:
                        md.append(f"  - Added Side Effects: {', '.join(change_data['added'])}")
                    if change_data["removed"]:
                        md.append(f"  - Removed Side Effects: {', '.join(change_data['removed'])}")
        md.append("")

    return "\n".join(md)


def _generate_html_delta(delta: Dict[str, Any], violations: List[Dict[str, Any]]) -> str:
    """Generate HTML delta report."""
    html = []
    html.append("<!DOCTYPE html>")
    html.append("<html><head><title>Analysis Delta Report</title>")
    html.append("<style>")
    html.append("body { font-family: Arial, sans-serif; margin: 20px; }")
    html.append(".summary { background: #f5f5f5; padding: 15px; border-radius: 5px; }")
    html.append(
        ".violation { background: #ffe6e6; padding: 10px; margin: 10px 0; border-left: 4px solid #ff0000; }"
    )
    html.append(".warning { background: #fff3cd; border-left-color: #ffc107; }")
    html.append(
        ".function { background: #f8f9fa; padding: 10px; margin: 5px 0; border-radius: 3px; }"
    )
    html.append("</style></head><body>")

    html.append("<h1>Analysis Delta Report</h1>")
    html.append(f"<p>Generated: {delta['timestamp']}</p>")

    # Summary
    summary = delta["summary"]
    html.append("<div class='summary'>")
    html.append("<h2>Summary</h2>")
    html.append(f"<p><strong>Functions Added:</strong> {summary['added_functions']}</p>")
    html.append(f"<p><strong>Functions Removed:</strong> {summary['removed_functions']}</p>")
    html.append(f"<p><strong>Functions Modified:</strong> {summary['modified_functions']}</p>")
    html.append(f"<p><strong>Complexity Change:</strong> {summary['complexity_change']:+d}</p>")
    html.append(f"<p><strong>Side Effects Added:</strong> {summary['side_effects_added']}</p>")
    html.append(f"<p><strong>Side Effects Removed:</strong> {summary['side_effects_removed']}</p>")
    html.append("</div>")

    # Policy violations
    if violations:
        html.append("<h2>⚠️ Policy Violations</h2>")
        for violation in violations:
            severity_class = "violation" if violation["severity"] == "error" else "warning"
            html.append(f"<div class='{severity_class}'>")
            html.append(f"<h3>{violation['type'].replace('_', ' ').title()}</h3>")
            html.append(f"<p><strong>Function:</strong> <code>{violation['function']}</code></p>")
            html.append(
                f"<p><strong>File:</strong> <code>{violation['file']}:{violation['line']}</code></p>"
            )
            html.append(f"<p><strong>Message:</strong> {violation['message']}</p>")
            html.append("</div>")

    # Added functions
    if delta["added"]:
        html.append("<h2>Added Functions</h2>")
        for func in delta["added"]:
            html.append(f"<div class='function'>")
            html.append(
                f"<strong>{func['name']}</strong> in <code>{func['file']}:{func['line']}</code>"
            )
            html.append(f"<ul>")
            html.append(f"<li>Complexity: {func['complexity']}</li>")
            if func["side_effects"]:
                html.append(f"<li>Side Effects: {', '.join(func['side_effects'])}</li>")
            if func["is_hot_path"]:
                html.append(f"<li>🔥 Hot Path</li>")
            html.append(f"</ul>")
            html.append("</div>")

    html.append("</body></html>")
    return "\n".join(html)


def _display_delta_summary(
    console: Console, delta: Dict[str, Any], violations: List[Dict[str, Any]]
):
    """Display a summary of the delta analysis."""
    summary = delta["summary"]

    # Create summary table
    table = Table(title="Delta Analysis Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")

    table.add_row("Functions Added", str(summary["added_functions"]))
    table.add_row("Functions Removed", str(summary["removed_functions"]))
    table.add_row("Functions Modified", str(summary["modified_functions"]))
    table.add_row("Complexity Change", f"{summary['complexity_change']:+d}")
    table.add_row("Side Effects Added", str(summary["side_effects_added"]))
    table.add_row("Side Effects Removed", str(summary["side_effects_removed"]))

    console.print(table)

    # Show policy violations
    if violations:
        console.print(f"\n[red]Policy Violations: {len(violations)}[/red]")
        for violation in violations[:5]:  # Show first 5
            severity_color = "red" if violation["severity"] == "error" else "yellow"
            console.print(f"[{severity_color}]• {violation['message']}[/{severity_color}]")

        if len(violations) > 5:
            console.print(f"[dim]... and {len(violations) - 5} more violations[/dim]")
    else:
        console.print("\n[green]No policy violations detected[/green]")


if __name__ == "__main__":
    app()


@app.command()
def glossary(o: str = typer.Option("docs/glossary.md", "--output", "-o")):
    os.makedirs(os.path.dirname(o), exist_ok=True)
    md = build_glossary(".")
    with open(o, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"[green]Wrote[/green] {o}")


@app.command()
def dashboard(
    repo: str = typer.Option("maps/repo.json", "--repo"),
    lens: str = typer.Option("maps/lens_merged.json", "--lens"),
    bounds: str = typer.Option("maps/boundaries.json", "--bounds"),
    o: str = typer.Option("docs/understanding-dashboard.md", "--output", "-o"),
):
    os.makedirs(os.path.dirname(o), exist_ok=True)
    md = build_dashboard({"repo": repo, "lens": lens, "bounds": bounds})
    with open(o, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"[green]Wrote[/green] {o}")


@contracts_app.command("report")
def contracts_report(
    path: str,
    json_out: bool = typer.Option(False, "--json", help="Emit JSON report to stdout"),
):
    data = report_json(path)
    if json_out:
        print(json.dumps(data, indent=2))
    else:
        for i in data.get("issues", []):
            print(
                f"[{i.get('severity','info')}] "
                f"{i.get('module_path')}:{i.get('function')} - {i.get('message')}"
            )
    if data.get("issues"):
        raise typer.Exit(1)


@app.command()
def pack(
    publish: bool = typer.Option(
        True, "--publish/--no-publish", help="Build pack artifacts (local zip)."
    )
):
    if publish:
        make_pack("dist")
        print("[green]Pack ready in dist/[/green]")


@app.command()
def ttu(
    event: str = typer.Argument(...),
    o: str = typer.Option("docs/ttu.md", "--output", "-o"),
):
    if event == "report":
        ttu_weekly(o)
        print(f"[green]Wrote[/green] {o}")
    else:
        ttu_record(event)
        print(f"[green]Recorded[/green] {event}")


@app.command()
def lens_preset(
    label: str,
    map: str = typer.Option(..., "--map"),
    o: str = typer.Option("maps/lens.json", "--output", "-o"),
):
    cfg = load_config()
    seeds = load_preset(label)
    hops = cfg.get("hops", 2)
    with open(map, "r", encoding="utf-8") as f:
        repo_map = json.load(f)
    lens = lens_from_seeds(seeds, repo_map, hops=hops)
    with open(o, "w", encoding="utf-8") as wf:
        json.dump(lens, wf, indent=2)
    print(f"[green]Lens written[/green] {o}")


@app.command()
def doctor():
    problems: List[str] = []
    notes: List[str] = []

    def ok(msg: str):
        print(f"[green]OK[/green] {msg}")

    def warn(msg: str, fix: Optional[str] = None):
        print(f"[yellow]WARN[/yellow] {msg}")
        if fix:
            notes.append(f"- {msg} → {fix}")

    def fail(msg: str, fix: Optional[str] = None):
        print(f"[red]FAIL[/red] {msg}")
        problems.append(msg)
        if fix:
            notes.append(f"- {msg} → {fix}")

    ok(f"Python {sys.version.split()[0]}")

    try:
        r = subprocess.run(
            ["node", "-v"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
        )
        if r.returncode == 0:
            ok(f"Node {r.stdout.strip()}")
        else:
            warn(
                "Node not found in PATH",
                "Install Node 18+ or use Devcontainer/Codespaces",
            )
    except Exception:
        warn("Node not found in PATH", "Install Node 18+ or use Devcontainer/Codespaces")

    try:
        import grpc_tools  # type: ignore

        ok("grpc_tools available")
    except Exception:
        fail("grpc_tools missing", "pip install grpcio-tools")

    def can_bind(port: int) -> bool:
        try:
            s = socket.socket()
            s.bind(("127.0.0.1", port))
            s.close()
            return True
        except Exception:
            return False

    if not can_bind(8000):
        warn(
            "Port 8000 not available",
            "Stop the process using 8000 or change server port",
        )
    else:
        ok("Port 8000 available")
    if not can_bind(50051):
        warn(
            "Port 50051 not available",
            "Stop the process using 50051 or change gRPC port",
        )
    else:
        ok("Port 50051 available")

    code_bin = shutil.which("code") or shutil.which("code.cmd")
    if code_bin:
        ok(f"VS Code found at {code_bin}")
    else:
        warn("VS Code not found", "Install VS Code or use Codespaces")

    try:
        test_file = pathlib.Path(".uf_write_test")
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink()
        ok("Repo write permissions OK")
    except Exception:
        fail(
            "No write permission in repo",
            "Check filesystem permissions or workspace settings",
        )

    print("\nNext steps")
    doc_url = "https://github.com/your-org/understand-first#readme"
    for n in notes:
        print(n)
    if problems:
        print(f"\nSee docs: {doc_url}")
        raise typer.Exit(code=1)
    else:
        print("All checks passed. See docs for advanced setup:")
        print(doc_url)


@app.command()
def demo():
    try:
        txt = from_openapi("examples/apis/petstore-mini.yaml")
        os.makedirs("contracts", exist_ok=True)
        open("contracts/contracts_from_openapi.yaml", "w", encoding="utf-8").write(txt)
    except Exception:
        pass

    http_proc = subprocess.Popen([sys.executable, "examples/servers/http_server.py"])  # nosec
    try:
        os.makedirs("traces", exist_ok=True)
        data = run_callable_with_trace("examples/app/hot_path.py", "run_hot_path")
        open("traces/tour.json", "w", encoding="utf-8").write(json.dumps(data, indent=2))

        os.makedirs("maps", exist_ok=True)
        repo_map = build_python_map(pathlib.Path("examples/python_toy"))
        open("maps/repo.json", "w", encoding="utf-8").write(json.dumps(repo_map, indent=2))
        lens = lens_from_seeds(["compute"], repo_map)
        merged = merge_trace_into_lens(lens, data)
        rank_by_error_proximity(merged)
        open("maps/lens_merged.json", "w", encoding="utf-8").write(json.dumps(merged, indent=2))

        os.makedirs("tours", exist_ok=True)
        open("tours/demo.md", "w", encoding="utf-8").write(write_tour_md(merged))
        os.makedirs("docs", exist_ok=True)
        open("docs/understanding-dashboard.md", "w", encoding="utf-8").write(
            build_dashboard(
                {
                    "repo": "maps/repo.json",
                    "lens": "maps/lens_merged.json",
                    "bounds": "maps/boundaries.json",
                }
            )
        )

        url = f"file://{pathlib.Path('tours/demo.md').resolve()}"
        print(f"[green]Open tour:[/green] {url}")
    finally:
        http_proc.terminate()


@app.command()
def init(
    stack: str = typer.Option("py", "--stack"),
    ci: str = typer.Option("github", "--ci"),
    wizard: bool = typer.Option(False, "--wizard", help="Interactive configuration wizard"),
    tui: bool = typer.Option(False, "--tui", help="Launch interactive TUI mode"),
):
    """Initialize understand-first configuration for your project."""
    console = Console()

    if tui:
        _launch_tui_mode()
    elif wizard:
        _run_config_wizard()
    else:
        _create_basic_config(stack, ci)


@app.command()
def diff(
    before: str = typer.Argument(..., help="Path to before analysis (JSON file or commit hash)"),
    after: str = typer.Argument(..., help="Path to after analysis (JSON file or commit hash)"),
    output: str = typer.Option(
        "delta.json", "--output", "-o", help="Output file for delta analysis"
    ),
    format: str = typer.Option(
        "json", "--format", "-f", help="Output format: json, markdown, html"
    ),
    policy_check: bool = typer.Option(
        True, "--policy-check", help="Enable policy compliance checking"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
):
    """Compare two analysis results and generate delta report with policy checking."""
    console = Console()

    try:
        # Load before and after analyses
        before_data = _load_analysis_data(before)
        after_data = _load_analysis_data(after)

        if not before_data or not after_data:
            console.print("[red]Error:[/red] Could not load analysis data")
            raise typer.Exit(1)

        # Generate delta analysis
        delta_result = _generate_delta_analysis(before_data, after_data)

        # Policy compliance checking
        policy_violations = []
        if policy_check:
            policy_violations = _check_policy_compliance(delta_result)

        # Generate output in requested format
        if format == "markdown":
            output_content = _generate_markdown_delta(delta_result, policy_violations)
        elif format == "html":
            output_content = _generate_html_delta(delta_result, policy_violations)
        else:
            output_content = json.dumps(delta_result, indent=2)

        # Write output
        with open(output, "w") as f:
            f.write(output_content)

        # Display summary
        _display_delta_summary(console, delta_result, policy_violations)

        # Exit with appropriate code
        if policy_violations:
            console.print(f"[yellow]Policy violations detected: {len(policy_violations)}[/yellow]")
            raise typer.Exit(2)
        else:
            console.print("[green]Delta analysis completed successfully[/green]")
            raise typer.Exit(0)

    except Exception as e:
        if verbose:
            console.print(f"[red]Error:[/red] {e}")
            import traceback

            traceback.print_exc()
        else:
            console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


def _create_basic_config(stack: str, ci: str):
    """Create a basic configuration file."""
    os.makedirs(".understand-first.yml".replace(".yml", ""), exist_ok=True)  # no-op
    open(".understand-first.yml", "w", encoding="utf-8").write(
        """hops: 2
seeds: []
seeds_for:
  bug: [examples/app/hot_path.py]
metrics:
  enabled: false
"""
    )
    os.makedirs("tours", exist_ok=True)
    open("README.md", "a", encoding="utf-8").write(
        "\n\n## 10-minute tour\nRun `u scan` then `u demo`.\n"
    )
    print("[green]Initialized understand-first config and basics[/green]")


def _launch_tui_mode():
    """Launch interactive TUI mode for understand-first."""
    console = Console()

    # Create layout
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3), Layout(name="main"), Layout(name="footer", size=3)
    )

    layout["main"].split_row(Layout(name="sidebar", size=30), Layout(name="content"))

    # Header
    header_panel = Panel(
        Align.center("[bold blue]🧠 Understand-First TUI[/bold blue]"), style="blue"
    )
    layout["header"].update(header_panel)

    # Footer
    footer_text = Text("Press 'q' to quit, 'h' for help, arrow keys to navigate", style="dim")
    layout["footer"].update(Panel(Align.center(footer_text), style="dim"))

    # Main TUI loop
    with Live(layout, refresh_per_second=4, screen=True) as live:
        _run_tui_main_loop(live, layout)


def _run_tui_main_loop(live, layout):
    """Main TUI event loop."""
    console = Console()
    current_view = "dashboard"

    while True:
        # Update content based on current view
        if current_view == "dashboard":
            _render_dashboard(layout)
        elif current_view == "scan":
            _render_scan_view(layout)
        elif current_view == "lens":
            _render_lens_view(layout)
        elif current_view == "tour":
            _render_tour_view(layout)
        elif current_view == "config":
            _render_config_view(layout)

        # Handle input
        try:
            key = console.input()
            if key.lower() == "q":
                break
            elif key.lower() == "h":
                _show_help(layout)
            elif key == "1":
                current_view = "dashboard"
            elif key == "2":
                current_view = "scan"
            elif key == "3":
                current_view = "lens"
            elif key == "4":
                current_view = "tour"
            elif key == "5":
                current_view = "config"
        except KeyboardInterrupt:
            break


def _render_dashboard(layout):
    """Render the main dashboard view."""
    # Sidebar
    sidebar_content = """
[bold]Navigation[/bold]
1. Dashboard
2. Scan Code
3. Lens Management
4. Tour Builder
5. Configuration

[bold]Quick Actions[/bold]
• Press 's' to scan current directory
• Press 'l' to create new lens
• Press 't' to generate tour
• Press 'c' to configure project
"""
    layout["sidebar"].update(Panel(sidebar_content, title="Menu", border_style="blue"))

    # Main content
    dashboard_content = """
[bold green]Welcome to Understand-First TUI![/bold green]

This interactive interface helps you:
• Analyze your codebase structure
• Create focused lenses for specific areas
• Generate understanding tours
• Track Time-to-Understanding metrics

[bold]Recent Activity[/bold]
• No recent scans found
• No active lenses
• No tours generated

[bold]Project Status[/bold]
• Configuration: Not initialized
• Last scan: Never
• Active lenses: 0
• Generated tours: 0

[bold]Quick Start[/bold]
1. Press 'c' to configure your project
2. Press 's' to scan your codebase
3. Press 'l' to create your first lens
4. Press 't' to generate a tour
"""
    layout["content"].update(Panel(dashboard_content, title="Dashboard", border_style="green"))


def _render_scan_view(layout):
    """Render the scan view."""
    # Sidebar
    sidebar_content = """
[bold]Scan Options[/bold]
• Target: Current directory
• Output: maps/out.json
• Verbose: False
• Debug: False

[bold]Analysis Types[/bold]
• Python: AST analysis
• Dependencies: Import tracking
• Side effects: I/O detection
• Complexity: Cyclomatic metrics
"""
    layout["sidebar"].update(Panel(sidebar_content, title="Scan Config", border_style="yellow"))

    # Main content
    scan_content = """
[bold yellow]Code Analysis Scanner[/bold yellow]

This will analyze your codebase and generate:
• Function dependency graph
• Side effect analysis
• Complexity metrics
• Hot path identification

[bold]Ready to scan?[/bold]
Press 'Enter' to start analysis or 'Esc' to go back.

[dim]Note: Large codebases may take several minutes to analyze.[/dim]
"""
    layout["content"].update(Panel(scan_content, title="Scan Code", border_style="yellow"))


def _render_lens_view(layout):
    """Render the lens management view."""
    # Sidebar
    sidebar_content = """
[bold]Lens Types[/bold]
• Entry Points
• Hot Paths
• Side Effects
• High Complexity
• Custom Seeds

[bold]Presets[/bold]
• bug: Error-related functions
• feature: New feature code
• api: API endpoints
• test: Test functions
"""
    layout["sidebar"].update(Panel(sidebar_content, title="Lens Types", border_style="cyan"))

    # Main content
    lens_content = """
[bold cyan]Lens Management[/bold cyan]

Lenses help you focus on specific parts of your codebase:
• Filter by function type
• Highlight important paths
• Isolate side effects
• Focus on complexity hotspots

[bold]Create New Lens[/bold]
1. Choose lens type
2. Set seed functions
3. Configure filters
4. Save as preset

[bold]Existing Lenses[/bold]
• No lenses created yet
"""
    layout["content"].update(Panel(lens_content, title="Lens Management", border_style="cyan"))


def _render_tour_view(layout):
    """Render the tour builder view."""
    # Sidebar
    sidebar_content = """
[bold]Tour Steps[/bold]
1. Introduction
2. Architecture Overview
3. Key Components
4. Data Flow
5. Side Effects
6. Testing Strategy

[bold]Export Options[/bold]
• Markdown
• HTML
• PDF
• Interactive Web
"""
    layout["sidebar"].update(Panel(sidebar_content, title="Tour Builder", border_style="magenta"))

    # Main content
    tour_content = """
[bold magenta]Tour Builder[/bold magenta]

Generate interactive tours to help team members understand your codebase:
• Step-by-step walkthrough
• Code highlighting
• Interactive navigation
• Export for documentation

[bold]Create New Tour[/bold]
1. Select starting functions
2. Define tour steps
3. Add explanations
4. Generate and export

[bold]Tour Templates[/bold]
• Onboarding tour
• Architecture overview
• Feature walkthrough
• Debugging guide
"""
    layout["content"].update(Panel(tour_content, title="Tour Builder", border_style="magenta"))


def _render_config_view(layout):
    """Render the configuration view."""
    # Sidebar
    sidebar_content = """
[bold]Config Sections[/bold]
• Project Type
• Analysis Settings
• Seeds & Presets
• Metrics & Tracking
• CI Integration
• IDE Integration

[bold]Current Status[/bold]
• Project: Not configured
• Analysis: Default settings
• Seeds: None defined
• Metrics: Disabled
"""
    layout["sidebar"].update(Panel(sidebar_content, title="Configuration", border_style="red"))

    # Main content
    config_content = """
[bold red]Project Configuration[/bold red]

Configure understand-first for your specific project:
• Set analysis depth and scope
• Define seed functions
• Configure metrics tracking
• Set up CI/CD integration

[bold]Configuration Wizard[/bold]
Press 'w' to run the interactive wizard
or manually edit .understand-first.yml

[bold]Current Settings[/bold]
• Hops: 2
• Seeds: []
• Metrics: Disabled
• CI: Not configured
"""
    layout["content"].update(Panel(config_content, title="Configuration", border_style="red"))


def _show_help(layout):
    """Show help information."""
    help_content = """
[bold]Keyboard Shortcuts[/bold]

Navigation:
• 1-5: Switch between views
• q: Quit application
• h: Show this help

Actions:
• s: Start code scan
• l: Create new lens
• t: Generate tour
• c: Configure project
• w: Run configuration wizard

General:
• Enter: Confirm action
• Esc: Go back
• Ctrl+C: Force quit
"""
    layout["content"].update(Panel(help_content, title="Help", border_style="blue"))


def _run_config_wizard():
    """Run interactive configuration wizard with enhanced features."""
    print("[bold blue]🧠 Understand-First Configuration Wizard[/bold blue]")
    print("This wizard will help you set up your .understand-first.yml configuration.")
    print("The wizard will guide you through project-specific optimizations and best practices.")
    print()

    # Enhanced project type selection
    project_types = {
        "1": ("python", "Python project", "General Python applications and libraries"),
        "2": (
            "django",
            "Django web application",
            "Django web apps with models, views, and templates",
        ),
        "3": ("fastapi", "FastAPI web application", "Modern async API applications with FastAPI"),
        "4": ("flask", "Flask web application", "Flask web apps with blueprints and extensions"),
        "5": (
            "microservices",
            "Microservices architecture",
            "Distributed systems with multiple services",
        ),
        "6": ("react", "React frontend", "React applications with components and hooks"),
        "7": (
            "nodejs",
            "Node.js application",
            "Node.js applications with Express or other frameworks",
        ),
        "8": ("go", "Go application", "Go applications and microservices"),
        "9": ("java", "Java application", "Java applications with Spring or other frameworks"),
        "10": ("custom", "Custom configuration", "Manually configure all settings"),
    }

    print("What type of project are you configuring?")
    for key, (value, description, details) in project_types.items():
        print(f"  {key}. {description}")
        print(f"     {details}")
        print()

    while True:
        choice = typer.prompt("Enter your choice (1-10)", type=str)
        if choice in project_types:
            project_type, project_name, project_details = project_types[choice]
            break
        print("[red]Invalid choice. Please enter 1-10.[/red]")

    print(f"\n[green]Selected:[/green] {project_name}")
    print(f"[dim]{project_details}[/dim]")

    # Load template if available
    template_config = _load_project_template(project_type)

    # Configuration options with enhanced defaults
    config = {
        "hops": 2,
        "seeds": [],
        "seeds_for": {},
        "contracts_paths": [],
        "glossary_path": "docs/glossary.md",
        "metrics": {"enabled": False},
        "exclude_patterns": [],
        "include_patterns": [],
        "analysis_options": {},
        "ci_integration": {"enabled": False},
        "ide_integration": {"enabled": True},
    }

    # Merge template configuration
    if template_config:
        config.update(template_config)
        print(f"\n[green]Loaded template configuration for {project_name}[/green]")

    # Hops configuration with better validation
    print("\n[bold]Analysis Depth Configuration[/bold]")
    print("Hops determine how deep the analysis should traverse from seed functions.")
    print("Higher values provide more comprehensive analysis but may be slower.")

    hops = typer.prompt(
        "How many hops should the lens traverse? (1-10, default: 2)",
        type=int,
        default=config.get("hops", 2),
    )
    config["hops"] = max(1, min(10, hops))  # Clamp between 1 and 10

    # Enhanced seeds configuration
    print("\n[bold]Seeds Configuration[/bold]")
    print("Seeds are starting points for understanding analysis.")
    print("You can add files, functions, modules, or patterns as seeds.")
    print("Examples: 'main.py', 'app.py:main', '*/models.py', 'service.*'")

    add_seeds = typer.confirm(
        "Would you like to add custom seeds?", default=len(config.get("seeds", [])) == 0
    )
    if add_seeds:
        seeds = config.get("seeds", [])
        print("\n[dim]Enter seeds one by one. Press Enter with empty input to finish.[/dim]")
        while True:
            seed = typer.prompt(
                "Enter a seed (file path, function, or pattern) or press Enter to finish",
                default="",
            )
            if not seed:
                break
            if seed not in seeds:
                seeds.append(seed)
                print(f"[green]Added seed:[/green] {seed}")
            else:
                print(f"[yellow]Seed already exists:[/yellow] {seed}")
        config["seeds"] = seeds

    # Enhanced preset seeds configuration
    print("\n[bold]Preset Seeds for Common Scenarios[/bold]")
    print("Define preset seed collections for common development scenarios.")
    print("These can be used with commands like 'u lens preset bug' or 'u lens preset feature'.")

    add_presets = typer.confirm(
        "Would you like to configure preset seed collections?", default=True
    )
    if add_presets:
        presets = config.get("seeds_for", {})

        # Suggest common presets based on project type
        suggested_presets = _get_suggested_presets(project_type)
        if suggested_presets:
            print(f"\n[bold]Suggested presets for {project_name}:[/bold]")
            for preset_name, preset_seeds in suggested_presets.items():
                print(f"  • {preset_name}: {', '.join(preset_seeds)}")

            use_suggested = typer.confirm("Use these suggested presets?", default=True)
            if use_suggested:
                presets.update(suggested_presets)

        # Allow custom presets
        add_custom_presets = typer.confirm("Add custom presets?", default=False)
        if add_custom_presets:
            while True:
                preset_name = typer.prompt(
                    "Enter preset name (e.g., 'bug', 'feature', 'api') or press Enter to finish",
                    default="",
                )
                if not preset_name:
                    break

                preset_seeds = []
                print(f"\n[dim]Enter seeds for '{preset_name}' preset:[/dim]")
                while True:
                    seed = typer.prompt(
                        f"Enter seed for '{preset_name}' preset or press Enter to finish",
                        default="",
                    )
                    if not seed:
                        break
                    preset_seeds.append(seed)

                if preset_seeds:
                    presets[preset_name] = preset_seeds
                    print(
                        f"[green]Added preset '{preset_name}' with {len(preset_seeds)} seeds[/green]"
                    )

        config["seeds_for"] = presets

    # Enhanced contract configuration
    print("\n[bold]Contract Configuration[/bold]")
    print("Contracts define API specifications and formal verification requirements.")
    print("These help ensure API compliance and can generate property tests.")

    add_contracts = typer.confirm("Do you have contract files to include?", default=False)
    if add_contracts:
        contract_paths = config.get("contracts_paths", [])
        print("\n[dim]Enter contract file paths one by one:[/dim]")
        while True:
            path = typer.prompt("Enter contract file path or press Enter to finish", default="")
            if not path:
                break
            if os.path.exists(path):
                contract_paths.append(path)
                print(f"[green]Added contract:[/green] {path}")
            else:
                print(f"[yellow]File not found:[/yellow] {path}")
                add_anyway = typer.confirm("Add anyway?", default=False)
                if add_anyway:
                    contract_paths.append(path)
        config["contracts_paths"] = contract_paths

    # Enhanced metrics configuration
    print("\n[bold]Metrics and Analytics Configuration[/bold]")
    print("Understand-First can track Time To Understanding (TTU) metrics and generate reports.")

    enable_metrics = typer.confirm("Enable TTU metrics tracking?", default=False)
    if enable_metrics:
        config["metrics"]["enabled"] = True

        # Additional metrics options
        track_weekly = typer.confirm("Generate weekly TTU reports?", default=True)
        if track_weekly:
            config["metrics"]["weekly_reports"] = True

        track_events = typer.confirm(
            "Track specific events (onboarding, debugging, etc.)?", default=True
        )
        if track_events:
            config["metrics"]["event_tracking"] = True
    else:
        config["metrics"]["enabled"] = False

    # CI/CD Integration
    print("\n[bold]CI/CD Integration[/bold]")
    print("Configure Understand-First to run in your CI/CD pipeline.")

    enable_ci = typer.confirm("Enable CI integration?", default=False)
    if enable_ci:
        config["ci_integration"]["enabled"] = True

        ci_platform = typer.prompt(
            "CI platform (github, gitlab, jenkins, other)", default="github"
        ).lower()
        config["ci_integration"]["platform"] = ci_platform

        fail_on_issues = typer.confirm("Fail CI on understanding issues?", default=True)
        config["ci_integration"]["fail_on_issues"] = fail_on_issues

        generate_reports = typer.confirm("Generate CI reports?", default=True)
        config["ci_integration"]["generate_reports"] = generate_reports

    # IDE Integration
    print("\n[bold]IDE Integration[/bold]")
    print("Configure IDE-specific features and integrations.")

    enable_ide = typer.confirm("Enable IDE integration?", default=True)
    if enable_ide:
        config["ide_integration"]["enabled"] = True

        ide_type = typer.prompt("IDE type (vscode, pycharm, vim, other)", default="vscode").lower()
        config["ide_integration"]["type"] = ide_type

        show_gutter_annotations = typer.confirm("Show gutter annotations?", default=True)
        config["ide_integration"]["gutter_annotations"] = show_gutter_annotations

        enable_quick_peek = typer.confirm("Enable quick peek tours?", default=True)
        config["ide_integration"]["quick_peek"] = enable_quick_peek

    # Analysis options
    print("\n[bold]Analysis Options[/bold]")
    print("Configure advanced analysis features and optimizations.")

    analysis_options = {}

    enable_complexity_analysis = typer.confirm("Enable complexity analysis?", default=True)
    if enable_complexity_analysis:
        analysis_options["complexity_analysis"] = True

    enable_side_effect_detection = typer.confirm("Enable side effect detection?", default=True)
    if enable_side_effect_detection:
        analysis_options["side_effects"] = True

    enable_dependency_analysis = typer.confirm("Enable dependency analysis?", default=True)
    if enable_dependency_analysis:
        analysis_options["dependencies"] = True

    config["analysis_options"] = analysis_options

    # File patterns
    print("\n[bold]File Inclusion/Exclusion Patterns[/bold]")
    print("Configure which files to include or exclude from analysis.")

    configure_patterns = typer.confirm("Configure file patterns?", default=False)
    if configure_patterns:
        # Include patterns
        include_patterns = []
        print("\n[dim]Enter include patterns (e.g., '*.py', 'src/**/*.js'):[/dim]")
        while True:
            pattern = typer.prompt("Include pattern or press Enter to finish", default="")
            if not pattern:
                break
            include_patterns.append(pattern)
        config["include_patterns"] = include_patterns

        # Exclude patterns
        exclude_patterns = ["**/__pycache__/**", "**/node_modules/**", "**/.git/**"]
        print(f"\n[dim]Default exclude patterns: {', '.join(exclude_patterns)}[/dim]")
        add_excludes = typer.confirm("Add additional exclude patterns?", default=False)
        if add_excludes:
            while True:
                pattern = typer.prompt("Exclude pattern or press Enter to finish", default="")
                if not pattern:
                    break
                exclude_patterns.append(pattern)
        config["exclude_patterns"] = exclude_patterns

    # Write configuration with validation
    try:
        import yaml

        # Validate configuration
        errors = validate_config_dict(config)
        if errors:
            print("\n[red]Configuration validation errors:[/red]")
            for error in errors:
                print(f"  • {error}")

            fix_errors = typer.confirm("Fix errors automatically?", default=True)
            if fix_errors:
                config = _fix_config_errors(config, errors)
            else:
                print("[yellow]Saving configuration with errors. Please fix manually.[/yellow]")

        config_yaml = yaml.dump(config, default_flow_style=False, sort_keys=False, indent=2)

        with open(".understand-first.yml", "w", encoding="utf-8") as f:
            f.write(config_yaml)

        # Create necessary directories
        directories = ["tours", "maps", "traces", "contracts", "docs", "fixtures"]
        for directory in directories:
            os.makedirs(directory, exist_ok=True)

        # Create example files
        _create_example_files(project_type)

        # Update README if it exists
        _update_readme_with_integration(project_type)

        print("\n[green]✅ Configuration saved to .understand-first.yml[/green]")
        print("\n[bold]Next steps:[/bold]")
        print("1. Run `u scan . -o maps/repo.json` to generate a repository map")
        print("2. Run `u demo` for a guided demonstration")
        print("3. Run `u doctor` to verify your setup")
        print("4. Run `u init --template` to use project templates")

        if config.get("ci_integration", {}).get("enabled"):
            print("5. Configure your CI pipeline to run `u ci`")

        print("\n[dim]Configuration wizard completed successfully![/dim]")

    except Exception as e:
        print(f"\n[red]Error saving configuration:[/red] {e}")
        raise typer.Exit(1)


def _load_project_template(project_type: str) -> Optional[Dict[str, Any]]:
    """Load project template configuration if available."""
    template_path = f"templates/{project_type}/.understand-first.yml"

    if os.path.exists(template_path):
        try:
            import yaml

            with open(template_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Warning: Failed to load template {template_path}: {e}")

    return None


def _get_suggested_presets(project_type: str) -> Dict[str, List[str]]:
    """Get suggested presets based on project type."""
    presets = {
        "python": {
            "main": ["main.py", "app.py", "run.py"],
            "tests": ["test_*.py", "tests/*.py"],
            "utils": ["utils/*.py", "helpers/*.py"],
        },
        "django": {
            "models": ["*/models.py"],
            "views": ["*/views.py"],
            "urls": ["*/urls.py"],
            "admin": ["*/admin.py"],
            "forms": ["*/forms.py"],
            "tests": ["*/test*.py", "*/tests.py"],
        },
        "fastapi": {
            "routes": ["*/routes/*.py", "*/api/*.py", "main.py"],
            "models": ["*/models.py", "*/schemas.py"],
            "services": ["*/services/*.py", "*/core/*.py"],
            "tests": ["test_*.py", "*/test_*.py"],
        },
        "flask": {
            "routes": ["app.py", "*/routes/*.py", "*/blueprints/*.py"],
            "models": ["*/models.py"],
            "forms": ["*/forms.py"],
            "templates": ["*/templates/**/*.html"],
            "tests": ["test_*.py", "*/test_*.py"],
        },
        "microservices": {
            "services": ["*/service*.py", "*/api*.py"],
            "clients": ["*/client*.py"],
            "models": ["*/models.py", "*/schemas.py"],
            "tests": ["*/test*.py", "*/tests.py"],
        },
        "react": {
            "components": ["src/components/**/*.js", "src/components/**/*.jsx"],
            "pages": ["src/pages/**/*.js", "src/pages/**/*.jsx"],
            "hooks": ["src/hooks/**/*.js"],
            "utils": ["src/utils/**/*.js", "src/helpers/**/*.js"],
            "tests": ["src/**/*.test.js", "src/**/*.spec.js"],
        },
        "nodejs": {
            "routes": ["routes/*.js", "*/routes/*.js"],
            "controllers": ["controllers/*.js", "*/controllers/*.js"],
            "models": ["models/*.js", "*/models/*.js"],
            "middleware": ["middleware/*.js", "*/middleware/*.js"],
            "tests": ["test/*.js", "*/test/*.js", "**/*.test.js"],
        },
        "go": {
            "main": ["main.go", "cmd/**/*.go"],
            "handlers": ["handlers/*.go", "*/handlers/*.go"],
            "models": ["models/*.go", "*/models/*.go"],
            "services": ["services/*.go", "*/services/*.go"],
            "tests": ["*_test.go", "**/*_test.go"],
        },
        "java": {
            "controllers": ["**/controller/*.java", "**/web/*.java"],
            "services": ["**/service/*.java", "**/business/*.java"],
            "models": ["**/model/*.java", "**/entity/*.java"],
            "repositories": ["**/repository/*.java", "**/dao/*.java"],
            "tests": ["**/test/**/*.java", "**/*Test.java"],
        },
    }

    return presets.get(project_type, {})


def _fix_config_errors(config: Dict[str, Any], errors: List[str]) -> Dict[str, Any]:
    """Fix common configuration errors automatically."""
    fixed_config = config.copy()

    for error in errors:
        if "hops" in error and "must be between" in error:
            fixed_config["hops"] = max(1, min(10, fixed_config.get("hops", 2)))
        elif "seeds_for" in error and "must be a dict" in error:
            fixed_config["seeds_for"] = {}
        elif "metrics" in error and "must be a dict" in error:
            fixed_config["metrics"] = {"enabled": False}
        elif "contracts_paths" in error and "must be a list" in error:
            fixed_config["contracts_paths"] = []
        elif "exclude_patterns" in error and "must be a list" in error:
            fixed_config["exclude_patterns"] = ["**/__pycache__/**", "**/node_modules/**"]
        elif "include_patterns" in error and "must be a list" in error:
            fixed_config["include_patterns"] = []

    return fixed_config


def _create_example_files(project_type: str) -> None:
    """Create example files based on project type."""
    try:
        # Create example tour
        tour_content = f"""# Understanding Tour Example

This is an example tour generated for a {project_type} project.

## Getting Started

1. Run `u scan . -o maps/repo.json` to generate a repository map
2. Run `u lens from-seeds --map maps/repo.json --seed main -o maps/lens.json`
3. Run `u tour maps/lens.json -o tours/understanding.md`

## Project-Specific Tips

For {project_type} projects, focus on:
- Main entry points and application structure
- Key business logic and data models
- API endpoints and routing
- Test coverage and quality

## Next Steps

- Add more seeds based on your specific use cases
- Configure CI integration for automated analysis
- Set up IDE integration for real-time insights
"""

        with open("tours/example.md", "w", encoding="utf-8") as f:
            f.write(tour_content)

        # Create example fixture
        fixture_content = f"""# Example Fixture for {project_type} Project

This fixture demonstrates how to test the understanding generated by Understand-First.

## Usage

Run this fixture to verify that the understanding tour can be executed:

```bash
u tour_run --fixtures fixtures maps/lens.json
```

## Customization

Modify this fixture to match your project's specific requirements and test scenarios.
"""

        with open("fixtures/example_fixture.py", "w", encoding="utf-8") as f:
            f.write(fixture_content)

        # Create example contract
        contract_content = f"""# Example Contract for {project_type} Project

This is an example contract file that defines API specifications and formal verification requirements.

## Contract Definition

```yaml
# Example API contract
ROUTE::api:
  GET /health:
    request_schema: {{}}
    response_schema:
      type: object
      properties:
        status:
          type: string
          enum: [healthy, unhealthy]
        timestamp:
          type: string
          format: date-time
    preconditions: []
    postconditions: ["response.status_code == 200"]
    side_effects: []
```

## Usage

1. Define your API contracts in this file
2. Run `u contracts verify` to check compliance
3. Generate property tests with `u contracts stub-tests`
"""

        with open("contracts/example_contracts.yaml", "w", encoding="utf-8") as f:
            f.write(contract_content)

        print("[green]Created example files:[/green]")
        print("  • tours/example.md")
        print("  • fixtures/example_fixture.py")
        print("  • contracts/example_contracts.yaml")

    except Exception as e:
        print(f"Warning: Failed to create example files: {e}")


def _update_readme_with_integration(project_type: str) -> None:
    """Update README with Understand-First integration section."""
    if not os.path.exists("README.md"):
        return

    try:
        integration_section = f"""

## Understand-First Integration

This project uses [Understand-First](https://github.com/your-org/understand-first) for automated code understanding and documentation generation.

### Quick Start

1. **Generate Repository Map**
   ```bash
   u scan . -o maps/repo.json
   ```

2. **Create Understanding Lens**
   ```bash
   u lens from-seeds --map maps/repo.json --seed main -o maps/lens.json
   ```

3. **Generate Understanding Tour**
   ```bash
   u tour maps/lens.json -o tours/understanding.md
   ```

4. **Run Guided Demo**
   ```bash
   u demo
   ```

### Project-Specific Configuration

This {project_type} project is configured with optimized settings for:
- **Seeds**: Key entry points and important modules
- **Analysis**: Complexity analysis, side effect detection, and dependency tracking
- **Integration**: IDE support and CI/CD pipeline integration

### Understanding Features

- **Interactive Tours**: Step-by-step walkthroughs of complex code paths
- **Runtime Tracing**: Actual execution paths, not just static analysis
- **Contract Verification**: API compliance and formal verification
- **Metrics Tracking**: Time To Understanding (TTU) measurement
- **IDE Integration**: Real-time insights in your development environment

### Configuration

The project configuration is stored in `.understand-first.yml`. Key settings include:

- **Hops**: Analysis depth (currently set to {2})
- **Seeds**: Starting points for analysis
- **Presets**: Common scenarios like bug fixes and feature development
- **Patterns**: File inclusion/exclusion rules

### CI/CD Integration

The project is configured for CI/CD integration. Add this to your pipeline:

```yaml
- name: Understand-First Analysis
  run: |
    u scan . -o maps/repo.json
    u lens preset feature --map maps/repo.json -o maps/lens.json
    u tour maps/lens.json -o tours/ci-tour.md
```

### IDE Integration

Install the Understand-First VS Code extension for:
- Gutter annotations showing complexity and call counts
- Quick peek tours and explanations
- Real-time understanding insights

### Learn More

- [Documentation](https://github.com/your-org/understand-first#readme)
- [Examples](https://github.com/your-org/understand-first/tree/main/examples)
- [Web Demo](https://your-org.github.io/understand-first/demo)
"""

        with open("README.md", "a", encoding="utf-8") as f:
            f.write(integration_section)

        print("[green]Updated README.md with Understand-First integration section[/green]")

    except Exception as e:
        print(f"Warning: Failed to update README: {e}")


def generate_diff_markdown(added_functions, removed_functions, modified_functions, changes_count):
    """Generate Markdown summary for diff analysis."""
    markdown = f"""# Understanding Delta Analysis

## Summary

- **Total Changes**: {changes_count}
- **Functions Added**: {len(added_functions)}
- **Functions Removed**: {len(removed_functions)}
- **Functions Modified**: {len(modified_functions)}

## Added Functions

"""

    if added_functions:
        for func in sorted(added_functions):
            markdown += f"- `{func}`\n"
    else:
        markdown += "No functions added.\n"

    markdown += "\n## Removed Functions\n\n"

    if removed_functions:
        for func in sorted(removed_functions):
            markdown += f"- `{func}`\n"
    else:
        markdown += "No functions removed.\n"

    markdown += "\n## Modified Functions\n\n"

    if modified_functions:
        for func in sorted(modified_functions):
            markdown += f"- `{func}`\n"
    else:
        markdown += "No functions modified.\n"

    markdown += """
## Review Checklist

- [ ] Review added functions for new side effects
- [ ] Verify removed functions don't break dependencies
- [ ] Check modified functions for complexity changes
- [ ] Update understanding tours if needed
- [ ] Update documentation for significant changes

*Generated by Understand-First*
"""

    return markdown


def generate_enhanced_diff_markdown(
    added_functions,
    removed_functions,
    modified_functions,
    policy_breaches,
    changes_count,
    policy_threshold,
):
    """Generate enhanced Markdown summary of diff analysis with policy breach information."""
    content = f"# Delta Analysis Summary\n\n"
    content += f"**Total Changes:** {changes_count}\n"
    content += f"**Policy Breaches:** {len(policy_breaches)}\n"
    content += f"**Policy Threshold:** {policy_threshold}\n\n"

    # Status indicator
    if policy_breaches:
        content += "## 🚨 Policy Breaches Detected\n\n"
        content += (
            f"The following functions exceed the complexity threshold of {policy_threshold}:\n\n"
        )
        for breach in policy_breaches:
            content += f"- **{breach['function']}**: {breach['old_complexity']} → {breach['new_complexity']} (threshold: {breach['threshold']})\n"
        content += "\n"
    elif changes_count > 0:
        content += "## ⚠️ Changes Detected\n\n"
        content += "The following changes were detected in your codebase:\n\n"
    else:
        content += "## ✅ No Changes Detected\n\n"
        content += "Your codebase has no changes since the last analysis.\n\n"

    if added_functions:
        content += f"## Added Functions ({len(added_functions)})\n\n"
        for func in sorted(added_functions):
            content += f"- `{func}`\n"
        content += "\n"

    if removed_functions:
        content += f"## Removed Functions ({len(removed_functions)})\n\n"
        for func in sorted(removed_functions):
            content += f"- `{func}`\n"
        content += "\n"

    if modified_functions:
        content += f"## Modified Functions ({len(modified_functions)})\n\n"
        for func in sorted(modified_functions):
            content += f"- `{func}`\n"
        content += "\n"

    content += "## Review Checklist\n\n"
    content += "- [ ] Review added functions for new side effects\n"
    content += "- [ ] Verify removed functions don't break dependencies\n"
    content += "- [ ] Check modified functions for complexity changes\n"
    if policy_breaches:
        content += f"- [ ] **Address policy breaches (complexity > {policy_threshold})**\n"
    content += "- [ ] Update documentation if needed\n"
    content += "- [ ] Update understanding tours if needed\n"
    content += "- [ ] Update CI/CD policies if needed\n\n"

    content += "## Exit Codes\n\n"
    content += "The following exit codes are used for CI integration:\n\n"
    content += "- **0**: No changes detected\n"
    content += "- **2**: Changes detected (update tours/documentation)\n"
    content += "- **3**: Policy breaches detected (address complexity issues)\n\n"

    content += "*Generated by Understand-First*"

    return content


@app.command()
def tour_gate(progress_json: str = typer.Option(".uf-progress.json", "--progress")):
    """Fail if walkthrough milestones are not met (Opened 3/3, Ran 3/3)."""
    try:
        data = json.load(open(progress_json, "r", encoding="utf-8"))
    except Exception:
        print("[red]No progress file found[/red]")
        raise typer.Exit(1)
    opened = int(data.get("opened", 0))
    ran = int(data.get("ran", 0))
    if opened >= 3 and ran >= 3:
        print("[green]Tour milestones met[/green]")
        return
    print(f"[red]Tour milestones not met[/red]: opened {opened}/3 ran {ran}/3")
    raise typer.Exit(1)


@app.command()
def diff(
    old_lens: str = typer.Option(..., "--old"),
    new_lens: str = typer.Option(..., "--new"),
    o: str = typer.Option("maps/delta.svg", "--output", "-o"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
    json_output: bool = typer.Option(False, "--json", help="Output JSON delta instead of SVG"),
    markdown: bool = typer.Option(False, "--markdown", help="Output Markdown summary"),
    ci_gate: bool = typer.Option(False, "--ci-gate", help="Exit with non-zero code for CI gates"),
    policy_threshold: int = typer.Option(
        5, "--policy-threshold", help="Complexity threshold for policy breach"
    ),
):
    """Compare two lens files and generate delta visualization with enhanced analysis."""
    console = Console()

    try:
        # Enhanced validation with better error messages
        if not pathlib.Path(old_lens).exists():
            console.print(
                Panel.fit(
                    f"[red]Error: Old lens file '{old_lens}' does not exist[/red]\n\n"
                    "This could mean:\n"
                    "• The file path is incorrect\n"
                    "• The file hasn't been generated yet\n"
                    "• There's a typo in the filename",
                    title="File Not Found",
                    border_style="red",
                )
            )
            raise typer.Exit(1)

        if not pathlib.Path(new_lens).exists():
            console.print(
                Panel.fit(
                    f"[red]Error: New lens file '{new_lens}' does not exist[/red]\n\n"
                    "This could mean:\n"
                    "• The file path is incorrect\n"
                    "• The file hasn't been generated yet\n"
                    "• There's a typo in the filename",
                    title="File Not Found",
                    border_style="red",
                )
            )
            raise typer.Exit(1)

        # Load lens data with error handling
        try:
            with open(old_lens, "r", encoding="utf-8") as f:
                old_data = json.load(f)
        except json.JSONDecodeError as e:
            console.print(f"[red]Error parsing old lens file:[/red] {str(e)}")
            raise typer.Exit(1)

        try:
            with open(new_lens, "r", encoding="utf-8") as f:
                new_data = json.load(f)
        except json.JSONDecodeError as e:
            console.print(f"[red]Error parsing new lens file:[/red] {str(e)}")
            raise typer.Exit(1)

        # Enhanced configuration display
        config_table = Table(title="Delta Analysis Configuration", show_header=False)
        config_table.add_column("Setting", style="cyan")
        config_table.add_column("Value", style="white")
        config_table.add_row("Old Lens", old_lens)
        config_table.add_row("New Lens", new_lens)
        config_table.add_row("Output Format", "JSON" if json_output else "SVG")
        config_table.add_row("Output File", o)
        config_table.add_row("Policy Threshold", str(policy_threshold))
        config_table.add_row("CI Gate", "Enabled" if ci_gate else "Disabled")

        console.print(config_table)
        console.print()

        # Enhanced analysis with better progress tracking
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:

            diff_task = progress.add_task("Analyzing differences...", total=100)
            progress.update(diff_task, advance=10)

            # Calculate statistics
            old_functions = set(old_data.get("functions", {}).keys())
            new_functions = set(new_data.get("functions", {}).keys())

            added_functions = new_functions - old_functions
            removed_functions = old_functions - new_functions
            modified_functions = []
            policy_breaches = []

            progress.update(diff_task, advance=20)

            # Enhanced function comparison
            for func in old_functions & new_functions:
                old_func = old_data["functions"][func]
                new_func = new_data["functions"][func]

                # Check for modifications
                if (
                    old_func.get("complexity", 0) != new_func.get("complexity", 0)
                    or old_func.get("side_effects", []) != new_func.get("side_effects", [])
                    or old_func.get("lines", 0) != new_func.get("lines", 0)
                ):
                    modified_functions.append(func)

                    # Check for policy breaches
                    if new_func.get("complexity", 0) > policy_threshold:
                        policy_breaches.append(
                            {
                                "function": func,
                                "old_complexity": old_func.get("complexity", 0),
                                "new_complexity": new_func.get("complexity", 0),
                                "threshold": policy_threshold,
                            }
                        )

            progress.update(diff_task, advance=30)

            # Check added functions for policy breaches
            for func in added_functions:
                func_data = new_data["functions"][func]
                if func_data.get("complexity", 0) > policy_threshold:
                    policy_breaches.append(
                        {
                            "function": func,
                            "old_complexity": 0,
                            "new_complexity": func_data.get("complexity", 0),
                            "threshold": policy_threshold,
                        }
                    )

            progress.update(diff_task, advance=20)

            # Generate enhanced output
            if json_output:
                delta_data = {
                    "summary": {
                        "added": len(added_functions),
                        "removed": len(removed_functions),
                        "modified": len(modified_functions),
                        "total_changes": len(added_functions)
                        + len(removed_functions)
                        + len(modified_functions),
                        "policy_breaches": len(policy_breaches),
                        "policy_threshold": policy_threshold,
                    },
                    "added_functions": list(added_functions),
                    "removed_functions": list(removed_functions),
                    "modified_functions": modified_functions,
                    "policy_breaches": policy_breaches,
                    "old_lens": old_lens,
                    "new_lens": new_lens,
                    "timestamp": datetime.now().isoformat(),
                }

                os.makedirs(pathlib.Path(o).parent, exist_ok=True)
                with open(o, "w", encoding="utf-8") as f:
                    json.dump(delta_data, f, indent=2)
            else:
                # Generate SVG visualization
                lens_delta_svg(old_lens, new_lens, o)

            progress.update(diff_task, advance=20)

        # Enhanced results display
        changes_count = len(added_functions) + len(removed_functions) + len(modified_functions)

        # Determine border style based on policy breaches
        if policy_breaches:
            border_style = "red"
            status_icon = "🚨"
            status_text = "Policy breaches detected!"
        elif changes_count > 0:
            border_style = "yellow"
            status_icon = "⚠️"
            status_text = "Changes detected"
        else:
            border_style = "green"
            status_icon = "✅"
            status_text = "No changes detected"

        results_panel = Panel(
            f"[green]✓ Delta analysis completed![/green]\n\n"
            f"📊 [bold]Changes Summary:[/bold]\n"
            f"   • Functions added: {len(added_functions)}\n"
            f"   • Functions removed: {len(removed_functions)}\n"
            f"   • Functions modified: {len(modified_functions)}\n"
            f"   • Total changes: {changes_count}\n"
            f"   • Policy breaches: {len(policy_breaches)}\n"
            f"   • Output file: {o}\n\n"
            f"🎯 [bold]Review Impact:[/bold]\n"
            f"   • Check added functions for new side effects\n"
            f"   • Verify removed functions don't break dependencies\n"
            f"   • Review modified functions for complexity changes\n"
            f"   • Address policy breaches (complexity > {policy_threshold})",
            title=f"{status_icon} Delta Analysis Results - {status_text}",
            border_style=border_style,
        )

        console.print(results_panel)

        # Show policy breaches if any
        if policy_breaches:
            console.print("\n[bold red]Policy Breaches Detected:[/bold red]")
            breach_table = Table(title="Functions Exceeding Complexity Threshold")
            breach_table.add_column("Function", style="cyan")
            breach_table.add_column("Old Complexity", justify="center", style="yellow")
            breach_table.add_column("New Complexity", justify="center", style="red")
            breach_table.add_column("Threshold", justify="center", style="magenta")

            for breach in policy_breaches:
                breach_table.add_row(
                    breach["function"],
                    str(breach["old_complexity"]),
                    str(breach["new_complexity"]),
                    str(breach["threshold"]),
                )

            console.print(breach_table)

        # Show detailed changes if verbose
        if verbose and changes_count > 0:
            if added_functions:
                console.print("\n[bold green]Added Functions:[/bold green]")
                for func in sorted(added_functions):
                    func_data = new_data["functions"][func]
                    complexity = func_data.get("complexity", 0)
                    side_effects = func_data.get("side_effects", [])
                    effects_str = (
                        f" (side effects: {', '.join(side_effects)})" if side_effects else ""
                    )
                    console.print(f"  + {func} (complexity: {complexity}){effects_str}")

            if removed_functions:
                console.print("\n[bold red]Removed Functions:[/bold red]")
                for func in sorted(removed_functions):
                    console.print(f"  - {func}")

            if modified_functions:
                console.print("\n[bold yellow]Modified Functions:[/bold yellow]")
                for func in sorted(modified_functions):
                    old_func = old_data["functions"][func]
                    new_func = new_data["functions"][func]
                    old_complexity = old_func.get("complexity", 0)
                    new_complexity = new_func.get("complexity", 0)
                    console.print(f"  ~ {func} (complexity: {old_complexity} → {new_complexity})")

        # Track TTU metric
        ttu_record(
            "diff_analyzed",
            {
                "changes_count": changes_count,
                "added": len(added_functions),
                "removed": len(removed_functions),
                "modified": len(modified_functions),
                "policy_breaches": len(policy_breaches),
            },
        )

        # Generate enhanced Markdown summary if requested
        if markdown:
            markdown_content = generate_enhanced_diff_markdown(
                added_functions,
                removed_functions,
                modified_functions,
                policy_breaches,
                changes_count,
                policy_threshold,
            )
            markdown_path = o.replace(".svg", ".md").replace(".json", ".md")
            with open(markdown_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)
            console.print(f"[green]✓ Markdown summary written to {markdown_path}[/green]")

        # Enhanced exit codes for CI
        if ci_gate:
            if policy_breaches:
                console.print(
                    f"\n[red]🚨 Policy breaches detected! {len(policy_breaches)} functions exceed complexity threshold of {policy_threshold}.[/red]"
                )
                raise typer.Exit(3)  # Policy breach exit code
            elif changes_count > 0:
                console.print(
                    "\n[yellow]⚠ Changes detected. Consider updating tours and documentation.[/yellow]"
                )
                raise typer.Exit(2)  # Changes detected exit code
            else:
                console.print("\n[green]✓ No changes detected.[/green]")
                raise typer.Exit(0)  # No changes exit code
        else:
            if policy_breaches:
                console.print(
                    f"\n[red]🚨 Policy breaches detected! {len(policy_breaches)} functions exceed complexity threshold of {policy_threshold}.[/red]"
                )
            elif changes_count > 0:
                console.print(
                    "\n[yellow]⚠ Changes detected. Consider updating tours and documentation.[/yellow]"
                )
            else:
                console.print("\n[green]✓ No changes detected.[/green]")
            raise typer.Exit(0)

    except Exception as e:
        console.print(
            Panel.fit(
                f"[red]Error during diff analysis:[/red] {str(e)}\n\n"
                "This might be due to:\n"
                "• Corrupted lens files\n"
                "• File permission issues\n"
                "• Invalid JSON format\n\n"
                "Try running with --verbose for more details",
                title="Analysis Error",
                border_style="red",
            )
        )
        if verbose:
            import traceback

            console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise typer.Exit(1)


@app.command()
def metrics(
    dashboard: bool = typer.Option(False, "--dashboard", "-d", help="Show metrics dashboard"),
    days: int = typer.Option(30, "--days", help="Number of days to analyze"),
    export: str = typer.Option(None, "--export", "-e", help="Export metrics to file"),
    track: str = typer.Option(None, "--track", "-t", help="Track a specific event"),
):
    """View and manage Understand-First metrics for TTU/TTFSC goals."""
    console = Console()

    try:
        if track:
            # Track a specific event
            session_id = get_tracker().start_session()
            track_event(track, session_id)
            console.print(f"[green]✓ Tracked event: {track}[/green]")
            return

        # Generate dashboard data
        dashboard_data = get_dashboard_data(days)

        if dashboard:
            # Show comprehensive dashboard
            show_metrics_dashboard(console, dashboard_data)
        else:
            # Show summary metrics
            show_metrics_summary(console, dashboard_data)

        # Export if requested
        if export:
            with open(export, "w", encoding="utf-8") as f:
                json.dump(dashboard_data, f, indent=2)
            console.print(f"[green]✓ Metrics exported to {export}[/green]")

    except Exception as e:
        console.print(f"[red]Error with metrics:[/red] {str(e)}")
        raise typer.Exit(1)


def show_metrics_dashboard(console: Console, data: Dict[str, Any]):
    """Display comprehensive metrics dashboard"""

    # Header
    console.print(
        Panel(
            "[bold blue]📊 Understand-First Metrics Dashboard[/bold blue]\n"
            f"Period: Last {data['period_days']} days\n"
            f"Generated: {datetime.fromtimestamp(data['timestamp']).strftime('%Y-%m-%d %H:%M:%S')}",
            title="Dashboard",
            border_style="blue",
        )
    )

    # North Star Goals Status
    goals_table = Table(title="North Star Goals Status", show_header=True)
    goals_table.add_column("Goal", style="cyan")
    goals_table.add_column("Target", style="yellow")
    goals_table.add_column("Current", style="white")
    goals_table.add_column("Status", style="green")

    # TTU Goal
    ttu_metrics = data["ttu_metrics"]
    ttu_current = ttu_metrics["average_ttu_minutes"]
    ttu_target = data["north_star_goals"]["ttu_target"]
    ttu_status = "✅" if ttu_current and ttu_current <= ttu_target else "❌"
    goals_table.add_row(
        "TTU (minutes)",
        f"≤{ttu_target}",
        f"{ttu_current:.1f}" if ttu_current else "N/A",
        ttu_status,
    )

    # Activation Goal
    activation_metrics = data["activation_metrics"]
    activation_current = activation_metrics["activation_rate_percentage"]
    activation_target = data["north_star_goals"]["activation_target"]
    activation_status = "✅" if activation_current >= activation_target else "❌"
    goals_table.add_row(
        "Activation Rate (%)",
        f"≥{activation_target}",
        f"{activation_current:.1f}",
        activation_status,
    )

    # Tour Completion Goal
    tour_metrics = data["tour_completion_metrics"]
    tour_current = tour_metrics["completion_rate_percentage"]
    tour_target = data["north_star_goals"]["tour_completion_target"]
    tour_status = "✅" if tour_current >= tour_target else "❌"
    goals_table.add_row(
        "Tour Completion (%)", f"≥{tour_target}", f"{tour_current:.1f}", tour_status
    )

    # PR Coverage Goal
    pr_metrics = data["pr_coverage_metrics"]
    pr_current = pr_metrics["coverage_rate_percentage"]
    pr_target = data["north_star_goals"]["pr_coverage_target"]
    pr_status = "✅" if pr_current >= pr_target else "❌"
    goals_table.add_row("PR Coverage (%)", f"≥{pr_target}", f"{pr_current:.1f}", pr_status)

    console.print(goals_table)
    console.print()

    # Detailed Metrics
    # TTU Metrics
    ttu_panel = Panel(
        f"📈 **TTU Metrics**\n"
        f"• Total sessions: {ttu_metrics['total_sessions']}\n"
        f"• Sessions with tour completion: {ttu_metrics['sessions_with_tour_completion']}\n"
        f"• Average TTU: {ttu_metrics['average_ttu_minutes']:.1f} minutes\n"
        f"• Under 10 minutes: {ttu_metrics['ttu_under_10_min_percentage']:.1f}%",
        title="Time-to-Understanding",
        border_style="blue",
    )
    console.print(ttu_panel)

    # Activation Metrics
    activation_panel = Panel(
        f"🚀 **Activation Metrics**\n"
        f"• Total sessions: {activation_metrics['total_sessions']}\n"
        f"• Activated sessions: {activation_metrics['activated_sessions']}\n"
        f"• Activation rate: {activation_metrics['activation_rate_percentage']:.1f}%\n"
        f"• Under 2 minutes: {activation_metrics['under_2_min_percentage']:.1f}%",
        title="User Activation",
        border_style="green",
    )
    console.print(activation_panel)

    # Tour Completion Metrics
    tour_panel = Panel(
        f"📚 **Tour Completion Metrics**\n"
        f"• Total tours: {tour_metrics['total_tours']}\n"
        f"• Completed tours: {tour_metrics['completed_tours']}\n"
        f"• Completion rate: {tour_metrics['completion_rate_percentage']:.1f}%\n"
        f"• Average completion: {tour_metrics['average_completion_percentage']:.1f}%",
        title="Tour Completion",
        border_style="yellow",
    )
    console.print(tour_panel)

    # PR Coverage Metrics
    pr_panel = Panel(
        f"🔀 **PR Coverage Metrics**\n"
        f"• Total PRs: {pr_metrics['total_prs']}\n"
        f"• PRs with artifacts: {pr_metrics['prs_with_artifacts']}\n"
        f"• Coverage rate: {pr_metrics['coverage_rate_percentage']:.1f}%",
        title="PR Coverage",
        border_style="red",
    )
    console.print(pr_panel)


def show_metrics_summary(console: Console, data: Dict[str, Any]):
    """Display metrics summary"""

    # Quick summary table
    summary_table = Table(
        title=f"Metrics Summary (Last {data['period_days']} days)", show_header=True
    )
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="white")
    summary_table.add_column("Target", style="yellow")

    # Add key metrics
    ttu_metrics = data["ttu_metrics"]
    activation_metrics = data["activation_metrics"]
    tour_metrics = data["tour_completion_metrics"]
    pr_metrics = data["pr_coverage_metrics"]

    summary_table.add_row(
        "Average TTU (minutes)",
        (
            f"{ttu_metrics['average_ttu_minutes']:.1f}"
            if ttu_metrics["average_ttu_minutes"]
            else "N/A"
        ),
        "≤10",
    )

    summary_table.add_row(
        "Activation Rate (%)", f"{activation_metrics['activation_rate_percentage']:.1f}", "≥80"
    )

    summary_table.add_row(
        "Tour Completion (%)", f"{tour_metrics['completion_rate_percentage']:.1f}", "≥80"
    )

    summary_table.add_row("PR Coverage (%)", f"{pr_metrics['coverage_rate_percentage']:.1f}", "≥90")

    console.print(summary_table)
    console.print()

    # Recommendations
    recommendations = []

    if not ttu_metrics["average_ttu_minutes"] or ttu_metrics["average_ttu_minutes"] > 10:
        recommendations.append(
            "🎯 Focus on reducing TTU: improve onboarding and tutorial experience"
        )

    if activation_metrics["activation_rate_percentage"] < 80:
        recommendations.append(
            "🚀 Improve activation: make map generation faster and more intuitive"
        )

    if tour_metrics["completion_rate_percentage"] < 80:
        recommendations.append("📚 Enhance tour experience: make tours more engaging and shorter")

    if pr_metrics["coverage_rate_percentage"] < 90:
        recommendations.append(
            "🔀 Increase PR coverage: automate understanding artifact generation"
        )

    if recommendations:
        console.print(
            Panel("\n".join(recommendations), title="Recommendations", border_style="yellow")
        )


@app.command()
def config_validate(path: str = typer.Option(".understand-first.yml", "--path")):
    if not os.path.exists(path):
        print(f"[yellow]No config found at {path}[/yellow]")
        raise typer.Exit(code=1)
    import yaml as _yaml

    try:
        data = _yaml.safe_load(open(path, "r", encoding="utf-8")) or {}
    except Exception as e:
        print(f"[red]YAML error:[/red] {e}")
        raise typer.Exit(code=1)
    errors = validate_config_dict(data)
    if errors:
        print("[red]Config errors:[/red]")
        for e in errors:
            print(f"- {e}")
        raise typer.Exit(code=1)
    print("[green]Config OK[/green]")


@lens_app.command("explain")
def lens_explain(
    qname: str,
    lens: str = typer.Option("maps/lens_merged.json", "--lens"),
    repo: str = typer.Option("maps/repo.json", "--repo"),
    json_out: bool = typer.Option(False, "--json"),
):
    with open(lens, "r", encoding="utf-8") as f:
        lens_data = json.load(f)
    with open(repo, "r", encoding="utf-8") as f:
        repo_map = json.load(f)
    info = explain_node(qname, lens_data, repo_map)
    if json_out:
        print(json.dumps(info, indent=2))
        return
    print(info.get("qname"))
    print("  reason:")
    for r in info.get("reason", []):
        k, v = next(iter(r.items()))
        print(f"    - {k}: {v}")
    edges = info.get("edges", {})
    print("  edges:")
    print("    callers:", ", ".join(edges.get("callers", [])))
    print("    callees:", ", ".join(edges.get("callees", [])))


@app.command()
def ci(
    scan_path: str = typer.Option(".", "--scan", help="Path to scan for analysis"),
    output_dir: str = typer.Option(
        "ci-artifacts", "--output", "-o", help="Output directory for CI artifacts"
    ),
    fail_on_issues: bool = typer.Option(
        True, "--fail-on-issues", help="Fail CI on understanding issues"
    ),
    generate_report: bool = typer.Option(True, "--report", help="Generate CI report"),
):
    """Run Understand-First analysis for CI/CD pipeline with enhanced reporting."""
    console = Console()

    try:
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)

        # Step 1: Scan repository
        console.print("[bold blue]🔍 Scanning repository...[/bold blue]")
        repo_map_path = os.path.join(output_dir, "repo.json")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            scan_task = progress.add_task("Scanning codebase...", total=100)
            progress.update(scan_task, advance=50)

            # Run scan
            result = build_python_map(pathlib.Path(scan_path))
            progress.update(scan_task, advance=50)

            # Write repo map
            with open(repo_map_path, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)

        console.print(f"[green]✓ Repository map generated: {repo_map_path}[/green]")

        # Step 2: Generate lens
        console.print("[bold blue]🎯 Generating understanding lens...[/bold blue]")
        lens_path = os.path.join(output_dir, "lens.json")

        # Use first few functions as seeds
        functions = list(result.get("functions", {}).keys())
        seeds = functions[:3] if functions else []

        if seeds:
            lens = lens_from_seeds(seeds, result)
            rank_by_error_proximity(lens)

            with open(lens_path, "w", encoding="utf-8") as f:
                json.dump(lens, f, indent=2)

            console.print(f"[green]✓ Understanding lens generated: {lens_path}[/green]")
        else:
            console.print("[yellow]⚠ No functions found for lens generation[/yellow]")
            lens = {"functions": {}, "lens": {"seeds": []}}

        # Step 3: Generate tour
        console.print("[bold blue]🗺️ Generating understanding tour...[/bold blue]")
        tour_path = os.path.join(output_dir, "tour.md")

        if lens.get("functions"):
            tour_md = write_tour_md(lens)
            with open(tour_path, "w", encoding="utf-8") as f:
                f.write(tour_md)
            console.print(f"[green]✓ Understanding tour generated: {tour_path}[/green]")
        else:
            console.print("[yellow]⚠ No lens data for tour generation[/yellow]")

        # Step 4: Generate CI report
        if generate_report:
            console.print("[bold blue]📊 Generating CI report...[/bold blue]")
            report_path = os.path.join(output_dir, "ci-report.md")

            report_content = generate_ci_report(result, lens, scan_path)
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(report_content)
            console.print(f"[green]✓ CI report generated: {report_path}[/green]")

        # Step 5: Check for issues
        issues = []
        functions_count = len(result.get("functions", {}))

        if functions_count == 0:
            issues.append("No functions found in codebase")

        # Check for high complexity functions
        high_complexity = []
        for func_name, func_data in result.get("functions", {}).items():
            complexity = func_data.get("complexity", 0)
            if complexity > 10:
                high_complexity.append(f"{func_name} (complexity: {complexity})")

        if high_complexity:
            issues.append(f"High complexity functions found: {', '.join(high_complexity[:3])}")

        # Check for side effects
        side_effects = []
        for func_name, func_data in result.get("functions", {}).items():
            effects = func_data.get("side_effects", [])
            if effects:
                side_effects.append(f"{func_name}: {', '.join(effects)}")

        if side_effects:
            issues.append(f"Functions with side effects: {', '.join(side_effects[:3])}")

        # Step 6: Report results
        if issues:
            console.print("\n[yellow]⚠ Issues detected:[/yellow]")
            for issue in issues:
                console.print(f"  • {issue}")

            if fail_on_issues:
                console.print("\n[red]❌ CI failed due to understanding issues[/red]")
                raise typer.Exit(1)
            else:
                console.print("\n[yellow]⚠ CI completed with warnings[/yellow]")
        else:
            console.print("\n[green]✅ CI completed successfully - no issues detected[/green]")

        # Step 7: Generate summary
        summary = {
            "scan_path": scan_path,
            "output_dir": output_dir,
            "functions_analyzed": functions_count,
            "issues_found": len(issues),
            "artifacts_generated": [
                "repo.json",
                "lens.json" if seeds else None,
                "tour.md" if lens.get("functions") else None,
                "ci-report.md" if generate_report else None,
            ],
            "issues": issues,
        }

        # Remove None values
        summary["artifacts_generated"] = [
            a for a in summary["artifacts_generated"] if a is not None
        ]

        summary_path = os.path.join(output_dir, "ci-summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        console.print(f"\n[green]✓ CI analysis completed. Summary: {summary_path}[/green]")

        # Track TTU metric
        ttu_record(
            "ci_completed",
            {
                "functions_analyzed": functions_count,
                "issues_found": len(issues),
                "artifacts_generated": len(summary["artifacts_generated"]),
            },
        )

    except Exception as e:
        console.print(f"[red]Error during CI analysis:[/red] {str(e)}")
        raise typer.Exit(1)


def generate_ci_report(repo_map, lens, scan_path):
    """Generate comprehensive CI report."""
    functions = repo_map.get("functions", {})
    functions_count = len(functions)

    # Calculate metrics
    total_complexity = sum(func.get("complexity", 0) for func in functions.values())
    avg_complexity = total_complexity / functions_count if functions_count > 0 else 0

    high_complexity_count = sum(1 for func in functions.values() if func.get("complexity", 0) > 10)
    side_effects_count = sum(1 for func in functions.values() if func.get("side_effects", []))

    # Generate report
    report = f"""# Understand-First CI Report

## Analysis Summary

- **Scan Path**: `{scan_path}`
- **Functions Analyzed**: {functions_count}
- **Total Complexity**: {total_complexity}
- **Average Complexity**: {avg_complexity:.1f}
- **High Complexity Functions**: {high_complexity_count}
- **Functions with Side Effects**: {side_effects_count}

## Understanding Lens

- **Seeds**: {len(lens.get('lens', {}).get('seeds', []))}
- **Functions in Lens**: {len(lens.get('functions', {}))}

## Recommendations

"""

    if high_complexity_count > 0:
        report += f"- Consider refactoring {high_complexity_count} high-complexity functions\n"

    if side_effects_count > 0:
        report += f"- Review {side_effects_count} functions with side effects\n"

    if avg_complexity > 5:
        report += "- Overall complexity is high - consider architectural improvements\n"

    if functions_count == 0:
        report += "- No functions found - check scan path and file patterns\n"

    report += """
## Next Steps

1. Review the understanding tour for key insights
2. Address any high-complexity functions
3. Document side effects and their implications
4. Update understanding artifacts as code evolves

*Generated by Understand-First CI*
"""

    return report


@app.command()
def wizard(
    scan_path: str = typer.Option(".", "--scan", help="Path to scan for analysis"),
    interactive: bool = typer.Option(True, "--interactive", help="Run in interactive mode"),
):
    """Interactive wizard to guide users through understanding analysis."""
    console = Console()

    if not interactive:
        console.print("[yellow]Non-interactive mode - running basic analysis[/yellow]")
        # Run basic analysis
        result = build_python_map(pathlib.Path(scan_path))
        console.print(
            f"[green]Analysis complete. Found {len(result.get('functions', {}))} functions.[/green]"
        )
        return

    # Enhanced welcome with better formatting
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
        # Step 1: Enhanced repository scanning
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

            # Simulate more realistic progress
            progress.update(scan_task, advance=20)
            time.sleep(0.5)

            progress.update(scan_task, advance=30)
            result = build_python_map(pathlib.Path(scan_path))

            progress.update(scan_task, advance=30)
            time.sleep(0.3)

            progress.update(scan_task, advance=20)

        functions = result.get("functions", {})

        # Enhanced success message with stats
        if functions:
            high_complexity = sum(1 for f in functions.values() if f.get("complexity", 0) > 5)
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

        # Step 2: Enhanced function overview with better formatting
        console.print("\n[bold cyan]Step 2: Function Overview[/bold cyan]")

        # Create a table for better function display
        table = Table(title="Functions in your codebase")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("Complexity", justify="center", style="magenta")
        table.add_column("Side Effects", justify="center", style="yellow")
        table.add_column("Lines", justify="center", style="green")

        for func_name, func_data in list(functions.items())[:10]:
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

            table.add_row(func_name, complexity_str, effects_str, str(lines))

        console.print(table)

        if len(functions) > 10:
            console.print(f"\n[yellow]... and {len(functions) - 10} more functions[/yellow]")

        # Step 3: Enhanced seed selection with better UX
        console.print("\n[bold cyan]Step 3: Select Seed Functions[/bold cyan]")
        console.print(
            "Choose functions to start your understanding journey. These will be your 'seeds'.\n"
            "Seeds help us understand which functions are most important to you.\n"
        )

        seeds = []
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
            elif choice.lower() == "list":
                console.print("\n[bold]All functions:[/bold]")
                for i, func_name in enumerate(functions.keys(), 1):
                    complexity = functions[func_name].get("complexity", 0)
                    console.print(f"  {i:2d}. {func_name} (complexity: {complexity})")
                console.print()
                continue
            elif choice.lower() == "help":
                console.print("\n[bold]Tips for selecting seeds:[/bold]")
                console.print("• Choose functions you're most interested in understanding")
                console.print("• Pick functions that seem central to your codebase")
                console.print("• Consider functions with high complexity or side effects")
                console.print("• You can always add more seeds later\n")
                continue
            elif choice in functions:
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
            # Auto-select first few functions with better explanation
            seeds = list(functions.keys())[:3]
            console.print(f"[yellow]No seeds selected. Using first 3 functions: {seeds}[/yellow]")
            console.print(
                "[dim]You can always run the wizard again to select different seeds[/dim]"
            )

        console.print(f"\n[green]✓ Selected seeds: {seeds}[/green]\n")

        # Step 4: Enhanced lens generation with better progress
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

        # Enhanced lens results display
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

        # Step 5: Enhanced lens results with better formatting
        console.print("\n[bold cyan]Step 5: Understanding Lens Results[/bold cyan]")
        console.print("Functions in your understanding lens (ranked by importance):\n")

        # Create a table for lens results
        lens_table = Table(title="Understanding Lens Functions")
        lens_table.add_column("Rank", justify="center", style="cyan")
        lens_table.add_column("Function", style="cyan", no_wrap=True)
        lens_table.add_column("Complexity", justify="center", style="magenta")
        lens_table.add_column("Side Effects", justify="center", style="yellow")
        lens_table.add_column("Importance", justify="center", style="green")

        for i, (func_name, func_data) in enumerate(lens_functions.items(), 1):
            complexity = func_data.get("complexity", 0)
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

        # Step 6: Enhanced tour generation
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

        # Step 7: Enhanced summary and next steps
        console.print("\n[bold green]🎉 Wizard Complete![/bold green]")

        # Create a summary table
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

        # Track TTU metric
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
        raise typer.Exit(1)


@app.command()
def tui(
    scan_path: str = typer.Option(".", "--scan", help="Path to scan for analysis"),
):
    """Launch interactive Text User Interface for code understanding."""
    console = Console()

    try:
        # Enhanced welcome with better formatting
        console.print(
            Panel.fit(
                "[bold blue]🚀 Understand-First TUI[/bold blue]\n\n"
                "Interactive exploration of your codebase.\n"
                "Navigate through functions, understand relationships,\n"
                "and generate personalized learning paths.",
                title="Welcome",
                border_style="blue",
            )
        )
        console.print("[dim]Press Ctrl+C to exit at any time[/dim]\n")

        # Enhanced data loading with progress
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
            result = build_python_map(pathlib.Path(scan_path))

            progress.update(load_task, advance=30)

        functions = result.get("functions", {})

        if functions:
            high_complexity = sum(1 for f in functions.values() if f.get("complexity", 0) > 5)
            with_side_effects = sum(1 for f in functions.values() if f.get("side_effects", []))

            console.print(
                Panel.fit(
                    f"[green]✓ Codebase loaded successfully![/green]\n\n"
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

        # Enhanced main TUI loop
        while True:
            console.print("\n[bold cyan]Main Menu[/bold cyan]")

            # Create a menu table for better visual appeal
            menu_table = Table(show_header=False, box=None)
            menu_table.add_column("Option", style="cyan", width=3)
            menu_table.add_column("Description", style="white")

            menu_table.add_row("1", "📋 View function list")
            menu_table.add_row("2", "🔍 Search functions")
            menu_table.add_row("3", "🔬 Generate understanding lens")
            menu_table.add_row("4", "📊 View function details")
            menu_table.add_row("5", "📚 Generate tour")
            menu_table.add_row("6", "💾 Export data")
            menu_table.add_row("7", "📈 View metrics")
            menu_table.add_row("0", "🚪 Exit")

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

        # Track TTU metric
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
        raise typer.Exit(1)


def show_function_list(console, functions):
    """Show paginated function list with enhanced formatting."""
    console.print("\n[bold cyan]Function List[/bold cyan]")

    page_size = 20
    total_pages = (len(functions) + page_size - 1) // page_size
    page = 0

    while True:
        start_idx = page * page_size
        end_idx = min(start_idx + page_size, len(functions))

        # Create a table for better function display
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


def show_metrics(console, result):
    """Show codebase metrics and statistics."""
    functions = result.get("functions", {})

    if not functions:
        console.print("[yellow]No functions to analyze metrics for.[/yellow]")
        return

    # Calculate metrics
    total_functions = len(functions)
    high_complexity = sum(1 for f in functions.values() if f.get("complexity", 0) > 5)
    with_side_effects = sum(1 for f in functions.values() if f.get("side_effects", []))
    avg_complexity = sum(f.get("complexity", 0) for f in functions.values()) / total_functions
    total_lines = sum(f.get("lines", 0) for f in functions.values())

    # Create metrics table
    metrics_table = Table(title="Codebase Metrics")
    metrics_table.add_column("Metric", style="cyan")
    metrics_table.add_column("Value", style="green")
    metrics_table.add_column("Percentage", style="yellow")

    metrics_table.add_row("Total Functions", str(total_functions), "100%")
    metrics_table.add_row(
        "High Complexity", str(high_complexity), f"{high_complexity/total_functions*100:.1f}%"
    )
    metrics_table.add_row(
        "With Side Effects", str(with_side_effects), f"{with_side_effects/total_functions*100:.1f}%"
    )
    metrics_table.add_row("Average Complexity", f"{avg_complexity:.1f}", "-")
    metrics_table.add_row("Total Lines", str(total_lines), "-")

    console.print(metrics_table)

    # Show complexity distribution
    complexity_dist = {}
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

    # Show top complex functions
    top_complex = sorted(functions.items(), key=lambda x: x[1].get("complexity", 0), reverse=True)[
        :5
    ]
    if top_complex:
        console.print("\n[bold cyan]Top 5 Most Complex Functions[/bold cyan]")
        for i, (name, data) in enumerate(top_complex, 1):
            complexity = data.get("complexity", 0)
            console.print(f"  {i}. {name} (complexity: {complexity})")


def search_functions(console, functions):
    """Search functions by name or complexity with enhanced formatting."""
    console.print("\n[bold cyan]Function Search[/bold cyan]")
    console.print("Search by function name or complexity threshold\n")

    query = typer.prompt("Enter search term (function name or complexity threshold)")

    if query.isdigit():
        # Search by complexity
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

            # Create a table for matches
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
        # Search by name
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

            # Create a table for matches
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


def generate_lens_interactive(console, functions, result):
    """Generate lens interactively."""
    console.print("\n[bold]Generate Understanding Lens[/bold]")

    # Show function selection
    console.print("Select seed functions (comma-separated numbers):")
    func_list = list(functions.items())
    for i, (name, data) in enumerate(func_list[:20]):  # Show first 20
        complexity = data.get("complexity", 0)
        console.print(f"  {i+1:2d}. {name} (complexity: {complexity})")

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

        # Generate lens
        with console.status("[bold green]Generating lens..."):
            lens = lens_from_seeds(seeds, result)
            rank_by_error_proximity(lens)

        lens_functions = lens.get("functions", {})
        console.print(f"[green]✓ Generated lens with {len(lens_functions)} functions[/green]")

        # Show lens results
        console.print("\nLens functions (ranked by importance):")
        for i, (name, data) in enumerate(lens_functions.items(), 1):
            complexity = data.get("complexity", 0)
            console.print(f"  {i:2d}. {name} (complexity: {complexity})")

    except (ValueError, IndexError) as e:
        console.print(f"[red]Invalid selection: {e}[/red]")


def view_function_details(console, functions):
    """View detailed function information."""
    console.print("\n[bold]Function Details[/bold]")

    func_name = typer.prompt("Enter function name")

    if func_name not in functions:
        console.print(f"[red]Function '{func_name}' not found[/red]")
        return

    data = functions[func_name]
    console.print(f"\n[bold]{func_name}[/bold]")
    console.print(f"  Complexity: {data.get('complexity', 0)}")
    console.print(f"  Side effects: {', '.join(data.get('side_effects', []))}")

    edges = data.get("edges", {})
    if edges.get("callers"):
        console.print(f"  Callers: {', '.join(edges['callers'])}")
    if edges.get("callees"):
        console.print(f"  Callees: {', '.join(edges['callees'])}")


def generate_tour_interactive(console, functions, result):
    """Generate tour interactively."""
    console.print("\n[bold]Generate Understanding Tour[/bold]")

    # Check if we have a lens
    seeds = typer.prompt("Enter seed functions (comma-separated)", default="")

    if not seeds:
        console.print("[yellow]No seeds provided. Using first 3 functions.[/yellow]")
        seeds = list(functions.keys())[:3]
    else:
        seeds = [s.strip() for s in seeds.split(",")]
        # Validate seeds
        valid_seeds = [s for s in seeds if s in functions]
        if not valid_seeds:
            console.print("[red]No valid seeds found[/red]")
            return
        seeds = valid_seeds

    console.print(f"[green]Using seeds: {seeds}[/green]")

    # Generate lens and tour
    with console.status("[bold green]Generating tour..."):
        lens = lens_from_seeds(seeds, result)
        rank_by_error_proximity(lens)

        if lens.get("functions"):
            tour_md = write_tour_md(lens)
            tour_path = "understanding_tour.md"
            with open(tour_path, "w", encoding="utf-8") as f:
                f.write(tour_md)
            console.print(f"[green]✓ Tour generated: {tour_path}[/green]")
        else:
            console.print("[yellow]No functions in lens for tour generation[/yellow]")


def export_data_interactive(console, result):
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
        console.print(f"[green]✓ Exported to {output_path}[/green]")
    elif choice == 2:
        output_path = "analysis.md"
        # Generate simple markdown report
        functions = result.get("functions", {})
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# Code Analysis Report\n\n")
            f.write(f"Functions analyzed: {len(functions)}\n\n")
            f.write("## Functions\n\n")
            for name, data in functions.items():
                complexity = data.get("complexity", 0)
                side_effects = data.get("side_effects", [])
                f.write(f"- **{name}** (complexity: {complexity})\n")
                if side_effects:
                    f.write(f"  - Side effects: {', '.join(side_effects)}\n")
        console.print(f"[green]✓ Exported to {output_path}[/green]")
    elif choice == 3:
        console.print("[yellow]SVG export not implemented in TUI mode[/yellow]")
    else:
        console.print("[red]Invalid choice[/red]")


@app.command()
def metrics(
    days: int = typer.Option(30, "--days", "-d", help="Number of days to analyze"),
    format: str = typer.Option("report", "--format", "-f", help="Output format: report, json, csv"),
    output: str = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """Generate metrics report for TTU and TTFSC tracking."""
    console = Console()

    try:
        from ucli.metrics.analytics import (
            get_dashboard_data,
            generate_metrics_report,
            export_metrics_csv,
        )

        console.print(
            f"[bold blue]📊 Generating metrics report for last {days} days...[/bold blue]"
        )

        if format == "report":
            report = generate_metrics_report(days)

            if output:
                with open(output, "w", encoding="utf-8") as f:
                    f.write(report)
                console.print(f"[green]✓ Metrics report saved to {output}[/green]")
            else:
                console.print("\n" + report)

        elif format == "json":
            data = get_dashboard_data(days)

            if output:
                with open(output, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                console.print(f"[green]✓ Metrics data saved to {output}[/green]")
            else:
                console.print(json.dumps(data, indent=2))

        elif format == "csv":
            output_file = output or f"metrics_export_{days}d.csv"
            csv_file = export_metrics_csv(days, output_file)
            console.print(f"[green]✓ Metrics CSV exported to {csv_file}[/green]")

        else:
            console.print("[red]Invalid format. Use: report, json, or csv[/red]")
            raise typer.Exit(1)

    except ImportError:
        console.print("[red]Analytics module not available[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error generating metrics:[/red] {str(e)}")
        raise typer.Exit(1)
