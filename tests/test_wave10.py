"""Wave 10: cross-file typed resolve, main thinness, annotations, trace docs/tests."""

from __future__ import annotations

import pathlib
import sys

import pytest
from cli.ucli.analyzers.python_analyzer import (
    _simple_type_name,
    build_python_map,
)
from cli.ucli.trace.pytrace import (
    _FUNC_DENYLIST,
    _validate_func_name,
    _windows_assign_job_memory_limit,
    run_callable_with_trace,
)


def test_commands_wave10_main_thin_and_groups():
    main = pathlib.Path("cli/ucli/main.py").read_text(encoding="utf-8")
    groups = pathlib.Path("cli/ucli/commands/typer_groups.py").read_text(encoding="utf-8")
    assert "from ucli.commands.typer_groups import register_all_groups" in main
    assert "register_all_groups(app)" in main
    assert "show_banner" in main or "show_banner" in groups
    assert "from ucli.commands.init_ops import" in main or "register_top_level" in groups
    assert "def show_banner(" not in main
    assert "def show_welcome_message(" not in main
    assert "def run_init(" not in main
    assert "def run_lens_from_seeds(" not in main
    assert "def run_contracts_init(" not in main
    assert pathlib.Path("cli/ucli/commands/typer_groups.py").is_file()
    # Honest shrink vs Wave 9 (~541 lines): keep under 420.
    assert len(main.splitlines()) < 420


