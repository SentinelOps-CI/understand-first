"""Wave 8: lens/tour/contracts/doctor extraction, from-import modules, class qnames."""

from __future__ import annotations

import pathlib

from cli.ucli.analyzers.python_analyzer import build_python_map


def test_commands_wave8_modules_exist():
    root = pathlib.Path("cli/ucli/commands")
    for name in ("lens_ops.py", "tour_ops.py", "contracts_ops.py", "doctor_ops.py"):
        assert (root / name).is_file()
    main = pathlib.Path("cli/ucli/main.py").read_text(encoding="utf-8")
    groups = pathlib.Path("cli/ucli/commands/typer_groups.py").read_text(encoding="utf-8")
    wiring = main + "\n" + groups
    assert "from ucli.commands.tour_ops import" in wiring
    assert "from ucli.commands.doctor_ops import" in wiring
    assert (
        "from ucli.commands.contracts_ops import" in groups
        or "from ucli.commands.contracts_ops import" in main
    )
    assert (
        "from ucli.commands.lens_ops import" in groups
        or "from ucli.commands.lens_ops import" in main
    )
    assert "def run_lens_from_seeds(" not in main
    assert "def run_tour_gate(" not in main
    assert "def run_contracts_init(" not in main
    assert "def run_doctor(" not in main
    # Measurable shrink vs Wave 7 (~1099 lines): keep under 750.
    assert len(main.splitlines()) < 750


def test_from_import_module_attribute_resolution(tmp_path: pathlib.Path):
    """from pkg import util; util.helper() resolves when util is a scanned module."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "util.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
    (tmp_path / "app.py").write_text(
        "from pkg import util\n\ndef main():\n    return util.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    helper_qn = next(k for k in repo["functions"] if k.endswith("util:helper"))
    main_qn = next(k for k in repo["functions"] if k.endswith("app:main"))
    assert main_qn in repo["functions"][helper_qn]["callers"]
    assert helper_qn in repo["functions"][main_qn]["calls"]


def test_from_import_symbol_attr_does_not_invent_module_edge(tmp_path: pathlib.Path):
    """from pkg import helper (a function) then helper.fn() must not invent edges."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "mod.py").write_text(
        "def helper():\n    return 1\n\ndef fn():\n    return 2\n",
        encoding="utf-8",
    )
    (tmp_path / "app.py").write_text(
        "from pkg.mod import helper\n\ndef main():\n    return helper.fn()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    main_qn = next(k for k in repo["functions"] if k.endswith("app:main"))
    # Attribute form stays unresolved — no fan-out to pkg.mod:fn.
    assert repo["functions"][main_qn]["calls"] == ["helper.fn"]
    fn_qn = next(k for k in repo["functions"] if k.endswith("mod:fn"))
    assert main_qn not in repo["functions"][fn_qn]["callers"]


def test_nested_attr_via_import_alias_high_confidence(tmp_path: pathlib.Path):
    """import pkg; pkg.util.helper() resolves only when uniquely matched."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "util.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
    (tmp_path / "app.py").write_text(
        "import pkg\n\ndef main():\n    return pkg.util.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    helper_qn = next(k for k in repo["functions"] if k.endswith("util:helper"))
    main_qn = next(k for k in repo["functions"] if k.endswith("app:main"))
    assert main_qn in repo["functions"][helper_qn]["callers"]
    assert helper_qn in repo["functions"][main_qn]["calls"]


def test_class_method_qnames_and_self_calls(tmp_path: pathlib.Path):
    """Methods use Class.method local names; self.method resolves same-file uniquely."""
    (tmp_path / "klass.py").write_text(
        "class Foo:\n"
        "    def helper(self):\n"
        "        return 1\n"
        "\n"
        "    def run(self):\n"
        "        return self.helper()\n"
        "\n"
        "def top():\n"
        "    return 0\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    helper_qn = next(k for k in repo["functions"] if k.endswith(":Foo.helper"))
    run_qn = next(k for k in repo["functions"] if k.endswith(":Foo.run"))
    top_qn = next(k for k in repo["functions"] if k.endswith(":top"))
    assert repo["functions"][helper_qn]["simple_name"] == "helper"
    assert repo["functions"][top_qn]["simple_name"] == "top"
    assert run_qn in repo["functions"][helper_qn]["callers"]
    assert helper_qn in repo["functions"][run_qn]["calls"]


def test_ambiguous_same_file_method_basename_omits_edge(tmp_path: pathlib.Path):
    """Two classes with helper(): bare helper() / ambiguous self must not fan out."""
    (tmp_path / "multi.py").write_text(
        "class A:\n"
        "    def helper(self):\n"
        "        return 1\n"
        "\n"
        "class B:\n"
        "    def helper(self):\n"
        "        return 2\n"
        "\n"
        "def run(obj):\n"
        "    return obj.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    run_qn = next(k for k in repo["functions"] if k.endswith(":run"))
    assert repo["functions"][run_qn]["calls"] == ["obj.helper"]
    for qn, meta in repo["functions"].items():
        if qn.endswith(".helper"):
            assert run_qn not in meta.get("callers", [])


def test_nested_function_inside_method_does_not_collide(tmp_path: pathlib.Path):
    """Nested defs under methods get Enclosing.nested names, not Class.nested."""
    (tmp_path / "nest.py").write_text(
        "class Foo:\n"
        "    def run(self):\n"
        "        def helper():\n"
        "            return 1\n"
        "        return helper()\n"
        "\n"
        "    def helper(self):\n"
        "        return 2\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    keys = list(repo["functions"])
    assert any(k.endswith(":Foo.helper") for k in keys)
    assert any(k.endswith(":Foo.run.helper") for k in keys)
    run_qn = next(k for k in keys if k.endswith(":Foo.run"))
    nested_qn = next(k for k in keys if k.endswith(":Foo.run.helper"))
    assert nested_qn in repo["functions"][run_qn]["calls"]


def test_web_demo_export_stub_disabled():
    """Wave 15: export chrome removed entirely (prefer deletion over disabled stubs)."""
    html = pathlib.Path("web_demo/index.html").read_text(encoding="utf-8")
    assert "Export (disabled)" not in html
    assert "Export (stub)" not in html
    assert 'id="exportBtn"' not in html
    assert "u pack" in html or "u tour" in html
    assert "not" in html.lower() and ("pack" in html.lower() or "tour" in html.lower())
