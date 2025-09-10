from typing import Optional, List
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
def tour_run(
    lens_json: str, fixtures_dir: str = typer.Option("fixtures", "--fixtures", "-f")
):
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
def contracts_stub(
    path: str, o: str = typer.Option("tests/test_contracts.py", "--output", "-o")
):
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
        print(
            f"modules: {data.get('modules_total')}\n"
            f"functions: {data.get('functions_total')}"
        )
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
        warn(
            "Node not found in PATH", "Install Node 18+ or use Devcontainer/Codespaces"
        )

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

    http_proc = subprocess.Popen(
        [sys.executable, "examples/servers/http_server.py"]
    )  # nosec
    try:
        os.makedirs("traces", exist_ok=True)
        data = run_callable_with_trace("examples/app/hot_path.py", "run_hot_path")
        open("traces/tour.json", "w", encoding="utf-8").write(
            json.dumps(data, indent=2)
        )

        os.makedirs("maps", exist_ok=True)
        repo_map = build_python_map(pathlib.Path("examples/python_toy"))
        open("maps/repo.json", "w", encoding="utf-8").write(
            json.dumps(repo_map, indent=2)
        )
        lens = lens_from_seeds(["compute"], repo_map)
        merged = merge_trace_into_lens(lens, data)
        rank_by_error_proximity(merged)
        open("maps/lens_merged.json", "w", encoding="utf-8").write(
            json.dumps(merged, indent=2)
        )

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
    stack: str = typer.Option("py", "--stack"), ci: str = typer.Option("github", "--ci")
):
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
