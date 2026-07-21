"""Wave 11: return-type typed resolve, import-as/relative class edges, hygiene."""

from __future__ import annotations

import pathlib

from cli.ucli.analyzers.python_analyzer import (
    _infer_return_type,
    _looks_like_class_name,
    _match_module_path,
    build_python_map,
)


def test_commands_wave11_main_and_groups():
    main = pathlib.Path("cli/ucli/main.py").read_text(encoding="utf-8")
    groups = pathlib.Path("cli/ucli/commands/typer_groups.py").read_text(encoding="utf-8")
    assert "register_all_groups(app)" in main
    assert "def register_top_level(" in groups
    assert "register_top_level(app)" in groups
    assert "def scan(" not in main
    # Keep main thin (Wave 10 was <420; Wave 11 target stays under 300).
    assert len(main.splitlines()) < 300


def test_return_type_factory_obj_method_same_file(tmp_path: pathlib.Path):
    """obj = make(); obj.helper() when make uniquely returns Foo()."""
    (tmp_path / "t.py").write_text(
        "class Foo:\n"
        "    def helper(self):\n"
        "        return 1\n"
        "\n"
        "def make():\n"
        "    return Foo()\n"
        "\n"
        "def run():\n"
        "    obj = make()\n"
        "    return obj.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    helper = next(k for k in repo["functions"] if k.endswith(":Foo.helper"))
    make_qn = next(k for k in repo["functions"] if k.endswith(":make"))
    run_qn = next(k for k in repo["functions"] if k.endswith(":run"))
    assert repo["functions"][make_qn].get("return_type") == "Foo"
    assert helper in repo["functions"][run_qn]["calls"]
    assert run_qn in repo["functions"][helper]["callers"]


def test_return_type_annotation_and_alias(tmp_path: pathlib.Path):
    """Annotation ``-> Foo`` and ``return x`` after ``x = Foo()`` both count."""
    (tmp_path / "t.py").write_text(
        "class Foo:\n"
        "    def helper(self):\n"
        "        return 1\n"
        "\n"
        "def make_ann() -> Foo:\n"
        "    return Foo()\n"
        "\n"
        "def make_alias():\n"
        "    x = Foo()\n"
        "    return x\n"
        "\n"
        "def run_ann():\n"
        "    obj = make_ann()\n"
        "    return obj.helper()\n"
        "\n"
        "def run_alias():\n"
        "    obj = make_alias()\n"
        "    return obj.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    helper = next(k for k in repo["functions"] if k.endswith(":Foo.helper"))
    for name in ("make_ann", "make_alias"):
        qn = next(k for k in repo["functions"] if k.endswith(f":{name}"))
        assert repo["functions"][qn].get("return_type") == "Foo", name
    for name in ("run_ann", "run_alias"):
        qn = next(k for k in repo["functions"] if k.endswith(f":{name}"))
        assert helper in repo["functions"][qn]["calls"], name
        assert qn in repo["functions"][helper]["callers"], name


def test_return_type_cross_file_factory_module_gated(tmp_path: pathlib.Path):
    """from mod_a import make; obj = make(); obj.helper — gated away from mod_b.Foo."""
    (tmp_path / "mod_a.py").write_text(
        "class Foo:\n    def helper(self):\n        return 1\n\ndef make():\n    return Foo()\n",
        encoding="utf-8",
    )
    (tmp_path / "mod_b.py").write_text(
        "class Foo:\n    def helper(self):\n        return 2\n",
        encoding="utf-8",
    )
    (tmp_path / "app.py").write_text(
        "from mod_a import make\n\ndef run():\n    obj = make()\n    return obj.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    a_helper = next(k for k in repo["functions"] if "mod_a" in k and k.endswith(":Foo.helper"))
    b_helper = next(k for k in repo["functions"] if "mod_b" in k and k.endswith(":Foo.helper"))
    run_qn = next(k for k in repo["functions"] if k.endswith("app:run"))
    assert a_helper in repo["functions"][run_qn]["calls"]
    assert run_qn in repo["functions"][a_helper]["callers"]
    assert run_qn not in repo["functions"][b_helper]["callers"]


def test_multi_return_type_refuses_obj_method_edge(tmp_path: pathlib.Path):
    """return Foo() | return Bar() — no return_type, no invented obj.helper edge."""
    (tmp_path / "t.py").write_text(
        "class Foo:\n"
        "    def helper(self):\n"
        "        return 1\n"
        "\n"
        "class Bar:\n"
        "    def helper(self):\n"
        "        return 2\n"
        "\n"
        "def make(flag):\n"
        "    if flag:\n"
        "        return Foo()\n"
        "    return Bar()\n"
        "\n"
        "def run():\n"
        "    obj = make(True)\n"
        "    return obj.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    make_qn = next(k for k in repo["functions"] if k.endswith(":make"))
    run_qn = next(k for k in repo["functions"] if k.endswith(":run"))
    assert "return_type" not in repo["functions"][make_qn]
    assert "obj.helper" in repo["functions"][run_qn]["calls"]
    assert make_qn in repo["functions"][run_qn]["calls"]
    for qn, meta in repo["functions"].items():
        if qn.endswith(".helper"):
            assert run_qn not in meta.get("callers", [])


def test_snake_case_call_is_not_constructor_bind():
    import ast

    tree = ast.parse("def run():\n    obj = make()\n    return obj\n")
    run = tree.body[0]
    from cli.ucli.analyzers.python_analyzer import _collect_local_types, _factory_call_callee

    assert _collect_local_types(run) == {}
    assign = run.body[0]
    assert _factory_call_callee(assign.value) == "make"
    assert _looks_like_class_name("Foo")
    assert not _looks_like_class_name("make")


def test_infer_return_type_gates():
    import ast

    ok = ast.parse("def make():\n    return Foo()\n").body[0]
    assert _infer_return_type(ok) == ("Foo", None)

    ann = ast.parse("def make() -> Foo:\n    return None\n").body[0]
    assert _infer_return_type(ann) == ("Foo", None)

    multi = ast.parse("def make(f):\n    if f:\n        return Foo()\n    return Bar()\n").body[0]
    assert _infer_return_type(multi) == (None, None)

    unknown = ast.parse("def make():\n    return helper()\n").body[0]
    assert _infer_return_type(unknown) == (None, None)


def test_import_mod_as_alias_class_ctor_and_factory(tmp_path: pathlib.Path):
    """import mod as m; obj = m.Foo() / m.make() both resolve when unique."""
    (tmp_path / "mod.py").write_text(
        "class Foo:\n    def helper(self):\n        return 1\n\ndef make():\n    return Foo()\n",
        encoding="utf-8",
    )
    (tmp_path / "app_ctor.py").write_text(
        "import mod as m\n\ndef run():\n    obj = m.Foo()\n    return obj.helper()\n",
        encoding="utf-8",
    )
    (tmp_path / "app_factory.py").write_text(
        "import mod as m\n\ndef run():\n    obj = m.make()\n    return obj.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    helper = next(k for k in repo["functions"] if k.endswith("mod:Foo.helper"))
    for stem in ("app_ctor", "app_factory"):
        run_qn = next(k for k in repo["functions"] if k.endswith(f"{stem}:run"))
        assert helper in repo["functions"][run_qn]["calls"], stem
        assert run_qn in repo["functions"][helper]["callers"], stem


def test_relative_from_dot_import_class(tmp_path: pathlib.Path):
    """from . import Foo (class in package __init__) then obj.helper resolves."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text(
        "class Foo:\n    def helper(self):\n        return 1\n",
        encoding="utf-8",
    )
    (pkg / "app.py").write_text(
        "from . import Foo\n\ndef run():\n    obj = Foo()\n    return obj.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    helper = next(k for k in repo["functions"] if k.endswith("__init__:Foo.helper"))
    run_qn = next(k for k in repo["functions"] if k.endswith("app:run"))
    assert helper in repo["functions"][run_qn]["calls"]
    assert run_qn in repo["functions"][helper]["callers"]


def test_match_module_path_init_and_module():
    assert _match_module_path("pkg/__init__.py", "pkg")
    assert _match_module_path("pkg/mod.py", "pkg.mod")
    assert _match_module_path("/abs/pkg/mod.py", "pkg.mod")
    assert not _match_module_path("pkg/other.py", "pkg.mod")
    assert not _match_module_path("pkg/mod.py", "pkg")


def test_web_demo_tour_export_honest():
    """Wave 15 minimal shell: no export/tour buttons; CLI pointers remain."""
    html = pathlib.Path("web_demo/index.html").read_text(encoding="utf-8")
    assert "Export (disabled)" not in html
    assert "not" in html.lower() and ("pack" in html.lower() or "u scan" in html)
    assert "u pack" in html
    assert "u tour" in html
    assert (
        "browser-heuristic" in html
        or "heuristic" in html.lower()
        or "illustrative" in html.lower()
        or "sketch" in html.lower()
    )


def test_schema_documents_return_type_resolve():
    ref = pathlib.Path("schemas/SCHEMA_REFERENCE.md").read_text(encoding="utf-8")
    schema = pathlib.Path("schemas/map-schema.json").read_text(encoding="utf-8")
    assert "return_type" in schema
    assert "return" in ref.lower() and (
        "factory" in ref.lower() or "return-type" in ref.lower() or "obj = " in ref
    )
