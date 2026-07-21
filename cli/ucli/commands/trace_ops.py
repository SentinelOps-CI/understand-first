"""Trace command implementations (extracted from main.py)."""

from __future__ import annotations

import json
import os
import pathlib

from rich import print

from ucli.trace.pytrace import analyze_errors_static, run_callable_with_trace


def run_trace_module(
    pyfile: str,
    func: str,
    a: str | None = None,
    b: str | None = None,
    o: str = "traces/trace.json",
) -> None:
    os.makedirs(pathlib.Path(o).parent, exist_ok=True)
    data = run_callable_with_trace(pyfile, func, a, b)
    with open(o, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"[green]Wrote[/green] {o}")


def run_trace_errors(pyfile: str, *, json_out: bool = True) -> None:
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
