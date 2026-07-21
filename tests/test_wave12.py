"""Wave 12: imported return-type resolve, consumers, hygiene."""

from __future__ import annotations

import ast
import json
import pathlib

from cli.ucli.analyzers.python_analyzer import _infer_return_type, build_python_map
from cli.ucli.report.report import make_report_md


def test_imported_return_type_from_import_gates_away_ambiguous_foo(tmp_path: pathlib.Path):
    """from models import Foo; make() -> Foo — resolve despite other.Foo."""
    (tmp_path / "models.py").write_text(
        "class Foo:\n    def helper(self):\n        return 1\n",
        encoding="utf-8",
    )
    (tmp_path / "other.py").write_text(
        "class Foo:\n    def helper(self):\n        return 2\n",
        encoding="utf-8",
    )
    (tmp_path / "factory.py").write_text(
        "from models import Foo\n\ndef make() -> Foo:\n    return Foo()\n",
        encoding="utf-8",
    )
    (tmp_path / "app.py").write_text(
        "from factory import make\n\ndef run():\n    obj = make()\n    return obj.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    make_qn = next(k for k in repo["functions"] if k.endswith("factory:make"))
    run_qn = next(k for k in repo["functions"] if k.endswith("app:run"))
    a_helper = next(k for k in repo["functions"] if "models" in k and k.endswith(":Foo.helper"))
    b_helper = next(k for k in repo["functions"] if "other" in k and k.endswith(":Foo.helper"))
    assert repo["functions"][make_qn].get("return_type") == "Foo"
    assert a_helper in repo["functions"][run_qn]["calls"]
    assert run_qn in repo["functions"][a_helper]["callers"]
    assert run_qn not in repo["functions"][b_helper]["callers"]


def test_imported_return_type_models_dot_foo_annotation(tmp_path: pathlib.Path):
    """import models; make() -> models.Foo — module-gated across ambiguity."""
    (tmp_path / "models.py").write_text(
        "class Foo:\n    def helper(self):\n        return 1\n",
        encoding="utf-8",
    )
    (tmp_path / "other.py").write_text(
        "class Foo:\n    def helper(self):\n        return 2\n",
        encoding="utf-8",
    )
    (tmp_path / "factory.py").write_text(
        "import models\n\ndef make() -> models.Foo:\n    return models.Foo()\n",
        encoding="utf-8",
    )
    (tmp_path / "app.py").write_text(
        "from factory import make\n\ndef run():\n    obj = make()\n    return obj.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    make_qn = next(k for k in repo["functions"] if k.endswith("factory:make"))
    run_qn = next(k for k in repo["functions"] if k.endswith("app:run"))
    a_helper = next(k for k in repo["functions"] if "models" in k and k.endswith(":Foo.helper"))
    b_helper = next(k for k in repo["functions"] if "other" in k and k.endswith(":Foo.helper"))
    assert repo["functions"][make_qn].get("return_type") == "Foo"
    assert a_helper in repo["functions"][run_qn]["calls"]
    assert run_qn in repo["functions"][a_helper]["callers"]
    assert run_qn not in repo["functions"][b_helper]["callers"]


def test_imported_return_type_as_alias_canonicalizes(tmp_path: pathlib.Path):
    """from models import Foo as F; -> F / return F() → return_type Foo, gated."""
    (tmp_path / "models.py").write_text(
        "class Foo:\n    def helper(self):\n        return 1\n",
        encoding="utf-8",
    )
    (tmp_path / "other.py").write_text(
        "class Foo:\n    def helper(self):\n        return 2\n",
        encoding="utf-8",
    )
    (tmp_path / "factory.py").write_text(
        "from models import Foo as F\n\ndef make() -> F:\n    return F()\n",
        encoding="utf-8",
    )
    (tmp_path / "app.py").write_text(
        "from factory import make\n\ndef run():\n    obj = make()\n    return obj.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    make_qn = next(k for k in repo["functions"] if k.endswith("factory:make"))
    run_qn = next(k for k in repo["functions"] if k.endswith("app:run"))
    a_helper = next(k for k in repo["functions"] if "models" in k and k.endswith(":Foo.helper"))
    b_helper = next(k for k in repo["functions"] if "other" in k and k.endswith(":Foo.helper"))
    assert repo["functions"][make_qn].get("return_type") == "Foo"
    assert a_helper in repo["functions"][run_qn]["calls"]
    assert run_qn in repo["functions"][a_helper]["callers"]
    assert run_qn not in repo["functions"][b_helper]["callers"]


def test_unimported_return_type_refuses_ambiguous_foo(tmp_path: pathlib.Path):
    """-> Foo with no import and two Foos — no invented obj.helper edge."""
    (tmp_path / "models.py").write_text(
        "class Foo:\n    def helper(self):\n        return 1\n",
        encoding="utf-8",
    )
    (tmp_path / "other.py").write_text(
        "class Foo:\n    def helper(self):\n        return 2\n",
        encoding="utf-8",
    )
    (tmp_path / "factory.py").write_text(
        "def make() -> Foo:\n    return Foo()\n",
        encoding="utf-8",
    )
    (tmp_path / "app.py").write_text(
        "from factory import make\n\ndef run():\n    obj = make()\n    return obj.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    make_qn = next(k for k in repo["functions"] if k.endswith("factory:make"))
    run_qn = next(k for k in repo["functions"] if k.endswith("app:run"))
    assert repo["functions"][make_qn].get("return_type") == "Foo"
    assert "obj.helper" in repo["functions"][run_qn]["calls"]
    for qn, meta in repo["functions"].items():
        if qn.endswith(":Foo.helper"):
            assert run_qn not in meta.get("callers", [])


def test_infer_return_type_import_origin():
    src = "from models import Foo as F\ndef make() -> F:\n    return F()\n"
    tree = ast.parse(src)
    make = tree.body[1]
    aliases = {"F": "models:Foo"}
    assert _infer_return_type(make, aliases) == ("Foo", "models")

    src2 = "import models\ndef make() -> models.Foo:\n    return None\n"
    tree2 = ast.parse(src2)
    make2 = tree2.body[1]
    aliases2 = {"models": "models"}
    assert _infer_return_type(make2, aliases2) == ("Foo", "models")


def test_report_lists_return_types(tmp_path: pathlib.Path):
    (tmp_path / "t.py").write_text(
        "class Foo:\n    def helper(self):\n        return 1\n\ndef make() -> Foo:\n    return Foo()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    md = make_report_md(repo)
    assert "return type" in md.lower() or "Return types" in md
    assert "Foo" in md


def test_bandit_baseline_loc_refreshed():
    baseline = json.loads(pathlib.Path(".bandit-baseline.json").read_text(encoding="utf-8"))
    assert baseline.get("results") == []
    loc = int((baseline.get("metrics") or {}).get("_totals", {}).get("loc") or 0)
    # LOC must stay in sync with a fresh bandit scan (Wave 11 left 6276 stale).
    assert loc >= 6500, f"refresh bandit baseline LOC (got {loc})"


def test_pytest_asyncio_loop_scope_configured():
    ini = pathlib.Path("pytest.ini").read_text(encoding="utf-8")
    pyproject = pathlib.Path("pyproject.toml").read_text(encoding="utf-8")
    assert (
        "asyncio_default_fixture_loop_scope" in ini
        or "asyncio_default_fixture_loop_scope" in pyproject
    )


def test_web_demo_wizard_tour_honest():
    html = pathlib.Path("web_demo/index.html").read_text(encoding="utf-8")
    # Wave 14/15: wizard/tour chrome removed — must not imply product tour parity.
    assert "personalized tour" not in html.lower()
    assert 'id="wizardOverlay"' not in html
    assert 'id="onboardingWizard"' not in html
    assert "Tour (CLI only)" not in html
    assert "u tour" in html
    assert "does not generate product tours" in html.lower() or "not" in html.lower()
    assert "Start demo tour" not in html
    assert "Generate demo tour sketch" not in html


def test_schema_documents_imported_return_type():
    ref = pathlib.Path("schemas/SCHEMA_REFERENCE.md").read_text(encoding="utf-8")
    assert "return_type" in ref
    assert "import" in ref.lower() and (
        "models.Foo" in ref or "imported" in ref.lower() or "from mod import" in ref.lower()
    )


def test_relative_from_dotdot_import_class_as_alias(tmp_path: pathlib.Path):
    """from ..models import Foo as F then obj.helper — uniqueness-gated only."""
    pkg = tmp_path / "pkg"
    sub = pkg / "sub"
    pkg.mkdir()
    sub.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "models.py").write_text(
        "class Foo:\n    def helper(self):\n        return 1\n",
        encoding="utf-8",
    )
    (tmp_path / "other.py").write_text(
        "class Foo:\n    def helper(self):\n        return 2\n",
        encoding="utf-8",
    )
    (sub / "__init__.py").write_text("", encoding="utf-8")
    (sub / "app.py").write_text(
        "from ..models import Foo as F\n\ndef run():\n    obj = F()\n    return obj.helper()\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    helper = next(k for k in repo["functions"] if "models" in k and k.endswith(":Foo.helper"))
    other = next(k for k in repo["functions"] if "other" in k and k.endswith(":Foo.helper"))
    run_qn = next(k for k in repo["functions"] if k.endswith("app:run"))
    assert helper in repo["functions"][run_qn]["calls"]
    assert run_qn in repo["functions"][helper]["callers"]
    assert run_qn not in repo["functions"][other]["callers"]
