"""Typer sub-app wiring for command groups (keeps main.py thin).

Each ``register_*`` attaches a named Typer group and maps options to ``run_*``
helpers in the corresponding ``*_ops`` modules.
"""

from __future__ import annotations

import typer

from ucli.commands.ci_ops import run_ci
from ucli.commands.contracts_ops import (
    run_contracts_check,
    run_contracts_compose,
    run_contracts_from_openapi,
    run_contracts_from_proto,
    run_contracts_init,
    run_contracts_lean_stubs,
    run_contracts_report,
    run_contracts_stub,
    run_contracts_verify_lean,
)
from ucli.commands.demo_ops import run_demo
from ucli.commands.diff_ops import run_diff
from ucli.commands.doctor_ops import run_doctor
from ucli.commands.explorer_ops import run_tui
from ucli.commands.init_ops import run_init
from ucli.commands.lens_ops import (
    run_ingest_github,
    run_ingest_jira,
    run_lens_explain,
    run_lens_from_issue,
    run_lens_from_seeds,
    run_lens_merge_trace,
    run_lens_preset,
)
from ucli.commands.metrics_ops import run_metrics
from ucli.commands.pack_ops import run_pack_create, run_pack_publish
from ucli.commands.report_ops import (
    run_config_validate,
    run_dashboard,
    run_glossary,
    run_map,
    run_report,
    run_ttu,
)
from ucli.commands.scan_ops import run_scan
from ucli.commands.tour_ops import run_tour, run_tour_gate, run_tour_run
from ucli.commands.trace_ops import run_trace_errors, run_trace_module
from ucli.commands.visual_ops import run_boundaries_scan, run_visual_delta
from ucli.commands.wizard_ops import run_wizard


def register_lens(app: typer.Typer) -> None:
    lens_app = typer.Typer(help="Task lenses")
    app.add_typer(lens_app, name="lens")

    @lens_app.command("from-issue")
    def lens_from_issue_cmd(
        issue_md: str,
        map: str = typer.Option(..., "--map"),
        o: str = typer.Option("maps/lens.json", "--output", "-o"),
    ):
        run_lens_from_issue(issue_md, map, o)

    @lens_app.command("from-seeds")
    def lens_from_seeds_cmd(
        seed: list[str] = typer.Option([], "--seed"),
        map: str = typer.Option(..., "--map"),
        o: str = typer.Option("maps/lens.json", "--output", "-o"),
        interactive: bool = typer.Option(
            False, "--interactive", "-i", help="Interactive seed selection"
        ),
        verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
        exact: bool = typer.Option(
            False,
            "--exact",
            help="Match seeds exactly (full qname, local name, or simple_name) instead of substring",
        ),
    ):
        """Create understanding lens from seed functions with enhanced TUI."""
        run_lens_from_seeds(seed, map, o, interactive=interactive, verbose=verbose, exact=exact)

    @lens_app.command("merge-trace")
    def lens_merge_trace_cmd(
        lens_json: str,
        trace_json: str,
        o: str = typer.Option("maps/lens_merged.json", "--output", "-o"),
    ):
        run_lens_merge_trace(lens_json, trace_json, o)

    @lens_app.command("preset")
    def lens_preset_cmd(
        label: str,
        map: str = typer.Option(..., "--map"),
        o: str = typer.Option("maps/lens.json", "--output", "-o"),
    ):
        run_lens_preset(label, map, o)

    @lens_app.command("ingest-github")
    def ingest_github(log_path: str):
        run_ingest_github(log_path)

    @lens_app.command("ingest-jira")
    def ingest_jira(jira_path: str):
        run_ingest_jira(jira_path)

    @lens_app.command("explain")
    def lens_explain(
        qname: str,
        lens: str = typer.Option("maps/lens_merged.json", "--lens"),
        repo: str = typer.Option("maps/repo.json", "--repo"),
        json_out: bool = typer.Option(False, "--json"),
    ):
        run_lens_explain(qname, lens, repo, json_out=json_out)


