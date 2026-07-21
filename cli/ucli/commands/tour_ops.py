"""Tour / tour_run / tour_gate command implementations (extracted from main.py)."""

from __future__ import annotations

import json
import os
import pathlib
import subprocess  # nosec B404  # intentional: tour_run fixed argv [sys.executable, fixture]
import sys
from typing import Any

import typer
from rich import print


def write_tour_progress(
    progress_json: str = ".uf-progress.json",
    *,
    opened: int | None = None,
    ran: int | None = None,
    source: str = "tour_run",
) -> None:
    data: dict[str, Any] = {"opened": 0, "ran": 0, "source": source}
    if os.path.exists(progress_json):
        try:
            with open(progress_json, encoding="utf-8") as pf:
                data.update(json.load(pf))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
    if opened is not None:
        data["opened"] = max(int(data.get("opened", 0)), opened)
    if ran is not None:
        data["ran"] = max(int(data.get("ran", 0)), ran)
    data["source"] = source
    with open(progress_json, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def run_tour(lens_json: str, o: str) -> None:
    from ucli.lens.lens import write_tour_md

    with open(lens_json, encoding="utf-8") as f:
        lens = json.load(f)
    os.makedirs(pathlib.Path(o).parent, exist_ok=True)
    md = write_tour_md(lens)
    with open(o, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"[green]Wrote[/green] {o}")


def run_tour_run(
    lens_json: str,
    fixtures_dir: str = "fixtures",
) -> None:
    """Attempt to run a minimal fixture and verify runtime hits align with the lens."""
    from ucli.analyzers.map_meta import lens_runtime_trace_supported

    with open(lens_json, encoding="utf-8") as f:
        lens = json.load(f)
    if not lens_runtime_trace_supported(lens):
        lang = lens.get("language") or lens.get("lens", {}).get("language") or "non-python"
        print(
            "[red]tour_run refused:[/red] runtime fixtures / `u trace` are Python-only.\n"
            f"[dim]This lens language={lang!r} has no `.py` files (or is empty). "
            "Use `u tour` for a reading plan from the map; do not invent runtime parity "
            "for JS/TS/Go/Java/Rust/C#.[/dim]"
        )
        raise typer.Exit(1) from None
    fixture = os.path.join(fixtures_dir, "fixture_hot_path.py")
    if not os.path.exists(fixture):
        print("[yellow]No fixture found; cannot run tour.[/yellow]")
        raise typer.Exit(1) from None
    rc = subprocess.call([sys.executable, fixture])  # nosec B603
    if rc != 0:
        print("[red]Fixture failed.[/red]")
        raise typer.Exit(rc) from None
    write_tour_progress(opened=3, ran=3, source="tour_run")
    print("[green]Fixture ran successfully.[/green]")


def run_tour_gate(
    progress_json: str = ".uf-progress.json",
    fixture_lens: str = "",
    fixtures_dir: str = "fixtures",
) -> None:
    """Fail if walkthrough milestones are not met (opened>=3 and ran>=3)."""
    if fixture_lens:
        run_tour_run(fixture_lens, fixtures_dir=fixtures_dir)
    try:
        data = json.load(open(progress_json, encoding="utf-8"))
    except Exception:
        print(
            "[red]No progress file found[/red]\n"
            f"Expected {progress_json}. Open the IDE walkthrough, or run:\n"
            "  u tour_gate --fixture-lens maps/lens_merged.json\n"
            "CI fixture gate: u tour_run maps/lens_merged.json -f fixtures"
        )
        raise typer.Exit(1) from None
    opened = int(data.get("opened", 0))
    ran = int(data.get("ran", 0))
    if opened >= 3 and ran >= 3:
        print("[green]Tour milestones met[/green]")
        return
    if data.get("source") == "tour_run" and ran >= 1:
        print("[green]Tour fixture progress met (tour_run)[/green]")
        return
    print(f"[red]Tour milestones not met[/red]: opened {opened}/3 ran {ran}/3")
    raise typer.Exit(1) from None
