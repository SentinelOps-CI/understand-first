"""Wave 17–18: JS/TS AST path, regex fallback, relative imports, labeling."""

from __future__ import annotations

import pathlib

import pytest
from cli.ucli.analyzers.js_analyzer import build_js_map
from cli.ucli.analyzers.js_ast_bridge import ast_backend_available
from cli.ucli.analyzers.registry import build_repo_map
from cli.ucli.commands.scan_ops import _complexity_kind_label
from cli.ucli.report.report import make_report_md


@pytest.fixture
def force_regex(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UF_JS_ANALYZER", "regex")


@pytest.fixture
def force_ast(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UF_JS_ANALYZER", "ast")


def test_regex_fallback_metadata(force_regex):
    m = build_js_map(pathlib.Path("examples/js_toy"))
    assert m["analyzer"] in {"javascript-best-effort", "typescript-best-effort"}
    assert m["analyzer_fidelity"] == "best-effort"
    assert m["complexity_kind"] == "keyword-heuristic"
    assert m["functions"]
    for meta in m["functions"].values():
        assert "best-effort" in meta["analyzer"]
        assert meta["complexity_kind"] == "keyword-heuristic"


@pytest.mark.skipif(not ast_backend_available(), reason="Node+typescript AST worker not installed")
def test_ast_path_metadata(force_ast):
    m = build_js_map(pathlib.Path("examples/js_toy"))
    assert m["analyzer"] == "javascript-ast"
    assert m["analyzer_fidelity"] == "ast"
    assert m["complexity_kind"] == "ast-cyclomatic"
    assert any(k.endswith(":add") for k in m["functions"])
    for meta in m["functions"].values():
        assert meta["analyzer"].endswith("-ast")
        assert meta["complexity_kind"] == "ast-cyclomatic"


@pytest.mark.skipif(not ast_backend_available(), reason="Node+typescript AST worker not installed")
def test_ast_sees_template_literal_call_regex_misses(force_ast, monkeypatch: pytest.MonkeyPatch):
    """nested_tricky: helper() inside a template literal — regex strips strings."""
    ast_map = build_js_map(pathlib.Path("examples/js_toy"))
    pe = next(k for k in ast_map["functions"] if k.endswith(":processEvent"))
    assert any(c.endswith(":helper") for c in ast_map["functions"][pe]["calls"])

    monkeypatch.setenv("UF_JS_ANALYZER", "regex")
    regex_map = build_js_map(pathlib.Path("examples/js_toy"))
    pe_r = next(k for k in regex_map["functions"] if k.endswith(":processEvent"))
    # Regex string-strip removes the template call; must not invent the edge.
    assert not any(
        (isinstance(c, str) and c.endswith(":helper"))
        for c in regex_map["functions"][pe_r]["calls"]
    )


@pytest.mark.skipif(not ast_backend_available(), reason="Node+typescript AST worker not installed")
def test_relative_import_resolve_unique(force_ast):
    m = build_js_map(pathlib.Path("examples/js_toy"))
    run = next(k for k in m["functions"] if k.endswith(":runShared"))
    assert any(c.endswith(":sharedUtil") for c in m["functions"][run]["calls"])


def test_regex_does_not_invent_relative_import_edges(force_regex):
    m = build_js_map(pathlib.Path("examples/js_toy"))
    run = next((k for k in m["functions"] if k.endswith(":runShared")), None)
    if run is None:
        pytest.skip("importer.mjs not visible to regex path")
    # Bare sharedUtil stays unqualified across files on regex path.
    assert "sharedUtil" in m["functions"][run]["calls"] or any(
        c == "sharedUtil" for c in m["functions"][run]["calls"]
    )
    assert not any(
        isinstance(c, str) and c.endswith(":sharedUtil") and ":" in c
        for c in m["functions"][run]["calls"]
    )


@pytest.mark.skipif(not ast_backend_available(), reason="Node+typescript AST worker not installed")
def test_typescript_only_tree_labeled_typescript_ast(force_ast, tmp_path: pathlib.Path):
    (tmp_path / "only.ts").write_text(
        "export function greet(name: string): string {\n  return name;\n}\n",
        encoding="utf-8",
    )
    m = build_js_map(tmp_path)
    assert m["language"] == "typescript"
    assert m["analyzer"] == "typescript-ast"
    assert any(k.endswith(":greet") for k in m["functions"])


def test_typescript_only_regex_labeled(force_regex, tmp_path: pathlib.Path):
    (tmp_path / "only.ts").write_text(
        "export function greet(name: string): string {\n  return name;\n}\n",
        encoding="utf-8",
    )
    m = build_js_map(tmp_path)
    assert m["language"] == "typescript"
    assert m["analyzer"] == "typescript-best-effort"


def test_python_path_unchanged():
    repo = build_repo_map(pathlib.Path("examples/python_toy"), languages=["python"])
    assert repo["language"] == "python"
    assert repo["complexity_kind"] == "mccabe"
    assert repo.get("analyzer") in {None, "python-ast"} or "python" in str(
        repo.get("analyzer", "python")
    )


def test_scan_complexity_label_distinguishes_kinds():
    assert "keyword" in _complexity_kind_label({"complexity_kind": "keyword-heuristic"}).lower()
    assert "ast-cyclomatic" in _complexity_kind_label({"complexity_kind": "ast-cyclomatic"}).lower()
    assert "McCabe" in _complexity_kind_label({"complexity_kind": "mccabe"})


def test_report_includes_fidelity_section(force_regex):
    m = build_js_map(pathlib.Path("examples/js_toy"))
    # Enrich like CLI maps often do
    md = make_report_md(m)
    assert "Map fidelity" in md
    assert "keyword-heuristic" in md or "best-effort" in md


@pytest.mark.skipif(not ast_backend_available(), reason="Node+typescript AST worker not installed")
def test_dispatcher_preserves_ast_analyzer(force_ast):
    via = build_repo_map(pathlib.Path("examples/js_toy"), languages=["javascript"])
    assert via["analyzer"] == "javascript-ast"
    assert via["complexity_kind"] == "ast-cyclomatic"
    assert via["analyzer_fidelity"]["javascript"] == "ast"


def test_ci_installs_js_ast_for_multilang_smoke():
    ci = pathlib.Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "multilang-smoke" in ci
    assert "js_ast" in ci or "analyzers/js_ast" in ci
    assert "npm" in ci


def test_schema_documents_ast_cyclomatic_and_ast_analyzer():
    schema = pathlib.Path("schemas/map-schema.json").read_text(encoding="utf-8")
    ref = pathlib.Path("schemas/SCHEMA_REFERENCE.md").read_text(encoding="utf-8")
    assert "ast-cyclomatic" in schema
    assert "javascript-ast" in ref or "ast-cyclomatic" in ref
    assert "UF_JS_ANALYZER" in ref or "regex fallback" in ref.lower()