def register_trace(app: typer.Typer) -> None:
    trace_app = typer.Typer(help="Runtime tracing (Python demo)")
    app.add_typer(trace_app, name="trace")

    @trace_app.command("module")
    def trace_module(
        pyfile: str,
        func: str,
        a: str | None = None,
        b: str | None = None,
        o: str = typer.Option("traces/trace.json", "--output", "-o"),
    ):
        run_trace_module(pyfile, func, a, b, o)

    @trace_app.command("errors")
    def trace_errors(pyfile: str, json_out: bool = typer.Option(True, "--json/--no-json")):
        run_trace_errors(pyfile, json_out=json_out)


def register_boundaries(app: typer.Typer) -> None:
    bound_app = typer.Typer(help="Boundary scanners")
    app.add_typer(bound_app, name="boundaries")

    @bound_app.command("scan")
    def boundaries_scan(
        path: str = typer.Argument("."),
        o: str = typer.Option("maps/boundaries.json", "--output", "-o"),
    ):
        run_boundaries_scan(path, o)


def register_contracts(app: typer.Typer) -> None:
    contracts_app = typer.Typer(help="Contracts")
    app.add_typer(contracts_app, name="contracts")

    @contracts_app.command("init")
    def contracts_init(
        path: str = typer.Argument("."),
        o: str = typer.Option("contracts/contracts.yaml", "--output", "-o"),
    ):
        run_contracts_init(path, o)

    @contracts_app.command("check")
    def contracts_check(path: str):
        run_contracts_check(path)

    @contracts_app.command("stub-tests")
    def contracts_stub(
        path: str, o: str = typer.Option("tests/test_contracts.py", "--output", "-o")
    ):
        run_contracts_stub(path, o)

    @contracts_app.command("from-openapi")
    def contracts_from_openapi(
        path: str,
        o: str = typer.Option("contracts/contracts_from_openapi.yaml", "--output", "-o"),
    ):
        run_contracts_from_openapi(path, o)

    @contracts_app.command("from-proto")
    def contracts_from_proto(
        path: str,
        o: str = typer.Option("contracts/contracts_from_proto.yaml", "--output", "-o"),
    ):
        run_contracts_from_proto(path, o)

    @contracts_app.command(
        "lean-stubs",
        help="Emit Lean scaffold stubs (Prop := True / by trivial; not a real proof).",
    )
    def contracts_lean_stubs(
        contracts_yaml: str, o: str = typer.Option("contracts/lean/", "--output-dir", "-o")
    ):
        run_contracts_lean_stubs(contracts_yaml, o)

    @contracts_app.command("compose")
    def contracts_compose(
        i: list[str] = typer.Option([], "--input", "-i", help="Contract YAML input paths"),
        o: str = typer.Option("contracts/contracts.yaml", "--output", "-o"),
    ):
        run_contracts_compose(i, o)

    @contracts_app.command(
        "verify-lean",
        help="Presence-only check that Lean scaffold theorem stubs exist (does not compile Lean).",
    )
    def contracts_verify_lean(
        contracts_yaml: str = typer.Argument(...),
        lean_dir: str = typer.Option("contracts/lean", "--lean-dir", "-l"),
        json_out: bool = typer.Option(False, "--json"),
    ):
        run_contracts_verify_lean(contracts_yaml, lean_dir, json_out=json_out)

    @contracts_app.command("report")
    def contracts_report(
        path: str,
        json_out: bool = typer.Option(False, "--json", help="Emit JSON report to stdout"),
    ):
        run_contracts_report(path, json_out=json_out)


