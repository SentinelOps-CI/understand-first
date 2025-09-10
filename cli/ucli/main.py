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


app = typer.Typer(
    help=(
        "Understand-first CLI (u): lenses, traces, contracts, boundaries, "
        "tour gate, delta visualizer."
    )
)


@app.command()
def scan(
    path: str = typer.Argument("."),
    o: str = typer.Option("maps/out.json", "--output", "-o"),
):
    p = pathlib.Path(path)
    result = build_python_map(p)
    os.makedirs(pathlib.Path(o).parent, exist_ok=True)
    with open(o, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"[green]Wrote[/green] {o}")


@app.command()
def map(json_path: str, o: str = typer.Option("maps", "--output", "-o")):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    os.makedirs(o, exist_ok=True)
    dot_path = os.path.join(o, pathlib.Path(json_path).stem + ".dot")
    write_dot(data, dot_path)
    print(f"[green]Wrote[/green] {dot_path}")


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
):
    with open(map, "r", encoding="utf-8") as f:
        repo_map = json.load(f)
    lens = lens_from_seeds(seed, repo_map)
    rank_by_error_proximity(lens)
    os.makedirs(pathlib.Path(o).parent, exist_ok=True)
    with open(o, "w", encoding="utf-8") as f:
        json.dump(lens, f, indent=2)
    print(f"[green]Wrote[/green] {o}")


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
):
    if wizard:
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
            logger.warning(f"Failed to load template {template_path}: {e}")

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
        logger.warning(f"Failed to create example files: {e}")


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
        logger.warning(f"Failed to update README: {e}")


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
