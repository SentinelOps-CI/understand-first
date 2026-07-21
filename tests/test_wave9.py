"""Wave 9: remaining CLI extractions, typed attr resolution, lens exact, trace harden."""

from __future__ import annotations

import pathlib

from cli.ucli.analyzers.python_analyzer import build_python_map
from cli.ucli.lens.lens import lens_from_seeds
from cli.ucli.trace.pytrace import run_callable_with_trace


def test_commands_wave9_modules_exist():
    root = pathlib.Path("cli/ucli/commands")
    for name in (
        "trace_ops.py",
        "pack_ops.py",
        "visual_ops.py",
        "report_ops.py",
    ):
        assert (root / name).is_file()
    main = pathlib.Path("cli/ucli/main.py").read_text(encoding="utf-8")
    groups = pathlib.Path("cli/ucli/commands/typer_groups.py").read_text(encoding="utf-8")
    wiring = main + "\n" + groups
    assert "from ucli.commands.report_ops import" in wiring
    assert (
        "from ucli.commands.trace_ops import" in groups
        or "from ucli.commands.trace_ops import" in main
    )
    assert (
        "from ucli.commands.pack_ops import" in groups
        or "from ucli.commands.pack_ops import" in main
    )
    assert (
        "from ucli.commands.visual_ops import" in groups
        or "from ucli.commands.visual_ops import" in main
    )
    assert "def run_trace_module(" not in main
    assert "def run_pack_create(" not in main
    assert "def run_visual_delta(" not in main
    assert "def run_metrics(" not in main
    # Measurable shrink vs Wave 8 (~669 lines): keep under 580.
    assert len(main.splitlines()) < 580