def register_pack(app: typer.Typer) -> None:
    pack_app = typer.Typer(help="Understanding Packs")
    app.add_typer(pack_app, name="pack")

    @pack_app.command("create")
    def pack_create(
        lens: str = typer.Option(..., "--lens"),
        tour: str = typer.Option(..., "--tour"),
        contracts: str = typer.Option(..., "--contracts"),
        o: str = typer.Option("packs/pack.zip", "--output", "-o"),
    ):
        run_pack_create(lens, tour, contracts, o)

    @pack_app.command("publish")
    def pack_publish(
        dist: str = typer.Option("dist", "--dist", help="Output directory for pack artifacts"),
    ):
        """Build local understanding-pack.zip artifacts (replaces legacy `u pack --publish`)."""
        run_pack_publish(dist)


def register_visual(app: typer.Typer) -> None:
    visual_app = typer.Typer(help="Visualization utilities")
    app.add_typer(visual_app, name="visual")

    @visual_app.command("delta")
    def visual_delta(
        old_lens: str,
        new_lens: str,
        o: str = typer.Option("maps/delta.svg", "--output", "-o"),
    ):
        run_visual_delta(old_lens, new_lens, o)


def register_top_level(app: typer.Typer) -> None:
    """Register flat top-level commands (same pattern as named groups)."""

    @app.command()
    def scan(
        path: str = typer.Argument("."),
        o: str = typer.Option("maps/out.json", "--output", "-o"),
        verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
        debug: bool = typer.Option(False, "--debug", help="Enable debug mode with tracebacks"),
        interactive: bool = typer.Option(
            False, "--interactive", "-i", help="Interactive scan with guided options"
        ),
        lang: str | None = typer.Option(
            None,
            "--lang",
            help=(
                "Limit analyzers: python, javascript, go, java, rust, csharp "
                "(aliases: js, ts, typescript, golang, cs, c#). Comma-separated."
            ),
        ),
    ):
        """Scan codebase and build repository map with enhanced progress tracking."""
        run_scan(path, o, verbose=verbose, debug=debug, interactive=interactive, lang=lang)

    @app.command()
    def map(json_path: str, o: str = typer.Option("maps", "--output", "-o")):
        """Generate DOT graph visualization from analysis results."""
        run_map(json_path, o)

    @app.command()
    def report(json_path: str, o: str = typer.Option("maps", "--output", "-o")):
        run_report(json_path, o)

    @app.command()
    def tour(lens_json: str, o: str = typer.Option("tours/tour.md", "--output", "-o")):
        run_tour(lens_json, o)

    # Keep underscore names so docs/CI (`u tour_run`) match invocation (Typer
    # would otherwise expose only ``tour-run``).
    @app.command("tour_run")
    def tour_run(lens_json: str, fixtures_dir: str = typer.Option("fixtures", "--fixtures", "-f")):
        """Run a Python fixture against a lens; refuses non-Python maps (no invented runtime)."""
        run_tour_run(lens_json, fixtures_dir=fixtures_dir)

    @app.command()
    def glossary(o: str = typer.Option("docs/glossary.md", "--output", "-o")):
        run_glossary(o)

    @app.command()
    def dashboard(
        repo: str = typer.Option("maps/repo.json", "--repo"),
        lens: str = typer.Option("maps/lens_merged.json", "--lens"),
        bounds: str = typer.Option("maps/boundaries.json", "--bounds"),
        o: str = typer.Option("docs/understanding-dashboard.md", "--output", "-o"),
    ):
        run_dashboard(repo, lens, bounds, o)

    @app.command()
    def ttu(
        event: str = typer.Argument(...),
        o: str = typer.Option("docs/ttu.md", "--output", "-o"),
    ):
        run_ttu(event, o)

    @app.command()
    def lens_preset(
        label: str,
        map: str = typer.Option(..., "--map"),
        o: str = typer.Option("maps/lens.json", "--output", "-o"),
    ):
        run_lens_preset(label, map, o)

    @app.command()
    def doctor():
        run_doctor()

    @app.command()
    def demo():
        """Generate sample maps, lens, tour, and dashboard artifacts."""
        run_demo()

    @app.command()
    def init(
        stack: str = typer.Option("py", "--stack"),
        ci: str = typer.Option("github", "--ci"),
        wizard: bool = typer.Option(False, "--wizard", help="Interactive configuration wizard"),
        tui: bool = typer.Option(False, "--tui", help="Launch interactive TUI mode"),
    ):
        """Write `.understand-first.yml` (use --wizard for interactive setup)."""
        run_init(stack=stack, ci=ci, wizard=wizard, tui=tui)

    @app.command("tour_gate")
    def tour_gate(
        progress_json: str = typer.Option(".uf-progress.json", "--progress"),
        fixture_lens: str = typer.Option(
            "",
            "--fixture-lens",
            help="If set, run tour_run on this lens and write progress (CI-friendly).",
        ),
        fixtures_dir: str = typer.Option("fixtures", "--fixtures", "-f"),
    ):
        """Fail if walkthrough milestones are not met (opened>=3 and ran>=3).

        Progress is produced by:
          - VS Code walkthrough panel (writes .uf-progress.json), or
          - ``u tour_gate --fixture-lens maps/lens_merged.json`` (runs fixture, records ran), or
          - ``u tour_run`` (updates ran count after a successful fixture).

        For PR CI that only needs a fixture smoke test, prefer ``u tour_run`` directly
        (see tour-must-pass.yml). This gate is for milestone tracking when a progress
        file exists.
        """
        run_tour_gate(progress_json, fixture_lens=fixture_lens, fixtures_dir=fixtures_dir)

    @app.command()
    def diff(
        old_lens: str = typer.Option(..., "--old"),
        new_lens: str = typer.Option(..., "--new"),
        o: str = typer.Option("maps/delta.svg", "--output", "-o"),
        verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
        json_output: bool = typer.Option(False, "--json", help="Output JSON delta instead of SVG"),
        markdown: bool = typer.Option(False, "--markdown", help="Output Markdown summary"),
        ci_gate: bool = typer.Option(
            False, "--ci-gate", help="Exit with non-zero code for CI gates"
        ),
        policy_threshold: int = typer.Option(
            5, "--policy-threshold", help="Complexity threshold for policy breach"
        ),
    ):
        """Compare two lens files and generate delta visualization with enhanced analysis."""
        run_diff(
            old_lens,
            new_lens,
            o,
            verbose=verbose,
            json_output=json_output,
            markdown=markdown,
            ci_gate=ci_gate,
            policy_threshold=policy_threshold,
        )

    @app.command()
    def metrics(
        dashboard: bool = typer.Option(False, "--dashboard", "-d", help="Show metrics dashboard"),
        days: int = typer.Option(30, "--days", help="Number of days to analyze"),
        export: str = typer.Option(None, "--export", "-e", help="Export metrics to file"),
        track: str = typer.Option(None, "--track", "-t", help="Track a specific event"),
    ):
        """View and manage Understand-First metrics for TTU/TTFSC goals."""
        run_metrics(dashboard=dashboard, days=days, export=export, track=track)

    @app.command()
    def config_validate(path: str = typer.Option(".understand-first.yml", "--path")):
        run_config_validate(path)

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
        run_ci(
            scan_path,
            output_dir,
            fail_on_issues=fail_on_issues,
            generate_report=generate_report,
        )

    @app.command()
    def wizard(
        scan_path: str = typer.Option(".", "--scan", help="Path to scan for analysis"),
        interactive: bool = typer.Option(True, "--interactive", help="Run in interactive mode"),
    ):
        """Interactive wizard to guide users through understanding analysis."""
        run_wizard(scan_path, interactive=interactive)

    @app.command()
    def tui(
        scan_path: str = typer.Option(".", "--scan", help="Path to scan for analysis"),
    ):
        """Launch interactive Text User Interface for code understanding."""
        run_tui(scan_path)


def register_all_groups(app: typer.Typer) -> None:
    """Attach lens/trace/boundaries/contracts/pack/visual groups and top-level cmds."""
    register_lens(app)
    register_trace(app)
    register_boundaries(app)
    register_contracts(app)
    register_pack(app)
    register_visual(app)
    register_top_level(app)
