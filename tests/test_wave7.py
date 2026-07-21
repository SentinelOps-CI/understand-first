"""Wave 7: wizard/ci extraction, attribute-call resolution, web honesty, B404 nosec."""

from __future__ import annotations

import json
import pathlib
import sqlite3
from datetime import datetime

from cli.ucli.analyzers.python_analyzer import build_python_map
from cli.ucli.commands.ci_ops import generate_ci_report


def test_commands_wave7_modules_exist():
    root = pathlib.Path("cli/ucli/commands")
    for name in ("ci_ops.py", "wizard_ops.py"):
        assert (root / name).is_file()
    main = pathlib.Path("cli/ucli/main.py").read_text(encoding="utf-8")
    groups = pathlib.Path("cli/ucli/commands/typer_groups.py").read_text(encoding="utf-8")
    wiring = main + "\n" + groups
    assert "from ucli.commands.ci_ops import run_ci" in wiring
    assert "from ucli.commands.wizard_ops import run_wizard" in wiring
    assert "def run_ci(" not in main
    assert "def run_wizard(" not in main
    assert "def generate_ci_report(" not in main
    # Measurable shrink vs Wave 6 (~1370 lines): keep under 1200.
    assert len(main.splitlines()) < 1200


def test_attribute_call_via_import_module(tmp_path: pathlib.Path):
    """import util; util.helper() resolves when uniquely matched."""
    (tmp_path / "util.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
    (tmp_path / "app.py").write_text(
        "import util\n\ndef main():\n    return util.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    helper_qn = next(k for k in repo["functions"] if k.endswith("util:helper"))
    main_qn = next(k for k in repo["functions"] if k.endswith("app:main"))
    assert main_qn in repo["functions"][helper_qn]["callers"]
    assert helper_qn in repo["functions"][main_qn]["calls"]


def test_attribute_call_via_import_as(tmp_path: pathlib.Path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "pkg" / "util.py").write_text("def helper():\n    return 2\n", encoding="utf-8")
    (tmp_path / "app.py").write_text(
        "import pkg.util as u\n\ndef main():\n    return u.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    helper_qn = next(k for k in repo["functions"] if k.endswith("util:helper"))
    main_qn = next(k for k in repo["functions"] if k.endswith("app:main"))
    assert main_qn in repo["functions"][helper_qn]["callers"]
    assert helper_qn in repo["functions"][main_qn]["calls"]


def test_ambiguous_attribute_does_not_invent_edges(tmp_path: pathlib.Path):
    """Two helpers named helper under different modules: omit when import cannot disambiguate."""
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "m.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
    (b / "m.py").write_text("def helper():\n    return 2\n", encoding="utf-8")
    # Object attribute with no import binding — must not fan out to both helpers.
    (tmp_path / "caller.py").write_text(
        "def main(obj):\n    return obj.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    main_qn = next(k for k in repo["functions"] if k.endswith("caller:main"))
    assert repo["functions"][main_qn]["calls"] == ["obj.helper"]
    for qn, meta in repo["functions"].items():
        if qn.endswith(":helper"):
            assert main_qn not in meta.get("callers", [])


def test_self_method_same_file_attribute(tmp_path: pathlib.Path):
    """Unbound self outside a class refuses same-file basename guess (honesty)."""
    (tmp_path / "klass.py").write_text(
        "def helper():\n    return 1\n\ndef run():\n    return self.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    helper_qn = next(k for k in repo["functions"] if k.endswith(":helper"))
    run_qn = next(k for k in repo["functions"] if k.endswith(":run"))
    assert repo["functions"][run_qn]["calls"] == ["self.helper"]
    assert run_qn not in repo["functions"][helper_qn]["callers"]


def test_generate_ci_report_from_ops():
    repo = {
        "functions": {
            "a:f": {"complexity": 2, "side_effects": []},
            "a:g": {"complexity": 12, "side_effects": ["io"]},
        }
    }
    lens = {"lens": {"seeds": ["a:f"]}, "functions": {"a:f": {}}}
    md = generate_ci_report(repo, lens, ".")
    assert "Functions Analyzed**: 2" in md
    assert "High Complexity Functions**: 1" in md


def test_dashboard_datetime_adapter_registered():
    """SQLite accepts datetime via explicit adapter (no 3.12 default-adapter deprecation)."""
    import sys

    dash_dir = str(pathlib.Path("dashboard").resolve())
    if dash_dir not in sys.path:
        sys.path.insert(0, dash_dir)
    import context_debt_dashboard  # noqa: F401 — registers adapter on import

    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t (ts TEXT)")
    conn.execute("INSERT INTO t (ts) VALUES (?)", (datetime(2024, 1, 2, 3, 4, 5),))
    row = conn.execute("SELECT ts FROM t").fetchone()
    assert row is not None
    assert "2024-01-02" in str(row[0])
    conn.close()


def test_b404_nosec_on_intentional_subprocess_imports():
    files = [
        pathlib.Path("cli/ucli/commands/tour_ops.py"),
        pathlib.Path("cli/ucli/commands/doctor_ops.py"),
        pathlib.Path("cli/ucli/commands/demo_ops.py"),
        pathlib.Path("cli/ucli/trace/pytrace.py"),
    ]
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "import subprocess" in text
        assert "nosec B404" in text
    # Wave 8 moved tour/doctor off main — no residual subprocess import there.
    main = pathlib.Path("cli/ucli/main.py").read_text(encoding="utf-8")
    assert "import subprocess" not in main


def test_bandit_baseline_empty_or_no_b404():
    baseline = json.loads(pathlib.Path(".bandit-baseline.json").read_text(encoding="utf-8"))
    results = baseline.get("results") or []
    b404 = [r for r in results if r.get("test_id") == "B404"]
    assert b404 == [], "B404 should be nosec'd; refresh baseline if empty"


def test_web_demo_metrics_and_export_honesty():
    """Wave 15: no metrics/export theater — demo sketch labels + CLI pack/tour pointers."""
    html = pathlib.Path("web_demo/index.html").read_text(encoding="utf-8")
    assert "demo sketch" in html.lower() or "heuristic" in html.lower()
    assert "Export (disabled)" not in html and "Export (stub)" not in html
    assert "u pack" in html or "u tour" in html
    assert "not" in html.lower() and ("u scan" in html or "CLI" in html)