def test_self_method_resolves_with_ambiguous_sibling_classes(tmp_path: pathlib.Path):
    """self.helper inside Foo must bind Foo.helper even when Bar.helper also exists."""
    (tmp_path / "multi.py").write_text(
        "class Foo:\n"
        "    def helper(self):\n"
        "        return 1\n"
        "\n"
        "    def run(self):\n"
        "        return self.helper()\n"
        "\n"
        "class Bar:\n"
        "    def helper(self):\n"
        "        return 2\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    foo_helper = next(k for k in repo["functions"] if k.endswith(":Foo.helper"))
    bar_helper = next(k for k in repo["functions"] if k.endswith(":Bar.helper"))
    run_qn = next(k for k in repo["functions"] if k.endswith(":Foo.run"))
    assert run_qn in repo["functions"][foo_helper]["callers"]
    assert foo_helper in repo["functions"][run_qn]["calls"]
    assert run_qn not in repo["functions"][bar_helper]["callers"]


def test_constructor_bound_obj_method_resolves(tmp_path: pathlib.Path):
    """obj = Foo(); obj.helper() resolves when Foo.helper is unique for that class."""
    (tmp_path / "ctor.py").write_text(
        "class Foo:\n"
        "    def helper(self):\n"
        "        return 1\n"
        "\n"
        "class Bar:\n"
        "    def helper(self):\n"
        "        return 2\n"
        "\n"
        "def run():\n"
        "    obj = Foo()\n"
        "    return obj.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    foo_helper = next(k for k in repo["functions"] if k.endswith(":Foo.helper"))
    bar_helper = next(k for k in repo["functions"] if k.endswith(":Bar.helper"))
    run_qn = next(k for k in repo["functions"] if k.endswith(":run"))
    assert foo_helper in repo["functions"][run_qn]["calls"]
    assert run_qn in repo["functions"][foo_helper]["callers"]
    assert run_qn not in repo["functions"][bar_helper]["callers"]


def test_annotation_bound_obj_method_resolves(tmp_path: pathlib.Path):
    """obj: Foo; obj.method() resolves; untyped obj always omits (even if unique)."""
    (tmp_path / "ann.py").write_text(
        "class Foo:\n"
        "    def helper(self):\n"
        "        return 1\n"
        "\n"
        "class Bar:\n"
        "    def helper(self):\n"
        "        return 2\n"
        "\n"
        "def typed(obj: Foo):\n"
        "    return obj.helper()\n"
        "\n"
        "def untyped(obj):\n"
        "    return obj.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    foo_helper = next(k for k in repo["functions"] if k.endswith(":Foo.helper"))
    typed_qn = next(k for k in repo["functions"] if k.endswith(":typed"))
    untyped_qn = next(k for k in repo["functions"] if k.endswith(":untyped"))
    assert foo_helper in repo["functions"][typed_qn]["calls"]
    assert repo["functions"][untyped_qn]["calls"] == ["obj.helper"]
    assert untyped_qn not in repo["functions"][foo_helper]["callers"]


def test_ambiguous_union_annotation_does_not_invent_edge(tmp_path: pathlib.Path):
    """obj: Foo | Bar must not invent a helper edge."""
    (tmp_path / "union.py").write_text(
        "class Foo:\n"
        "    def helper(self):\n"
        "        return 1\n"
        "\n"
        "class Bar:\n"
        "    def helper(self):\n"
        "        return 2\n"
        "\n"
        "def run(obj: Foo | Bar):\n"
        "    return obj.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    run_qn = next(k for k in repo["functions"] if k.endswith(":run"))
    assert repo["functions"][run_qn]["calls"] == ["obj.helper"]
    for qn, meta in repo["functions"].items():
        if qn.endswith(".helper"):
            assert run_qn not in meta.get("callers", [])


def test_lens_exact_match_vs_substring():
    repo = {
        "functions": {
            "a.py:run": {"calls": [], "simple_name": "run"},
            "a.py:runner": {"calls": [], "simple_name": "runner"},
            "a.py:Foo.run": {"calls": [], "simple_name": "run"},
        }
    }
    sub = lens_from_seeds(["run"], repo, hops=0)
    assert set(sub["functions"]) == {"a.py:run", "a.py:runner", "a.py:Foo.run"}
    exact = lens_from_seeds(["run"], repo, hops=0, exact=True)
    assert set(exact["functions"]) == {"a.py:run", "a.py:Foo.run"}
    assert exact["lens"]["exact_match"] is True
    by_qname = lens_from_seeds(["a.py:Foo.run"], repo, hops=0, exact=True)
    assert set(by_qname["functions"]) == {"a.py:Foo.run"}


def test_trace_denylist_and_bad_func_name(tmp_path: pathlib.Path, monkeypatch):
    mod = tmp_path / "ok.py"
    mod.write_text("def safe():\n    return 1\n\ndef eval():\n    return 0\n", encoding="utf-8")
    monkeypatch.setenv("UF_TRACE_ALLOW_ROOTS", str(tmp_path))
    denied = run_callable_with_trace(str(mod), "eval")
    assert (
        "denylist" in (denied.get("error") or "").lower()
        or "refused" in (denied.get("error") or "").lower()
    )
    bad = run_callable_with_trace(str(mod), "os.system")
    assert "refused" in (bad.get("error") or "").lower()
    ok = run_callable_with_trace(str(mod), "safe")
    assert not ok.get("error")
    assert any(e.get("func") == "safe" for e in ok.get("events", []))


def test_schema_documents_simple_name_and_class_qnames():
    schema = pathlib.Path("schemas/map-schema.json").read_text(encoding="utf-8")
    assert "simple_name" in schema
    assert "Class.method" in schema
    ref = pathlib.Path("schemas/SCHEMA_REFERENCE.md").read_text(encoding="utf-8")
    assert "simple_name" in ref
    assert "Class.method" in ref or "Foo.run" in ref
    assert "--exact" in ref or "exact" in ref.lower()
    sec = pathlib.Path("docs/SECURITY.md").read_text(encoding="utf-8")
    assert "Residual risk" in sec
    assert "denylist" in sec.lower() or "Job Object" in sec
