"""Wave 30: Python residual high-confidence imported typing gaps."""

from __future__ import annotations

import ast
import pathlib

from cli.ucli.analyzers.python_analyzer import (
    _collect_import_aliases,
    _simple_type_name,
    _type_ref_with_origin,
    build_python_map,
)

TOY = pathlib.Path("examples/python_toy")


def _helper_qn(repo: dict, *, file_stem: str, class_method: str) -> str:
    return next(
        k
        for k in repo["functions"]
        if file_stem in k.replace("\\", "/") and k.endswith(f":{class_method}")
    )


def _ann(src: str) -> ast.AST:
    tree = ast.parse(src)
    fn = tree.body[0]
    assert isinstance(fn, ast.FunctionDef)
    ann = fn.args.args[0].annotation
    assert ann is not None
    return ann


def test_string_annotation_optional_union_and_refuse():
    assert _simple_type_name(_ann('def f(x: "Foo"):\n    pass\n')) == "Foo"
    assert _simple_type_name(_ann('def f(x: "Foo | None"):\n    pass\n')) == "Foo"
    assert _simple_type_name(_ann('def f(x: "Foo | Bar"):\n    pass\n')) is None
    assert _simple_type_name(_ann('def f(x: "list[Foo]"):\n    pass\n')) is None


def test_annotated_final_classvar_unwrap():
    assert _simple_type_name(_ann('def f(x: Annotated[Foo, "m"]):\n    pass\n')) == "Foo"
    assert _simple_type_name(_ann("def f(x: Final[Foo]):\n    pass\n")) == "Foo"
    assert _simple_type_name(_ann("def f(x: ClassVar[Foo]):\n    pass\n")) == "Foo"


def test_optional_import_alias_unwrap():
    src = "from typing import Optional as Opt\ndef f(x: Opt[Foo]):\n    pass\n"
    tree = ast.parse(src)
    aliases = _collect_import_aliases(tree, pathlib.Path("app.py"))
    fn = tree.body[1]
    assert isinstance(fn, ast.FunctionDef)
    ann = fn.args.args[0].annotation
    assert ann is not None
    assert _simple_type_name(ann, aliases) == "Foo"
    assert _type_ref_with_origin(ann, aliases) == ("Foo", None)


def test_type_checking_guard_records_import(tmp_path: pathlib.Path):
    src = (
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    from mod import Foo\n"
        "def f(x: Foo):\n"
        "    pass\n"
    )
    (tmp_path / "app.py").write_text(src, encoding="utf-8")
    tree = ast.parse(src)
    aliases = _collect_import_aliases(tree, tmp_path / "app.py")
    assert aliases.get("Foo") == "mod:Foo"
    assert aliases.get("TYPE_CHECKING") == "typing:TYPE_CHECKING"


def test_quoted_imported_annotation_resolves(tmp_path: pathlib.Path):
    (tmp_path / "mod.py").write_text(
        "class Foo:\n    def helper(self):\n        return 1\n",
        encoding="utf-8",
    )
    (tmp_path / "other.py").write_text(
        "class Foo:\n    def helper(self):\n        return 2\n",
        encoding="utf-8",
    )
    (tmp_path / "app.py").write_text(
        'from mod import Foo\ndef run(obj: "Foo"):\n    return obj.helper()\n',
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path, processes=1)
    helper = _helper_qn(repo, file_stem="mod", class_method="Foo.helper")
    other = _helper_qn(repo, file_stem="other", class_method="Foo.helper")
    run_qn = next(k for k in repo["functions"] if k.endswith("app:run"))
    assert helper in repo["functions"][run_qn]["calls"]
    assert run_qn in repo["functions"][helper]["callers"]
    assert run_qn not in repo["functions"][other]["callers"]


