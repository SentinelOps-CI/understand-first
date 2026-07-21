"""Map / report / glossary / dashboard / ttu / config helpers (extracted from main)."""

from __future__ import annotations

import json
import os
import pathlib

import typer
from rich import print
from rich.console import Console

from ucli.config import validate_config_dict
from ucli.dashboard.build import build_dashboard
from ucli.glossary.build import build_glossary
from ucli.graph.graph import write_dot
from ucli.metrics.ttu import record as ttu_record
from ucli.metrics.ttu import weekly_report as ttu_weekly
from ucli.report.report import make_report_md


def run_map(json_path: str, o: str) -> None:
    """Generate DOT graph visualization from analysis results."""
    console = Console()
    try:
        if not pathlib.Path(json_path).exists():
            console.print(f"[red]Error:[/red] File '{json_path}' does not exist")
            raise typer.Exit(1) from None

        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)

        os.makedirs(o, exist_ok=True)
        dot_path = os.path.join(o, pathlib.Path(json_path).stem + ".dot")
        write_dot(data, dot_path)
        console.print(f"[green]Wrote[/green] {dot_path}")
    except typer.Exit:
        raise
    except Exception as e:
        console.print(f"[red]Error generating map:[/red] {str(e)}")
        raise typer.Exit(1) from None


def run_report(json_path: str, o: str) -> None:
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    os.makedirs(o, exist_ok=True)
    md_path = os.path.join(o, pathlib.Path(json_path).stem + ".md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(make_report_md(data))
    print(f"[green]Wrote[/green] {md_path}")


def run_glossary(o: str) -> None:
    parent = os.path.dirname(o)
    if parent:
        os.makedirs(parent, exist_ok=True)
    md = build_glossary(".")
    with open(o, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"[green]Wrote[/green] {o}")


def run_dashboard(repo: str, lens: str, bounds: str, o: str) -> None:
    parent = os.path.dirname(o)
    if parent:
        os.makedirs(parent, exist_ok=True)
    md = build_dashboard({"repo": repo, "lens": lens, "bounds": bounds})
    with open(o, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"[green]Wrote[/green] {o}")


def run_ttu(event: str, o: str) -> None:
    if event == "report":
        ttu_weekly(o)
        print(f"[green]Wrote[/green] {o}")
    else:
        ttu_record(event)
        print(f"[green]Recorded[/green] {event}")


def run_config_validate(path: str) -> None:
    if not os.path.exists(path):
        print(f"[yellow]No config found at {path}[/yellow]")
        raise typer.Exit(code=1) from None
    import yaml as _yaml

    try:
        data = _yaml.safe_load(open(path, encoding="utf-8")) or {}
    except Exception as e:
        print(f"[red]YAML error:[/red] {e}")
        raise typer.Exit(code=1) from None
    errors = validate_config_dict(data)
    if errors:
        print("[red]Config errors:[/red]")
        for e in errors:
            print(f"- {e}")
        raise typer.Exit(code=1) from None
    print("[green]Config OK[/green]")
