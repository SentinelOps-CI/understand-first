"""Doctor command: environment sanity checks (extracted from main.py)."""

from __future__ import annotations

import pathlib
import shutil
import socket
import subprocess  # nosec B404  # intentional: doctor probes node -v with fixed argv
import sys

import typer
from rich import print


def run_doctor() -> None:
    problems: list[str] = []
    notes: list[str] = []

    def ok(msg: str) -> None:
        print(f"[green]OK[/green] {msg}")

    def warn(msg: str, fix: str | None = None) -> None:
        print(f"[yellow]WARN[/yellow] {msg}")
        if fix:
            notes.append(f"- {msg} → {fix}")

    def fail(msg: str, fix: str | None = None) -> None:
        print(f"[red]FAIL[/red] {msg}")
        problems.append(msg)
        if fix:
            notes.append(f"- {msg} → {fix}")

    ok(f"Python {sys.version.split()[0]}")

    node_bin = shutil.which("node")
    if node_bin:
        try:
            r = subprocess.run(  # nosec B603
                [node_bin, "-v"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
            if r.returncode == 0:
                ok(f"Node {r.stdout.strip()}")
                try:
                    from ucli.analyzers.js_ast_bridge import (
                        ast_backend_available,
                        ast_unavailable_reason,
                    )

                    if ast_backend_available():
                        ok("JS/TS AST worker ready (typescript in cli/ucli/analyzers/js_ast)")
                    else:
                        warn(
                            "JS/TS AST worker deps missing — regex fallback will be used",
                            ast_unavailable_reason() or "npm install in cli/ucli/analyzers/js_ast",
                        )
                except Exception:
                    warn(
                        "Could not probe JS/TS AST worker",
                        "npm install in cli/ucli/analyzers/js_ast",
                    )
            else:
                warn(
                    "Node not found in PATH",
                    "Install Node 18+ or use Devcontainer/Codespaces",
                )
        except OSError:
            warn("Node not found in PATH", "Install Node 18+ or use Devcontainer/Codespaces")
    else:
        warn("Node not found in PATH", "Install Node 18+ or use Devcontainer/Codespaces")

    go_bin = shutil.which("go")
    if go_bin:
        try:
            r = subprocess.run(  # nosec B603
                [go_bin, "version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
            if r.returncode == 0:
                ok(f"Go {r.stdout.strip()}")
                try:
                    from ucli.analyzers.go_ast_bridge import (
                        ast_backend_available as go_ast_available,
                    )
                    from ucli.analyzers.go_ast_bridge import (
                        ast_unavailable_reason as go_ast_unavailable_reason,
                    )

                    if go_ast_available():
                        ok("Go AST worker ready (go run cli/ucli/analyzers/go_ast)")
                    else:
                        warn(
                            "Go AST worker not ready — regex fallback will be used",
                            go_ast_unavailable_reason() or "Install Go 1.21+",
                        )
                except Exception:
                    warn("Could not probe Go AST worker", "Install Go 1.21+")
            else:
                warn("Go not usable", "Install Go 1.21+ for go-ast maps")
        except OSError:
            warn("Go not found in PATH", "Install Go 1.21+ for go-ast maps")
    else:
        warn("Go not found in PATH", "Install Go 1.21+ for go-ast maps (regex fallback otherwise)")

    cargo_bin = shutil.which("cargo")
    if cargo_bin:
        try:
            from ucli.analyzers.rust_ast_bridge import (
                ast_backend_available as rust_ast_available,
            )
            from ucli.analyzers.rust_ast_bridge import (
                ast_unavailable_reason as rust_ast_unavailable_reason,
            )

            if rust_ast_available():
                ok("Rust AST worker ready (cargo + cli/ucli/analyzers/rust_ast)")
            else:
                warn(
                    "Rust AST worker not ready — regex fallback will be used",
                    rust_ast_unavailable_reason() or "Install Rust/cargo",
                )
        except Exception:
            warn("Could not probe Rust AST worker", "Install Rust/cargo")
    else:
        warn(
            "cargo not found on PATH",
            "Install Rust 1.70+ for rust-ast maps (regex fallback otherwise)",
        )

    try:
        from ucli.analyzers.java_analyzer import javalang_available

        if javalang_available():
            ok("javalang available (java-ast path)")
        else:
            warn(
                "javalang not installed — Java scans use regex best-effort",
                "pip install javalang or understand-first[analyzers]",
            )
    except Exception:
        warn("Could not probe javalang", "pip install javalang")

    dotnet_bin = shutil.which("dotnet")
    if dotnet_bin:
        try:
            from ucli.analyzers.csharp_ast_bridge import (
                ast_backend_available as csharp_ast_available,
            )
            from ucli.analyzers.csharp_ast_bridge import (
                ast_unavailable_reason as csharp_ast_unavailable_reason,
            )

            if csharp_ast_available():
                ok("C# AST worker ready (dotnet SDK + cli/ucli/analyzers/csharp_ast)")
            else:
                warn(
                    "C# AST worker not ready — regex fallback will be used",
                    csharp_ast_unavailable_reason() or "Install .NET SDK 8+",
                )
        except Exception:
            warn("Could not probe C# AST worker", "Install .NET SDK 8+")
    else:
        warn(
            "dotnet not found on PATH",
            "Install .NET SDK 8+ for csharp-ast maps (regex fallback otherwise)",
        )

    try:
        import grpc_tools  # noqa: F401
    except ImportError:
        fail("grpc_tools missing", "pip install grpcio-tools")
    else:
        ok("grpc_tools available")

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
    doc_url = "https://github.com/SentinelOps-CI/understand-first#readme"
    for n in notes:
        print(n)
    if problems:
        print(f"\nSee docs: {doc_url}")
        raise typer.Exit(code=1) from None
    print("All checks passed. See docs for advanced setup:")
    print(doc_url)
