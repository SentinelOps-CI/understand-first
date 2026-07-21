"""Wave 21: Java javalang AST + JS re-export barrel resolve."""

from __future__ import annotations

import pathlib

import pytest
from cli.ucli.analyzers.java_analyzer import build_java_map, javalang_available
from cli.ucli.analyzers.js_analyzer import build_js_map
from cli.ucli.analyzers.js_ast_bridge import ast_backend_available


@pytest.fixture
def force_java_regex(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UF_JAVA_ANALYZER", "regex")


@pytest.fixture
def force_java_ast(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UF_JAVA_ANALYZER", "ast")


@pytest.fixture
def force_js_ast(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UF_JS_ANALYZER", "ast")


def test_java_regex_still_works(force_java_regex):
    m = build_java_map(pathlib.Path("examples/java_toy"))
    assert m["analyzer"] == "java-best-effort"
    assert m["complexity_kind"] == "keyword-heuristic"
    assert any(k.endswith(":MathUtil.add") for k in m["functions"])


@pytest.mark.skipif(not javalang_available(), reason="javalang not installed")
def test_java_ast_path_metadata(force_java_ast):
    m = build_java_map(pathlib.Path("examples/java_toy"))
    assert m["analyzer"] == "java-ast"
    assert m["analyzer_fidelity"] == "ast"
    assert m["complexity_kind"] == "ast-cyclomatic"
    compute = next(k for k in m["functions"] if k.endswith(":MathUtil.compute"))
    assert any(
        isinstance(c, str) and c.endswith(":MathUtil.add") for c in m["functions"][compute]["calls"]
    )
    classify = next(k for k in m["functions"] if k.endswith(":MathUtil.classify"))
    assert m["functions"][classify]["complexity"] > 1
    run = next(k for k in m["functions"] if k.endswith(":Importer.runShared"))
    assert any(
        isinstance(c, str) and c.endswith(":Helper.helper") for c in m["functions"][run]["calls"]
    )


@pytest.mark.skipif(not ast_backend_available(), reason="Node+typescript AST worker not installed")
def test_js_barrel_reexport_resolve(force_js_ast):
    m = build_js_map(pathlib.Path("examples/js_toy"))
    run = next(k for k in m["functions"] if k.endswith(":runBarrel"))
    assert any(
        isinstance(c, str) and c.endswith(":barrelUtil") for c in m["functions"][run]["calls"]
    )
    # Must land on defining module, not the barrel index (no local def there).
    assert any(
        isinstance(c, str) and "barrel_lib" in c and c.endswith(":barrelUtil")
        for c in m["functions"][run]["calls"]
    )
