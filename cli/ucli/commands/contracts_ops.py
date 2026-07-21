"""Contracts command implementations (extracted from main.py)."""

from __future__ import annotations

import json
import os
import pathlib

import typer
from rich import print

from ucli.contracts.contracts import (
    check_contracts,
    compose,
    from_openapi,
    from_proto,
    init_contracts,
    lean_stubs,
    report_json,
    stub_tests,
    verify_lean,
)


def run_contracts_init(path: str, o: str) -> None:
    os.makedirs(pathlib.Path(o).parent, exist_ok=True)
    txt = init_contracts(path)
    with open(o, "w", encoding="utf-8") as f:
        f.write(txt)
    print(f"[green]Wrote[/green] {o}")


def run_contracts_check(path: str) -> None:
    ok, report = check_contracts(path)
    print(report)
    if not ok:
        raise typer.Exit(1) from None


def run_contracts_stub(path: str, o: str) -> None:
    os.makedirs(pathlib.Path(o).parent, exist_ok=True)
    txt = stub_tests(path)
    with open(o, "w", encoding="utf-8") as f:
        f.write(txt)
    print(f"[green]Wrote[/green] {o}")


def run_contracts_from_openapi(path: str, o: str) -> None:
    txt = from_openapi(path)
    os.makedirs(pathlib.Path(o).parent, exist_ok=True)
    with open(o, "w", encoding="utf-8") as f:
        f.write(txt)
    print(f"[green]Wrote[/green] {o}")


def run_contracts_from_proto(path: str, o: str) -> None:
    txt = from_proto(path)
    os.makedirs(pathlib.Path(o).parent, exist_ok=True)
    with open(o, "w", encoding="utf-8") as f:
        f.write(txt)
    print(f"[green]Wrote[/green] {o}")


def run_contracts_lean_stubs(contracts_yaml: str, o: str) -> None:
    os.makedirs(o, exist_ok=True)
    count = lean_stubs(contracts_yaml, o)
    print(
        f"[green]Wrote[/green] {count} Lean scaffold stub(s) to {o} "
        "(Prop := True / by trivial; not compiled)"
    )


def run_contracts_compose(inputs: list[str], o: str) -> None:
    if not inputs:
        print("[red]No input files provided[/red]")
        raise typer.Exit(1) from None
    txt = compose(inputs)
    os.makedirs(pathlib.Path(o).parent, exist_ok=True)
    with open(o, "w", encoding="utf-8") as f:
        f.write(txt)
    print(f"[green]Wrote[/green] {o}")


def run_contracts_verify_lean(
    contracts_yaml: str,
    lean_dir: str,
    *,
    json_out: bool = False,
) -> None:
    data = verify_lean(contracts_yaml, lean_dir)
    if json_out:
        print(json.dumps(data, indent=2))
    else:
        print(
            f"mode: {data.get('mode', 'presence-only')} "
            "(file presence only; does not compile Lean)\n"
            f"modules: {data.get('modules_total')}\n"
            f"functions: {data.get('functions_total')}"
        )
        missing = data.get("missing_invariants", [])
        if missing:
            print("missing invariants:")
            for m in missing:
                print(f"  - {m}")
    if data.get("missing_invariants"):
        raise typer.Exit(1) from None


def run_contracts_report(path: str, *, json_out: bool = False) -> None:
    data = report_json(path)
    if json_out:
        print(json.dumps(data, indent=2))
    else:
        for i in data.get("issues", []):
            print(
                f"[{i.get('severity', 'info')}] "
                f"{i.get('module_path')}:{i.get('function')} - {i.get('message')}"
            )
    if data.get("issues"):
        raise typer.Exit(1) from None
