"""Demo command: end-to-end sample artifacts (extracted from main.py)."""

from __future__ import annotations

import json
import os
import pathlib
import subprocess  # nosec B404  # intentional: demo server fixed argv, no shell
import sys

from rich import print

from ucli.analyzers.python_analyzer import build_python_map
from ucli.contracts.contracts import from_openapi
from ucli.dashboard.build import build_dashboard
from ucli.lens.lens import (
    lens_from_seeds,
    merge_trace_into_lens,
    rank_by_error_proximity,
    write_tour_md,
)
from ucli.trace.pytrace import run_callable_with_trace


def run_demo() -> None:
    """Generate sample contracts, maps, lens, tour, and dashboard artifacts."""
    try:
        txt = from_openapi("examples/apis/petstore-mini.yaml")
        os.makedirs("contracts", exist_ok=True)
        pathlib.Path("contracts/contracts_from_openapi.yaml").write_text(txt, encoding="utf-8")
    except (OSError, ValueError, TypeError, KeyError):
        # Optional OpenAPI sample may be absent in slim checkouts.
        pass

    http_proc = subprocess.Popen(  # nosec B603
        [sys.executable, "examples/servers/http_server.py"]
    )
    try:
        os.makedirs("traces", exist_ok=True)
        data = run_callable_with_trace("examples/app/hot_path.py", "run_hot_path")
        pathlib.Path("traces/tour.json").write_text(json.dumps(data, indent=2), encoding="utf-8")

        os.makedirs("maps", exist_ok=True)
        repo_map = build_python_map(pathlib.Path("examples/python_toy"))
        pathlib.Path("maps/repo.json").write_text(json.dumps(repo_map, indent=2), encoding="utf-8")
        lens = lens_from_seeds(["compute"], repo_map)
        merged = merge_trace_into_lens(lens, data)
        rank_by_error_proximity(merged)
        pathlib.Path("maps/lens_merged.json").write_text(
            json.dumps(merged, indent=2), encoding="utf-8"
        )

        os.makedirs("tours", exist_ok=True)
        pathlib.Path("tours/demo.md").write_text(write_tour_md(merged), encoding="utf-8")
        os.makedirs("docs", exist_ok=True)
        pathlib.Path("docs/understanding-dashboard.md").write_text(
            build_dashboard(
                {
                    "repo": "maps/repo.json",
                    "lens": "maps/lens_merged.json",
                    "bounds": "maps/boundaries.json",
                }
            ),
            encoding="utf-8",
        )

        url = f"file://{pathlib.Path('tours/demo.md').resolve()}"
        print(f"[green]Open tour:[/green] {url}")
    finally:
        http_proc.terminate()
