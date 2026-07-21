"""Visual delta and boundaries scan (extracted from main.py)."""

from __future__ import annotations

import json
import os
import pathlib

from rich import print

from ucli.boundaries.scan import scan_boundaries
from ucli.visual.delta import lens_delta_svg


def run_visual_delta(old_lens: str, new_lens: str, o: str) -> None:
    svg = lens_delta_svg(old_lens, new_lens)
    os.makedirs(pathlib.Path(o).parent, exist_ok=True)
    with open(o, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"[green]Wrote[/green] {o}")


def run_boundaries_scan(path: str, o: str) -> None:
    result = scan_boundaries(path)
    os.makedirs(pathlib.Path(o).parent, exist_ok=True)
    with open(o, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"[green]Wrote[/green] {o}")