def test_cross_file_imported_class_method_resolves(tmp_path: pathlib.Path):
    """from mod import Foo; Foo.helper() resolves when Foo uniquely maps to a class."""
    (tmp_path / "mod.py").write_text(
        "class Foo:\n"
        "    def helper(self):\n"
        "        return 1\n"
        "\n"
        "class Bar:\n"
        "    def helper(self):\n"
        "        return 2\n",
        encoding="utf-8",
    )
    (tmp_path / "app.py").write_text(
        "from mod import Foo\n\ndef run():\n    return Foo.helper(None)\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    foo_helper = next(k for k in repo["functions"] if k.endswith("mod:Foo.helper"))
    bar_helper = next(k for k in repo["functions"] if k.endswith("mod:Bar.helper"))
    run_qn = next(k for k in repo["functions"] if k.endswith("app:run"))
    assert foo_helper in repo["functions"][run_qn]["calls"]
    assert run_qn in repo["functions"][foo_helper]["callers"]
    assert run_qn not in repo["functions"][bar_helper]["callers"]


def test_cross_file_imported_ctor_obj_method_resolves(tmp_path: pathlib.Path):
    """from mod import Foo; obj = Foo(); obj.helper() — import-gated even if Bar.helper exists elsewhere."""
    (tmp_path / "mod_a.py").write_text(
        "class Foo:\n    def helper(self):\n        return 1\n",
        encoding="utf-8",
    )
    (tmp_path / "mod_b.py").write_text(
        "class Foo:\n    def helper(self):\n        return 2\n",
        encoding="utf-8",
    )
    (tmp_path / "app.py").write_text(
        "from mod_a import Foo\n\ndef run():\n    obj = Foo()\n    return obj.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    a_helper = next(k for k in repo["functions"] if "mod_a" in k and k.endswith(":Foo.helper"))
    b_helper = next(k for k in repo["functions"] if "mod_b" in k and k.endswith(":Foo.helper"))
    run_qn = next(k for k in repo["functions"] if k.endswith("app:run"))
    assert a_helper in repo["functions"][run_qn]["calls"]
    assert run_qn in repo["functions"][a_helper]["callers"]
    assert run_qn not in repo["functions"][b_helper]["callers"]


def test_cross_file_imported_annotation_obj_method_resolves(tmp_path: pathlib.Path):
    """from mod import Foo; def f(obj: Foo): obj.helper() — Optional/Union-aware annotations."""
    (tmp_path / "mod.py").write_text(
        "class Foo:\n    def helper(self):\n        return 1\n",
        encoding="utf-8",
    )
    (tmp_path / "app.py").write_text(
        "from typing import Optional\n"
        "from mod import Foo\n"
        "\n"
        "def typed(obj: Foo):\n"
        "    return obj.helper()\n"
        "\n"
        "def opt(obj: Optional[Foo]):\n"
        "    return obj.helper()\n"
        "\n"
        "def pipe(obj: Foo | None):\n"
        "    return obj.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    helper = next(k for k in repo["functions"] if k.endswith("mod:Foo.helper"))
    for name in ("typed", "opt", "pipe"):
        qn = next(k for k in repo["functions"] if k.endswith(f"app:{name}"))
        assert helper in repo["functions"][qn]["calls"], name
        assert qn in repo["functions"][helper]["callers"], name


def test_ambiguous_import_alias_does_not_invent_class_edge(tmp_path: pathlib.Path):
    """from mod import helper (function) then helper.method() must not invent edges."""
    (tmp_path / "mod.py").write_text(
        "def helper():\n    return 1\n\ndef method():\n    return 2\n",
        encoding="utf-8",
    )
    (tmp_path / "app.py").write_text(
        "from mod import helper\n\ndef run():\n    return helper.method()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    run_qn = next(k for k in repo["functions"] if k.endswith("app:run"))
    assert repo["functions"][run_qn]["calls"] == ["helper.method"]
    method_qn = next(k for k in repo["functions"] if k.endswith("mod:method"))
    assert run_qn not in repo["functions"][method_qn]["callers"]


def test_multi_class_union_annotation_still_omits(tmp_path: pathlib.Path):
    """obj: Foo | Bar across files must not invent a helper edge."""
    (tmp_path / "mod.py").write_text(
        "class Foo:\n"
        "    def helper(self):\n"
        "        return 1\n"
        "\n"
        "class Bar:\n"
        "    def helper(self):\n"
        "        return 2\n",
        encoding="utf-8",
    )
    (tmp_path / "app.py").write_text(
        "from mod import Foo, Bar\n\ndef run(obj: Foo | Bar):\n    return obj.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    run_qn = next(k for k in repo["functions"] if k.endswith("app:run"))
    assert repo["functions"][run_qn]["calls"] == ["obj.helper"]
    for qn, meta in repo["functions"].items():
        if qn.endswith(".helper"):
            assert run_qn not in meta.get("callers", [])


def test_annotation_parsing_optional_union_typeddict_gates():
    import ast

    tree = ast.parse("def f(x: Optional[Foo]):\n    pass\n")
    assert _simple_type_name(tree.body[0].args.args[0].annotation) == "Foo"

    tree = ast.parse("def f(x: Foo | None):\n    pass\n")
    assert _simple_type_name(tree.body[0].args.args[0].annotation) == "Foo"

    tree = ast.parse("def f(x: Foo | Bar):\n    pass\n")
    assert _simple_type_name(tree.body[0].args.args[0].annotation) is None

    tree = ast.parse("def f(x: list[Foo]):\n    pass\n")
    assert _simple_type_name(tree.body[0].args.args[0].annotation) is None

    tree = ast.parse("def f(x: TypedDict):\n    pass\n")
    assert _simple_type_name(tree.body[0].args.args[0].annotation) is None

    tree = ast.parse("def f(x: Union[Foo, None]):\n    pass\n")
    assert _simple_type_name(tree.body[0].args.args[0].annotation) == "Foo"


def test_usage_documents_uf_trace_allow_roots():
    usage = pathlib.Path("docs/usage.md").read_text(encoding="utf-8")
    assert "UF_TRACE_ALLOW_ROOTS" in usage
    assert "os.pathsep" in usage or "pathsep" in usage.lower()


def test_trace_denylist_covers_open_and_dunders():
    assert "open" in _FUNC_DENYLIST
    assert _validate_func_name("open") is not None
    assert _validate_func_name("__import__") is not None
    assert _validate_func_name("safe_fn") is None


def test_trace_windows_job_object_attach_best_effort(tmp_path: pathlib.Path, monkeypatch):
    """On Windows, job helper attaches a handle; elsewhere it is a no-op."""
    mod = tmp_path / "ok.py"
    mod.write_text("def safe():\n    return 1\n", encoding="utf-8")
    monkeypatch.setenv("UF_TRACE_ALLOW_ROOTS", str(tmp_path))

    if sys.platform != "win32":
        # Exercise the early-return path without a real Popen.
        class _Dummy:
            pid = 1

        _windows_assign_job_memory_limit(_Dummy())  # type: ignore[arg-type]
        pytest.skip("Windows Job Object only applies on win32")

    result = run_callable_with_trace(str(mod), "safe")
    assert not result.get("error")
    # Best-effort: either job attached during Popen path, or silent failure —
    # tracing must still succeed either way.
    assert any(e.get("func") == "safe" for e in result.get("events", []))


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX resource limits path")
def test_trace_denylist_refuses_compile_on_posix(tmp_path: pathlib.Path, monkeypatch):
    mod = tmp_path / "ok.py"
    mod.write_text("def compile():\n    return 0\n", encoding="utf-8")
    monkeypatch.setenv("UF_TRACE_ALLOW_ROOTS", str(tmp_path))
    denied = run_callable_with_trace(str(mod), "compile")
    assert (
        "denylist" in (denied.get("error") or "").lower()
        or "refused" in (denied.get("error") or "").lower()
    )
