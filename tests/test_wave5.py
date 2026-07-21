"""Wave 5 remediation: modular commands, exec isolation, AST stubs, gap metrics."""

from __future__ import annotations

import pathlib

from cli.ucli.analyzers.python_analyzer import _parse_file, build_python_map
from cli.ucli.contracts.contracts import stub_tests
from cli.ucli.trace.pytrace import run_callable_with_trace


def test_stub_tests_uses_ast_not_exec_module(tmp_path: pathlib.Path):
    mod = tmp_path / "mod.py"
    mod.write_text("def ok():\n    return 1\n", encoding="utf-8")
    contracts = tmp_path / "c.yaml"
    contracts.write_text(
        f"module: {mod.as_posix()}\nfunctions:\n  ok:\n    pre: []\n    post: []\n    side_effects: []\n",
        encoding="utf-8",
    )
    txt = stub_tests(str(contracts))
    assert "exec_module" not in txt
    assert "importlib.util" not in txt
    assert "_ast_func_names" in txt
    assert "assert 'ok' in names" in txt


def test_pytrace_subprocess_isolation(tmp_path: pathlib.Path, monkeypatch):
    """Target module runs in a child process; parent must not exec_module it."""
    mod = tmp_path / "traced.py"
    mod.write_text(
        "def add(a, b):\n    return a + b\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("UF_TRACE_ALLOW_ROOTS", str(tmp_path))
    result = run_callable_with_trace(str(mod), "add", "2", "3")
    assert "error" not in result or not result.get("error")
    assert isinstance(result.get("events"), list)
    assert any(e.get("func") == "add" for e in result["events"])


def test_pytrace_uses_subprocess_not_inprocess_exec():
    src = pathlib.Path("cli/ucli/trace/pytrace.py").read_text(encoding="utf-8")
    assert "subprocess.Popen" in src or "subprocess.run" in src
    # exec_module may exist only inside the worker script string, not as an
    # in-process call in run_callable_with_trace itself.
    after_def = src.split("def run_callable_with_trace", 1)[1]
    assert "exec_module" not in after_def
    assert "subprocess.Popen" in after_def or "subprocess.run" in after_def


def test_gap_metrics_docstring_and_types(tmp_path: pathlib.Path):
    src = tmp_path / "typed.py"
    src.write_text(
        "def bare(x):\n"
        "    return x\n"
        "\n"
        "def documented(x: int) -> int:\n"
        '    """Return x."""\n'
        "    return x\n",
        encoding="utf-8",
    )
    parsed = _parse_file(src)
    assert parsed["bare"]["has_docstring"] is False
    assert parsed["bare"]["has_type_hints"] is False
    assert parsed["documented"]["has_docstring"] is True
    assert parsed["documented"]["has_return_annotation"] is True
    assert parsed["documented"]["has_type_hints"] is True
    assert parsed["documented"]["fully_typed_params"] is True

    repo = build_python_map(tmp_path)
    bare_qn = next(k for k in repo["functions"] if k.endswith(":bare"))
    assert "has_docstring" in repo["functions"][bare_qn]
    assert repo["functions"][bare_qn]["has_docstring"] is False


def test_calls_qualified_same_file(tmp_path: pathlib.Path):
    src = tmp_path / "m.py"
    src.write_text(
        "def helper():\n    return 1\n\ndef caller():\n    return helper()\n",
        encoding="utf-8",
    )
    # Per-file parse keeps bare names
    assert "helper" in _parse_file(src)["caller"]["calls"]
    repo = build_python_map(tmp_path)
    helper_qn = next(k for k in repo["functions"] if k.endswith(":helper"))
    caller_qn = next(k for k in repo["functions"] if k.endswith(":caller"))
    assert helper_qn in repo["functions"][caller_qn]["calls"]


def test_import_alias_cross_file_callers(tmp_path: pathlib.Path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "util.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
    (pkg / "app.py").write_text(
        "from pkg.util import helper\n\ndef main():\n    return helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    helper_qn = next(k for k in repo["functions"] if k.endswith("util:helper"))
    main_qn = next(k for k in repo["functions"] if k.endswith("app:main"))
    assert main_qn in repo["functions"][helper_qn]["callers"]
    assert helper_qn in repo["functions"][main_qn]["calls"]


def test_commands_modules_exist():
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
    assert (
        "from ucli.commands.scan_ops import run_scan" in main
        or "from ucli.commands.scan_ops import run_scan" in groups
    )
    assert "from ucli.commands.init_ops import" in main or "register_top_level" in groups
    assert "def run_scan(" not in main


def test_bandit_baseline_committed_and_ci_fail_closed():
    root = pathlib.Path(__file__).resolve().parents[1]
    baseline = root / ".bandit-baseline.json"
    assert baseline.is_file(), "commit .bandit-baseline.json for fail-closed CI"
    assert "results" in baseline.read_text(encoding="utf-8")
    gitignore = (root / ".gitignore").read_text(encoding="utf-8")
    assert "!.bandit-baseline.json" in gitignore
    ci = (root / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "continue-on-error: true" not in ci.split("bandit")[1].split("Upload security")[0]
    assert "-b .bandit-baseline.json" in ci
    assert "bandit -r cli/ -lll" in ci
