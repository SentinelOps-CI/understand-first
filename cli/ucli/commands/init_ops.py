"""Init / wizard / TUI helpers and CLI banner (extracted from main.py)."""

from __future__ import annotations

import os
from typing import Any

import typer
from rich import print
from rich.align import Align
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ucli.config import filter_config_to_schema, validate_config_dict


def show_banner() -> None:
    """Print the Understand-First ASCII banner."""
    console = Console()
    banner = """
[bold cyan]
  _   _           _               _                  _   _____ _          _
 | | | |_ __   __| | ___ _ __ ___| |_ __ _ _ __   __| | |  ___(_)_ __ ___| |_
 | | | | '_ \\ / _` |/ _ \\ '__/ __| __/ _` | '_ \\ / _` | | |_  | | '__/ __| __|
 | |_| | | | | (_| |  __/ |  \\__ \\ || (_| | | | | (_| | |  _| | | |  \\__ \\ |_
  \\___/|_| |_|\\__,_|\\___|_|  |___/\\__\\__,_|_| |_|\\__,_| |_|   |_|_|  |___/\\__|
[/bold cyan]
"""
    console.print(banner)
    console.print("[dim]Accelerate code understanding with intelligent analysis[/dim]")
    console.print()


def show_welcome_message() -> None:
    """Print quick-start hints under the banner."""
    console = Console()
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="cyan")
    table.add_column(style="white")
    table.add_row("Quick start:", "u scan . && u lens from-seeds --map maps/repo.json --seed <fn>")
    table.add_row("Help:", "u --help   |   u <command> --help")
    console.print(table)


def run_init(*, stack: str, ci: str, wizard: bool, tui: bool) -> None:
    """Dispatch ``u init`` to TUI, wizard, or basic config write."""
    if tui:
        _launch_tui_mode()
    elif wizard:
        _run_config_wizard()
    else:
        _create_basic_config(stack, ci)


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
    Console()

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
    for key, (_value, description, details) in project_types.items():
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

    # Only keys honored by runtime SCHEMA (see ucli.config.SCHEMA).
    config = {
        "hops": 2,
        "seeds": [],
        "seeds_for": {},
        "contracts_paths": [],
        "glossary_path": "docs/glossary.md",
        "metrics": {"enabled": False},
    }

    # Merge template configuration (schema-filtered)
    if template_config:
        config.update(filter_config_to_schema(template_config))
        print(f"\n[green]Loaded template configuration for {project_name}[/green]")

    # Hops configuration with better validation
    print("\n[bold]Analysis Depth Configuration[/bold]")
    print("Hops determine how deep the analysis should traverse from seed functions.")
    print("Higher values provide more comprehensive analysis but may be slower.")
    print("[dim]Schema allows hops in 0..5.[/dim]")

    hops = typer.prompt(
        "How many hops should the lens traverse? (0-5, default: 2)",
        type=int,
        default=config.get("hops", 2),
    )
    config["hops"] = max(0, min(5, hops))

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
    config["metrics"] = {"enabled": bool(enable_metrics)}

    # Write configuration with validation (SCHEMA keys only)
    try:
        import yaml

        config = filter_config_to_schema(config)
        errors = validate_config_dict(config)
        if errors:
            print("\n[red]Configuration validation errors:[/red]")
            for error in errors:
                print(f"  • {error}")

            fix_errors = typer.confirm("Fix errors automatically?", default=True)
            if fix_errors:
                config = filter_config_to_schema(_fix_config_errors(config, errors))
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
        print("4. Run `u config-validate` to confirm the config schema")

        print("\n[dim]Configuration wizard completed successfully![/dim]")

    except Exception as e:
        print(f"\n[red]Error saving configuration:[/red] {e}")
        raise typer.Exit(1) from None


def _load_project_template(project_type: str) -> dict[str, Any] | None:
    """Load project template configuration if available (SCHEMA keys only)."""
    template_path = f"templates/{project_type}/.understand-first.yml"

    if os.path.exists(template_path):
        try:
            import yaml

            with open(template_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            if isinstance(data, dict):
                return filter_config_to_schema(data)
        except Exception as e:
            print(f"Warning: Failed to load template {template_path}: {e}")

    return None


def _get_suggested_presets(project_type: str) -> dict[str, list[str]]:
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


def _fix_config_errors(config: dict[str, Any], errors: list[str]) -> dict[str, Any]:
    """Fix common configuration errors automatically (SCHEMA-aligned)."""
    fixed_config = filter_config_to_schema(config)

    for error in errors:
        if "hops" in error:
            fixed_config["hops"] = max(0, min(5, int(fixed_config.get("hops", 2) or 2)))
        elif "seeds_for" in error:
            fixed_config["seeds_for"] = {}
        elif "metrics" in error:
            fixed_config["metrics"] = {"enabled": False}
        elif "contracts_paths" in error:
            fixed_config["contracts_paths"] = []
        elif "seeds" in error:
            fixed_config["seeds"] = []
        elif "glossary_path" in error:
            fixed_config["glossary_path"] = "docs/glossary.md"

    return filter_config_to_schema(fixed_config)


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

This project uses [Understand-First](https://github.com/SentinelOps-CI/understand-first) for automated code understanding and documentation generation.

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

- [Documentation](https://github.com/SentinelOps-CI/understand-first#readme)
- [Examples](https://github.com/SentinelOps-CI/understand-first/tree/main/examples)
- [Web Demo](https://sentinelops-ci.github.io/understand-first/demo)
"""

        with open("README.md", "a", encoding="utf-8") as f:
            f.write(integration_section)

        print("[green]Updated README.md with Understand-First integration section[/green]")

    except Exception as e:
        print(f"Warning: Failed to update README: {e}")
