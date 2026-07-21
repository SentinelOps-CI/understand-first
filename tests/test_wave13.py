"""Wave 13: multi-hop factory return chaining, deeper relative imports, hygiene."""

from __future__ import annotations

import pathlib

from cli.ucli.analyzers.python_analyzer import build_python_map


def test_multi_hop_factory_return_direct(tmp_path: pathlib.Path):
    """outer returns inner(); obj = outer(); obj.helper → Foo.helper."""
    (tmp_path / "t.py").write_text(
        "class Foo:\n"
        "    def helper(self):\n"
        "        return 1\n"
        "\n"
        "def inner():\n"
        "    return Foo()\n"
        "\n"
        "def outer():\n"
        "    return inner()\n"
        "\n"
        "def run():\n"
        "    obj = outer()\n"
        "    return obj.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    helper = next(k for k in repo["functions"] if k.endswith(":Foo.helper"))
    outer_qn = next(k for k in repo["functions"] if k.endswith(":outer"))
    run_qn = next(k for k in repo["functions"] if k.endswith(":run"))
    assert repo["functions"][outer_qn].get("return_type") == "Foo"
    assert helper in repo["functions"][run_qn]["calls"]
    assert run_qn in repo["functions"][helper]["callers"]


def test_multi_hop_factory_return_via_alias_assign(tmp_path: pathlib.Path):
    """outer: x = inner(); return x — same high-confidence chain."""
    (tmp_path / "t.py").write_text(
        "class Foo:\n"
        "    def helper(self):\n"
        "        return 1\n"
        "\n"
        "def inner():\n"
        "    return Foo()\n"
        "\n"
        "def outer():\n"
        "    x = inner()\n"
        "    return x\n"
        "\n"
        "def run():\n"
        "    obj = outer()\n"
        "    return obj.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    helper = next(k for k in repo["functions"] if k.endswith(":Foo.helper"))
    outer_qn = next(k for k in repo["functions"] if k.endswith(":outer"))
    run_qn = next(k for k in repo["functions"] if k.endswith(":run"))
    assert repo["functions"][outer_qn].get("return_type") == "Foo"
    assert helper in repo["functions"][run_qn]["calls"]
    assert run_qn in repo["functions"][helper]["callers"]


def test_multi_hop_three_levels(tmp_path: pathlib.Path):
    """a → b → c → Foo within hop cap of 3."""
    (tmp_path / "t.py").write_text(
        "class Foo:\n"
        "    def helper(self):\n"
        "        return 1\n"
        "\n"
        "def c():\n"
        "    return Foo()\n"
        "\n"
        "def b():\n"
        "    return c()\n"
        "\n"
        "def a():\n"
        "    return b()\n"
        "\n"
        "def run():\n"
        "    obj = a()\n"
        "    return obj.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    helper = next(k for k in repo["functions"] if k.endswith(":Foo.helper"))
    a_qn = next(k for k in repo["functions"] if k.endswith(":a"))
    run_qn = next(k for k in repo["functions"] if k.endswith(":run"))
    assert repo["functions"][a_qn].get("return_type") == "Foo"
    assert helper in repo["functions"][run_qn]["calls"]


def test_multi_hop_refuses_cycle(tmp_path: pathlib.Path):
    """a returns b(); b returns a() — no return_type; no typed obj.helper edge."""
    (tmp_path / "t.py").write_text(
        "class Foo:\n"
        "    def helper(self):\n"
        "        return 1\n"
        "\n"
        "class Bar:\n"
        "    def helper(self):\n"
        "        return 2\n"
        "\n"
        "def a():\n"
        "    return b()\n"
        "\n"
        "def b():\n"
        "    return a()\n"
        "\n"
        "def run():\n"
        "    obj = a()\n"
        "    return obj.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    a_qn = next(k for k in repo["functions"] if k.endswith(":a"))
    b_qn = next(k for k in repo["functions"] if k.endswith(":b"))
    run_qn = next(k for k in repo["functions"] if k.endswith(":run"))
    assert "return_type" not in repo["functions"][a_qn]
    assert "return_type" not in repo["functions"][b_qn]
    # Ambiguous same-file .helper → token stays; no invented callers.
    assert "obj.helper" in repo["functions"][run_qn]["calls"]
    for qn, meta in repo["functions"].items():
        if qn.endswith(".helper"):
            assert run_qn not in meta.get("callers", [])


def test_multi_hop_refuses_disagreeing_callees(tmp_path: pathlib.Path):
    """return make_foo() | return make_bar() — refuse chain."""
    (tmp_path / "t.py").write_text(
        "class Foo:\n"
        "    def helper(self):\n"
        "        return 1\n"
        "\n"
        "class Bar:\n"
        "    def helper(self):\n"
        "        return 2\n"
        "\n"
        "def make_foo():\n"
        "    return Foo()\n"
        "\n"
        "def make_bar():\n"
        "    return Bar()\n"
        "\n"
        "def outer(flag):\n"
        "    if flag:\n"
        "        return make_foo()\n"
        "    return make_bar()\n"
        "\n"
        "def run():\n"
        "    obj = outer(True)\n"
        "    return obj.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    outer_qn = next(k for k in repo["functions"] if k.endswith(":outer"))
    run_qn = next(k for k in repo["functions"] if k.endswith(":run"))
    assert "return_type" not in repo["functions"][outer_qn]
    for qn, meta in repo["functions"].items():
        if qn.endswith(".helper"):
            assert run_qn not in meta.get("callers", [])


def test_multi_hop_cross_file_import_gated(tmp_path: pathlib.Path):
    """Cross-file outer→inner with imported Foo stays gated away from other.Foo."""
    (tmp_path / "models.py").write_text(
        "class Foo:\n    def helper(self):\n        return 1\n",
        encoding="utf-8",
    )
    (tmp_path / "other.py").write_text(
        "class Foo:\n    def helper(self):\n        return 2\n",
        encoding="utf-8",
    )
    (tmp_path / "factory.py").write_text(
        "from models import Foo\n\ndef inner() -> Foo:\n    return Foo()\n\ndef outer():\n    return inner()\n",
        encoding="utf-8",
    )
    (tmp_path / "app.py").write_text(
        "from factory import outer\n\ndef run():\n    obj = outer()\n    return obj.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    outer_qn = next(k for k in repo["functions"] if k.endswith("factory:outer"))
    run_qn = next(k for k in repo["functions"] if k.endswith("app:run"))
    a_helper = next(k for k in repo["functions"] if "models" in k and k.endswith(":Foo.helper"))
    b_helper = next(k for k in repo["functions"] if "other" in k and k.endswith(":Foo.helper"))
    assert repo["functions"][outer_qn].get("return_type") == "Foo"
    assert a_helper in repo["functions"][run_qn]["calls"]
    assert run_qn not in repo["functions"][b_helper]["callers"]


def test_relative_from_dotdot_pkg_models_class_as_alias(tmp_path: pathlib.Path):
    """from ..pkg.models import Foo as F — nested relative + alias, uniqueness-gated."""
    root = tmp_path / "top"
    pkg = root / "pkg"
    svc = root / "service"
    for d in (root, pkg, svc):
        d.mkdir()
        (d / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "models.py").write_text(
        "class Foo:\n    def helper(self):\n        return 1\n",
        encoding="utf-8",
    )
    (tmp_path / "other.py").write_text(
        "class Foo:\n    def helper(self):\n        return 2\n",
        encoding="utf-8",
    )
    (svc / "app.py").write_text(
        "from ..pkg.models import Foo as F\n\ndef run():\n    obj = F()\n    return obj.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    helper = next(k for k in repo["functions"] if "models" in k and k.endswith(":Foo.helper"))
    other = next(k for k in repo["functions"] if "other" in k and k.endswith(":Foo.helper"))
    run_qn = next(k for k in repo["functions"] if k.endswith("app:run"))
    assert helper in repo["functions"][run_qn]["calls"]
    assert run_qn in repo["functions"][helper]["callers"]
    assert run_qn not in repo["functions"][other]["callers"]


def test_relative_from_dotdotdot_pkg_class_as_alias(tmp_path: pathlib.Path):
    """from ...pkg.models import Foo as C — three-dot relative from nested package."""
    root = tmp_path / "top"
    pkg = root / "pkg"
    svc = root / "service"
    nested = svc / "nested"
    for d in (root, pkg, svc, nested):
        d.mkdir()
        (d / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "models.py").write_text(
        "class Foo:\n    def helper(self):\n        return 1\n",
        encoding="utf-8",
    )
    (tmp_path / "other.py").write_text(
        "class Foo:\n    def helper(self):\n        return 2\n",
        encoding="utf-8",
    )
    (nested / "app.py").write_text(
        "from ...pkg.models import Foo as C\n\ndef run():\n    obj = C()\n    return obj.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    helper = next(k for k in repo["functions"] if "models" in k and k.endswith(":Foo.helper"))
    other = next(k for k in repo["functions"] if "other" in k and k.endswith(":Foo.helper"))
    run_qn = next(k for k in repo["functions"] if k.endswith("app:run"))
    assert helper in repo["functions"][run_qn]["calls"]
    assert run_qn not in repo["functions"][other]["callers"]


def test_relative_factory_import_then_obj_method(tmp_path: pathlib.Path):
    """from ..factory import make; obj = make(); obj.helper — relative + factory."""
    pkg = tmp_path / "pkg"
    sub = pkg / "sub"
    pkg.mkdir()
    sub.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (sub / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "models.py").write_text(
        "class Foo:\n    def helper(self):\n        return 1\n",
        encoding="utf-8",
    )
    (tmp_path / "other.py").write_text(
        "class Foo:\n    def helper(self):\n        return 2\n",
        encoding="utf-8",
    )
    (pkg / "factory.py").write_text(
        "from .models import Foo\n\ndef make() -> Foo:\n    return Foo()\n",
        encoding="utf-8",
    )
    (sub / "app.py").write_text(
        "from ..factory import make\n\ndef run():\n    obj = make()\n    return obj.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    helper = next(k for k in repo["functions"] if "models" in k and k.endswith(":Foo.helper"))
    other = next(k for k in repo["functions"] if "other" in k and k.endswith(":Foo.helper"))
    run_qn = next(k for k in repo["functions"] if k.endswith("app:run"))
    assert helper in repo["functions"][run_qn]["calls"]
    assert run_qn not in repo["functions"][other]["callers"]


def test_ci_no_dual_pypi_publish():
    ci = pathlib.Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    pub = pathlib.Path(".github/workflows/publish-pypi.yml").read_text(encoding="utf-8")
    assert "twine upload" not in ci
    assert "Publish to PyPI" not in ci
    assert "pypa/gh-action-pypi-publish" in pub
    assert "Sole PyPI publisher" in pub or "trusted publishing" in pub.lower()


def test_release_pack_publish_honest():
    rel = pathlib.Path(".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "u pack --publish" not in rel
    assert "u pack publish" in rel
    assert "|| true" not in rel
    assert "continue-on-error: true" in rel


def test_readme_capability_and_pack_honest():
    readme = pathlib.Path("README.md").read_text(encoding="utf-8")
    assert "u pack publish" in readme
    assert "u pack --publish" not in readme
    assert "not faked" in readme.lower() or "Python today" in readme
    assert "instrumentation/" in readme
    assert "not wired" in readme.lower()


def test_instrumentation_orphan_labeled():
    text = pathlib.Path("instrumentation/README.md").read_text(encoding="utf-8")
    assert "orphan" in text.lower() or "not" in text.lower() and "wired" in text.lower()
    assert "not" in text.lower() and "cli" in text.lower()


def test_ide_exposes_return_type():
    ext = pathlib.Path("ide/vscode/understand-first/extension.js").read_text(encoding="utf-8")
    assert "return_type" in ext
    assert "Return type" in ext or "→ ${returnType}" in ext or "→ ${" in ext


def test_schema_documents_multi_hop():
    ref = pathlib.Path("schemas/SCHEMA_REFERENCE.md").read_text(encoding="utf-8")
    assert "multi-hop" in ref.lower() or "Multi-hop" in ref
    assert "3 hops" in ref or "hop" in ref.lower()
