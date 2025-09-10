import argparse
import json
import os
import pathlib
import subprocess
import sys
import shutil

from cli.ucli.analyzers.python_analyzer import build_python_map
from cli.ucli.lens.lens import (
    lens_from_seeds,
    merge_trace_into_lens,
    write_tour_md,
    rank_by_error_proximity,
)
from cli.ucli.trace.pytrace import run_callable_with_trace
from cli.ucli.dashboard.build import build_dashboard
from cli.ucli.contracts.contracts import (
    compose as contracts_compose,
    lean_stubs as contracts_lean_stubs,
    verify_lean as contracts_verify_lean,
    from_openapi as contracts_from_openapi,
    from_proto as contracts_from_proto,
)


def cmd_doctor(ns: argparse.Namespace) -> int:
    problems: list[str] = []
    notes: list[str] = []

    def ok(msg: str):
        print(f"OK {msg}")

    def warn(msg: str, fix: str | None = None):
        print(f"WARN {msg}")
        if fix:
            notes.append(f"- {msg} → {fix}")

    def fail(msg: str, fix: str | None = None):
        print(f"FAIL {msg}")
        problems.append(msg)
        if fix:
            notes.append(f"- {msg} → {fix}")

    ok(f"Python {sys.version.split()[0]}")

    try:
        r = subprocess.run(
            ["node", "-v"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
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
            "Node not found in PATH",
            "Install Node 18+ or use Devcontainer/Codespaces",
        )

    def can_bind(port: int) -> bool:
        import socket as _socket

        try:
            s = _socket.socket()
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

    doc_url = "https://github.com/your-org/understand-first#readme"
    for n in notes:
        print(n)
    if problems:
        print(f"See docs: {doc_url}")
        return 1
    print(doc_url)
    return 0


def cmd_demo(ns: argparse.Namespace) -> int:
    try:
        from cli.ucli.contracts.contracts import from_openapi  # lazy import

        txt = from_openapi("examples/apis/petstore-mini.yaml")
        os.makedirs("contracts", exist_ok=True)
        open("contracts/contracts_from_openapi.yaml", "w", encoding="utf-8").write(txt)
    except Exception:
        pass

    http_proc = subprocess.Popen([sys.executable, "examples/servers/http_server.py"])  # nosec
    try:
        os.makedirs("traces", exist_ok=True)
        data = run_callable_with_trace("examples/app/hot_path.py", "run_hot_path")
        open(
            "traces/tour.json",
            "w",
            encoding="utf-8",
        ).write(json.dumps(data, indent=2))

        os.makedirs("maps", exist_ok=True)
        repo_map = build_python_map(pathlib.Path("examples/python_toy"))
        open(
            "maps/repo.json",
            "w",
            encoding="utf-8",
        ).write(json.dumps(repo_map, indent=2))
        lens = lens_from_seeds(["compute"], repo_map)
        merged = merge_trace_into_lens(lens, data)
        rank_by_error_proximity(merged)
        open(
            "maps/lens_merged.json",
            "w",
            encoding="utf-8",
        ).write(json.dumps(merged, indent=2))

        os.makedirs("tours", exist_ok=True)
        open(
            "tours/demo.md",
            "w",
            encoding="utf-8",
        ).write(write_tour_md(merged))
        os.makedirs("docs", exist_ok=True)
        open(
            "docs/understanding-dashboard.md",
            "w",
            encoding="utf-8",
        ).write(
            build_dashboard(
                {
                    "repo": "maps/repo.json",
                    "lens": "maps/lens_merged.json",
                    "bounds": "maps/boundaries.json",
                }
            )
        )

        url = f"file://{pathlib.Path('tours/demo.md').resolve()}"
        print(url)
        return 0
    finally:
        http_proc.terminate()


def cmd_init(ns: argparse.Namespace) -> int:
    """Initialize Understand-First configuration"""
    if ns.wizard:
        # Import and run the wizard from the CLI module
        try:
            from cli.ucli.main import _run_config_wizard

            _run_config_wizard()
            return 0
        except Exception as e:
            print(f"Error running configuration wizard: {e}")
            return 1
    else:
        print("Use --wizard flag to run the interactive configuration wizard")
        print("Example: u init --wizard")
        return 0


def cmd_scan(ns: argparse.Namespace) -> int:
    root = pathlib.Path(ns.path)
    data = build_python_map(root)
    os.makedirs(pathlib.Path(ns.output).parent, exist_ok=True)
    with open(ns.output, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Wrote {ns.output}")
    return 0


def cmd_lens_from_seeds(ns: argparse.Namespace) -> int:
    with open(ns.map, "r", encoding="utf-8") as f:
        repo_map = json.load(f)
    seeds = ns.seed or []
    lens = lens_from_seeds(seeds, repo_map)
    rank_by_error_proximity(lens)
    os.makedirs(pathlib.Path(ns.output).parent, exist_ok=True)
    with open(ns.output, "w", encoding="utf-8") as f:
        json.dump(lens, f, indent=2)
    print(f"Wrote {ns.output}")
    return 0


def cmd_lens_merge_trace(ns: argparse.Namespace) -> int:
    with open(ns.lens_json, "r", encoding="utf-8") as f:
        lens = json.load(f)
    with open(ns.trace_json, "r", encoding="utf-8") as f:
        trace = json.load(f)
    merged = merge_trace_into_lens(lens, trace)
    rank_by_error_proximity(merged)
    os.makedirs(pathlib.Path(ns.output).parent, exist_ok=True)
    with open(ns.output, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)
    print(f"Wrote {ns.output}")
    return 0


def cmd_contracts_compose(ns: argparse.Namespace) -> int:
    inputs = ns.input or []
    txt = contracts_compose(inputs)
    os.makedirs(pathlib.Path(ns.output).parent, exist_ok=True)
    with open(ns.output, "w", encoding="utf-8") as f:
        f.write(txt)
    print(f"Wrote {ns.output}")
    return 0


def cmd_contracts_lean(ns: argparse.Namespace) -> int:
    out_dir = ns.output
    os.makedirs(out_dir, exist_ok=True)
    n = contracts_lean_stubs(ns.contracts_yaml, out_dir)
    print(f"Wrote {n} Lean stub(s) to {out_dir}")
    return 0


def cmd_contracts_verify(ns: argparse.Namespace) -> int:
    data = contracts_verify_lean(ns.contracts_yaml, ns.lean_dir)
    if ns.json:
        print(json.dumps(data, indent=2))
    else:
        print(f"modules: {data.get('modules_total')}")
        print(f"functions: {data.get('functions_total')}")
        for m in data.get("missing_invariants", []):
            print(f"missing: {m}")
    return 0 if not data.get("missing_invariants") else 1


def cmd_contracts_from_openapi(ns: argparse.Namespace) -> int:
    txt = contracts_from_openapi(ns.path)
    os.makedirs(pathlib.Path(ns.output).parent, exist_ok=True)
    with open(ns.output, "w", encoding="utf-8") as f:
        f.write(txt)
    print(f"Wrote {ns.output}")
    return 0


def cmd_contracts_from_proto(ns: argparse.Namespace) -> int:
    txt = contracts_from_proto(ns.path)
    os.makedirs(pathlib.Path(ns.output).parent, exist_ok=True)
    with open(ns.output, "w", encoding="utf-8") as f:
        f.write(txt)
    print(f"Wrote {ns.output}")
    return 0


def cmd_trace_module(ns: argparse.Namespace) -> int:
    os.makedirs(pathlib.Path(ns.output).parent, exist_ok=True)
    data = run_callable_with_trace(ns.pyfile, ns.func, ns.a, ns.b)
    with open(ns.output, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Wrote {ns.output}")
    return 0


def cmd_tour(ns: argparse.Namespace) -> int:
    with open(ns.lens_json, "r", encoding="utf-8") as f:
        lens = json.load(f)
    os.makedirs(pathlib.Path(ns.output).parent, exist_ok=True)
    md = write_tour_md(lens)
    with open(ns.output, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Wrote {ns.output}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="u")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp_scan = sub.add_parser("scan")
    sp_scan.add_argument("path")
    sp_scan.add_argument("-o", "--output", default="maps/out.json")
    sp_scan.set_defaults(func=cmd_scan)

    sp_lens = sub.add_parser("lens")
    lens_sub = sp_lens.add_subparsers(dest="lens_cmd", required=True)
    sp_lens_fs = lens_sub.add_parser("from-seeds")
    sp_lens_fs.add_argument("--seed", action="append")
    sp_lens_fs.add_argument("--map", required=True)
    sp_lens_fs.add_argument("-o", "--output", default="maps/lens.json")
    sp_lens_fs.set_defaults(func=cmd_lens_from_seeds)

    sp_lens_mt = lens_sub.add_parser("merge-trace")
    sp_lens_mt.add_argument("lens_json")
    sp_lens_mt.add_argument("trace_json")
    sp_lens_mt.add_argument("-o", "--output", default="maps/lens_merged.json")
    sp_lens_mt.set_defaults(func=cmd_lens_merge_trace)

    sp_trace = sub.add_parser("trace")
    trace_sub = sp_trace.add_subparsers(dest="trace_cmd", required=True)
    sp_trace_mod = trace_sub.add_parser("module")
    sp_trace_mod.add_argument("pyfile")
    sp_trace_mod.add_argument("func")
    sp_trace_mod.add_argument("a", nargs="?")
    sp_trace_mod.add_argument("b", nargs="?")
    sp_trace_mod.add_argument("-o", "--output", default="traces/trace.json")
    sp_trace_mod.set_defaults(func=cmd_trace_module)

    sp_tour = sub.add_parser("tour")
    sp_tour.add_argument("lens_json")
    sp_tour.add_argument("-o", "--output", default="tours/tour.md")
    sp_tour.set_defaults(func=cmd_tour)

    sp_doctor = sub.add_parser("doctor")
    sp_doctor.set_defaults(func=cmd_doctor)

    sp_demo = sub.add_parser("demo")
    sp_demo.set_defaults(func=cmd_demo)

    sp_init = sub.add_parser("init")
    sp_init.add_argument(
        "--wizard", action="store_true", help="Run interactive configuration wizard"
    )
    sp_init.set_defaults(func=cmd_init)

    # Contracts group (compose, lean-stubs, verify-lean, from-openapi, from-proto)
    sp_contracts = sub.add_parser("contracts")
    contracts_sub = sp_contracts.add_subparsers(dest="contracts_cmd", required=True)

    sp_c_from_openapi = contracts_sub.add_parser("from-openapi")
    sp_c_from_openapi.add_argument("path")
    sp_c_from_openapi.add_argument(
        "-o",
        "--output",
        default="contracts/contracts_from_openapi.yaml",
    )
    sp_c_from_openapi.set_defaults(func=cmd_contracts_from_openapi)

    sp_c_from_proto = contracts_sub.add_parser("from-proto")
    sp_c_from_proto.add_argument("path")
    sp_c_from_proto.add_argument(
        "-o",
        "--output",
        default="contracts/contracts_from_proto.yaml",
    )
    sp_c_from_proto.set_defaults(func=cmd_contracts_from_proto)

    sp_c_compose = contracts_sub.add_parser("compose")
    sp_c_compose.add_argument(
        "-i",
        "--input",
        action="append",
        required=True,
    )
    sp_c_compose.add_argument(
        "-o",
        "--output",
        default="contracts/contracts.yaml",
    )
    sp_c_compose.set_defaults(func=cmd_contracts_compose)

    sp_c_lean = contracts_sub.add_parser("lean-stubs")
    sp_c_lean.add_argument("contracts_yaml")
    sp_c_lean.add_argument("-o", "--output", default="contracts/lean/")
    sp_c_lean.set_defaults(func=cmd_contracts_lean)

    sp_c_verify = contracts_sub.add_parser("verify-lean")
    sp_c_verify.add_argument("contracts_yaml")
    sp_c_verify.add_argument(
        "-l",
        "--lean-dir",
        default="contracts/lean",
    )
    sp_c_verify.add_argument("--json", action="store_true")
    sp_c_verify.set_defaults(func=cmd_contracts_verify)

    return p


def main(argv=None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)
    return ns.func(ns)


if __name__ == "__main__":
    raise SystemExit(main())
