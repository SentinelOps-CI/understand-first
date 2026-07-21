"""Wave 6: command extractions, relative imports, dashboard gaps, trace allowlist."""

from __future__ import annotations

import pathlib

import pytest
from cli.ucli.analyzers.python_analyzer import build_python_map
from cli.ucli.trace.pytrace import _path_is_allowed, run_callable_with_trace


def test_commands_wave6_modules_exist():
    root = pathlib.Path("cli/ucli/commands")
    for name in (
        "scan_ops.py",
        "init_ops.py",
        "metrics_ops.py",
        "diff_ops.py",
        "demo_ops.py",
        "explorer_ops.py",
    ):
        assert (root / name).is_file()
    main = pathlib.Path("cli/ucli/main.py").read_text(encoding="utf-8")
    groups = pathlib.Path("cli/ucli/commands/typer_groups.py").read_text(encoding="utf-8")
    wiring = main + "\n" + groups
    assert "from ucli.commands.demo_ops import run_demo" in wiring
    assert "from ucli.commands.diff_ops import run_diff" in wiring
    assert "from ucli.commands.explorer_ops import run_tui" in wiring
    assert "def run_demo(" not in main
    assert "def run_diff(" not in main
    assert "def show_function_list(" not in main
    # Wave 7 extracted wizard/ci; keep Wave 6 ceiling (tighter check in test_wave7).
    assert len(main.splitlines()) < 1800


def test_relative_import_cross_file_callers(tmp_path: pathlib.Path):
    pkg = tmp_path / "pkg"
    sub = pkg / "sub"
    sub.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (sub / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "util.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
    (sub / "app.py").write_text(
        "from ..util import helper\n\ndef main():\n    return helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    helper_qn = next(k for k in repo["functions"] if k.endswith("util:helper"))
    main_qn = next(k for k in repo["functions"] if k.endswith("app:main"))
    assert main_qn in repo["functions"][helper_qn]["callers"]
    assert helper_qn in repo["functions"][main_qn]["calls"]


def test_relative_import_same_package(tmp_path: pathlib.Path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "util.py").write_text("def helper():\n    return 2\n", encoding="utf-8")
    (pkg / "app.py").write_text(
        "from .util import helper\n\ndef main():\n    return helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    helper_qn = next(k for k in repo["functions"] if k.endswith("util:helper"))
    main_qn = next(k for k in repo["functions"] if k.endswith("app:main"))
    assert main_qn in repo["functions"][helper_qn]["callers"]
    assert helper_qn in repo["functions"][main_qn]["calls"]


def test_ambiguous_relative_does_not_invent_edges(tmp_path: pathlib.Path):
    """Two helpers with the same short name: omit cross-file edge without import alias."""
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "__init__.py").write_text("", encoding="utf-8")
    (b / "__init__.py").write_text("", encoding="utf-8")
    (a / "m.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
    (b / "m.py").write_text("def helper():\n    return 2\n", encoding="utf-8")
    (tmp_path / "caller.py").write_text(
        "def main():\n    return helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    main_qn = next(k for k in repo["functions"] if k.endswith("caller:main"))
    # Bare call with two global candidates and no import — stay bare, no callers fan-out.
    assert repo["functions"][main_qn]["calls"] == ["helper"]
    for qn, meta in repo["functions"].items():
        if qn.endswith(":helper"):
            assert main_qn not in meta.get("callers", [])


def test_dashboard_uses_docstring_and_type_fields(tmp_path: pathlib.Path):
    import sys

    dash_dir = str(pathlib.Path("dashboard").resolve())
    if dash_dir not in sys.path:
        sys.path.insert(0, dash_dir)
    from context_debt_dashboard import ContextDebtAnalyzer

    src = tmp_path / "m.py"
    src.write_text(
        "def bare(x):\n    return x\n\n"
        "def documented(x: int) -> int:\n"
        '    """Doc."""\n'
        "    return x\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    db = tmp_path / "debt.db"
    analyzer = ContextDebtAnalyzer(str(db))
    analyzer.analyze_codebase(repo, repository=str(tmp_path))

    metrics = analyzer._analyze_context_debt_metrics(repo)
    metric_names = {m.name for m in metrics}
    assert "Documentation Coverage" in metric_names
    assert "Type Hint Coverage" in metric_names
    doc = next(m for m in metrics if m.name == "Documentation Coverage")
    assert doc.value == 50.0  # 1 of 2 documented

    gaps = analyzer._analyze_documentation_gaps(repo)
    gap_types = {g.gap_type for g in gaps}
    assert "missing_docstring" in gap_types
    assert "missing_type_hints" in gap_types

    hotspots = analyzer._analyze_hotspots(repo)
    bare = next(h for h in hotspots if h.function_name.endswith(":bare"))
    documented = next(h for h in hotspots if h.function_name.endswith(":documented"))
    assert bare.risk_score > documented.risk_score


def test_pytrace_path_allowlist_blocks_outside(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
):
    outside = tmp_path / "outside.py"
    outside.write_text("def f():\n    return 1\n", encoding="utf-8")
    other = tmp_path / "allow_only"
    other.mkdir()
    monkeypatch.setattr(
        "cli.ucli.trace.pytrace._allow_roots",
        lambda: [other],
    )
    assert not _path_is_allowed(outside, [other])
    result = run_callable_with_trace(str(outside), "f")
    assert "refused" in (result.get("error") or "").lower()


def test_web_demo_stubs_lens_and_trace():
    """Wave 15: stubs deleted — honesty via absence + CLI pointers, not labeled theater."""
    html = pathlib.Path("web_demo/index.html").read_text(encoding="utf-8")
    assert "Lens (stub)" not in html
    assert "Trace (stub)" not in html
    assert "Save Preset (CLI only)" not in html
    assert "u scan" in html
    assert "not" in html.lower() and ("u scan" in html or "CLI" in html)