def test_annotated_imported_annotation_resolves(tmp_path: pathlib.Path):
    (tmp_path / "mod.py").write_text(
        "class Foo:\n    def helper(self):\n        return 1\n",
        encoding="utf-8",
    )
    (tmp_path / "other.py").write_text(
        "class Foo:\n    def helper(self):\n        return 2\n",
        encoding="utf-8",
    )
    (tmp_path / "app.py").write_text(
        "from typing import Annotated\n"
        "from mod import Foo\n"
        'def run(obj: Annotated[Foo, "meta"]):\n'
        "    return obj.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path, processes=1)
    helper = _helper_qn(repo, file_stem="mod", class_method="Foo.helper")
    other = _helper_qn(repo, file_stem="other", class_method="Foo.helper")
    run_qn = next(k for k in repo["functions"] if k.endswith("app:run"))
    assert helper in repo["functions"][run_qn]["calls"]
    assert run_qn not in repo["functions"][other]["callers"]


def test_optional_as_alias_imported_annotation_resolves(tmp_path: pathlib.Path):
    (tmp_path / "mod.py").write_text(
        "class Foo:\n    def helper(self):\n        return 1\n",
        encoding="utf-8",
    )
    (tmp_path / "other.py").write_text(
        "class Foo:\n    def helper(self):\n        return 2\n",
        encoding="utf-8",
    )
    (tmp_path / "app.py").write_text(
        "from typing import Optional as Opt\n"
        "from mod import Foo\n"
        "def run(obj: Opt[Foo]):\n"
        "    return obj.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path, processes=1)
    helper = _helper_qn(repo, file_stem="mod", class_method="Foo.helper")
    other = _helper_qn(repo, file_stem="other", class_method="Foo.helper")
    run_qn = next(k for k in repo["functions"] if k.endswith("app:run"))
    assert helper in repo["functions"][run_qn]["calls"]
    assert run_qn not in repo["functions"][other]["callers"]


def test_final_annassign_imported_resolves(tmp_path: pathlib.Path):
    (tmp_path / "mod.py").write_text(
        "class Foo:\n    def helper(self):\n        return 1\n",
        encoding="utf-8",
    )
    (tmp_path / "other.py").write_text(
        "class Foo:\n    def helper(self):\n        return 2\n",
        encoding="utf-8",
    )
    (tmp_path / "app.py").write_text(
        "from typing import Final\n"
        "from mod import Foo\n"
        "def run():\n"
        "    obj: Final[Foo] = Foo()\n"
        "    return obj.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path, processes=1)
    helper = _helper_qn(repo, file_stem="mod", class_method="Foo.helper")
    other = _helper_qn(repo, file_stem="other", class_method="Foo.helper")
    run_qn = next(k for k in repo["functions"] if k.endswith("app:run"))
    assert helper in repo["functions"][run_qn]["calls"]
    assert run_qn not in repo["functions"][other]["callers"]


def test_type_checking_quoted_import_resolves(tmp_path: pathlib.Path):
    (tmp_path / "mod.py").write_text(
        "class Foo:\n    def helper(self):\n        return 1\n",
        encoding="utf-8",
    )
    (tmp_path / "other.py").write_text(
        "class Foo:\n    def helper(self):\n        return 2\n",
        encoding="utf-8",
    )
    (tmp_path / "app.py").write_text(
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    from mod import Foo\n"
        'def run(obj: "Foo"):\n'
        "    return obj.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path, processes=1)
    helper = _helper_qn(repo, file_stem="mod", class_method="Foo.helper")
    other = _helper_qn(repo, file_stem="other", class_method="Foo.helper")
    run_qn = next(k for k in repo["functions"] if k.endswith("app:run"))
    assert helper in repo["functions"][run_qn]["calls"]
    assert run_qn not in repo["functions"][other]["callers"]


def test_foo_as_f_optional_wrapper_resolves(tmp_path: pathlib.Path):
    """from mod import Foo as F; Optional[F] still import-gates."""
    (tmp_path / "mod.py").write_text(
        "class Foo:\n    def helper(self):\n        return 1\n",
        encoding="utf-8",
    )
    (tmp_path / "other.py").write_text(
        "class Foo:\n    def helper(self):\n        return 2\n",
        encoding="utf-8",
    )
    (tmp_path / "app.py").write_text(
        "from typing import Optional\n"
        "from mod import Foo as F\n"
        "def run(obj: Optional[F]):\n"
        "    return obj.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path, processes=1)
    helper = _helper_qn(repo, file_stem="mod", class_method="Foo.helper")
    other = _helper_qn(repo, file_stem="other", class_method="Foo.helper")
    run_qn = next(k for k in repo["functions"] if k.endswith("app:run"))
    assert helper in repo["functions"][run_qn]["calls"]
    assert run_qn not in repo["functions"][other]["callers"]


def test_multi_class_annotated_still_omits(tmp_path: pathlib.Path):
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
        "from typing import Annotated\n"
        "from mod import Foo, Bar\n"
        'def run(obj: Annotated[Foo | Bar, "x"]):\n'
        "    return obj.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path, processes=1)
    run_qn = next(k for k in repo["functions"] if k.endswith("app:run"))
    assert repo["functions"][run_qn]["calls"] == ["obj.helper"]
    for qn, meta in repo["functions"].items():
        if qn.endswith(".helper"):
            assert run_qn not in meta.get("callers", [])


def test_python_toy_wave30_typed_client_resolves():
    """Durable fixture under examples/python_toy exercises Wave 30 paths."""
    assert (TOY / "pkg" / "models.py").is_file()
    assert (TOY / "pkg" / "typed_client.py").is_file()
    repo = build_python_map(TOY, processes=1)
    paint = next(k for k in repo["functions"] if k.endswith("models:Widget.paint"))
    for name in ("via_quoted", "via_annotated", "via_opt_alias", "via_final"):
        qn = next(k for k in repo["functions"] if k.endswith(f"typed_client:{name}"))
        assert paint in repo["functions"][qn]["calls"], name
        assert qn in repo["functions"][paint]["callers"], name


def test_schema_documents_wave30_typing():
    ref = pathlib.Path("schemas/SCHEMA_REFERENCE.md").read_text(encoding="utf-8")
    assert "Wave 30" in ref
    assert "TYPE_CHECKING" in ref
    assert "Annotated" in ref
