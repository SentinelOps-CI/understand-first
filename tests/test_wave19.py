"""Wave 19: Go analyzer (AST preferred, regex fallback), fixtures, labeling."""

from __future__ import annotations

import pathlib

import pytest
from cli.ucli.analyzers.go_analyzer import build_go_map
from cli.ucli.analyzers.go_ast_bridge import ast_backend_available
from cli.ucli.analyzers.registry import build_repo_map, supported_languages
from cli.ucli.commands.scan_ops import _complexity_kind_label
from cli.ucli.report.report import make_report_md


@pytest.fixture
def force_regex(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UF_GO_ANALYZER", "regex")


@pytest.fixture
def force_ast(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UF_GO_ANALYZER", "ast")


def test_registry_lists_go():
    assert "go" in supported_languages()


def test_regex_fallback_metadata(force_regex):
    m = build_go_map(pathlib.Path("examples/go_toy"))
    assert m["analyzer"] == "go-best-effort"
    assert m["analyzer_fidelity"] == "best-effort"
    assert m["complexity_kind"] == "keyword-heuristic"
    assert m["language"] == "go"
    assert m["functions"]
    for meta in m["functions"].values():
        assert meta["analyzer"] == "go-best-effort"
        assert meta["complexity_kind"] == "keyword-heuristic"
        assert meta["language"] == "go"
        assert "name" in meta and "type" in meta


def test_regex_fixture_funcs_and_same_file_calls(force_regex):
    m = build_go_map(pathlib.Path("examples/go_toy"))
    fns = m["functions"]
    assert any(k.endswith(":Add") for k in fns)
    assert any(k.endswith(":Compute") for k in fns)
    assert any(k.endswith(":Classify") for k in fns)
    assert any(k.endswith(":Calc.Scale") for k in fns)
    assert any(k.endswith(":Calc.Run") for k in fns)

    compute = next(k for k in fns if k.endswith(":Compute"))
    assert any(c.endswith(":Add") for c in fns[compute]["calls"])
    classify = next(k for k in fns if k.endswith(":Classify"))
    assert fns[classify]["complexity"] > 1


def test_regex_no_cross_file_same_package_edges(force_regex):
    m = build_go_map(pathlib.Path("examples/go_toy"))
    caller = next(k for k in m["functions"] if k.endswith(":RunShared"))
    calls = m["functions"][caller]["calls"]
    # Bare name may appear; must not invent a cross-file qualified edge.
    assert not any(isinstance(c, str) and c.endswith(":Helper") and ":" in c for c in calls)


def test_regex_does_not_invent_string_call(force_regex):
    m = build_go_map(pathlib.Path("examples/go_toy"))
    pe = next(k for k in m["functions"] if k.endswith(":processEvent"))
    assert not any(
        (isinstance(c, str) and (c.endswith(":helper") or c == "helper"))
        for c in m["functions"][pe]["calls"]
    )


@pytest.mark.skipif(not ast_backend_available(), reason="Go toolchain AST worker not available")
def test_ast_path_metadata(force_ast):
    m = build_go_map(pathlib.Path("examples/go_toy"))
    assert m["analyzer"] == "go-ast"
    assert m["analyzer_fidelity"] == "ast"
    assert m["complexity_kind"] == "ast-cyclomatic"
    assert any(k.endswith(":Add") for k in m["functions"])
    for meta in m["functions"].values():
        assert meta["analyzer"] == "go-ast"
        assert meta["complexity_kind"] == "ast-cyclomatic"


@pytest.mark.skipif(not ast_backend_available(), reason="Go toolchain AST worker not available")
def test_ast_same_package_unique_edge(force_ast):
    m = build_go_map(pathlib.Path("examples/go_toy"))
    caller = next(k for k in m["functions"] if k.endswith(":RunShared"))
    assert any(c.endswith(":Helper") for c in m["functions"][caller]["calls"])


@pytest.mark.skipif(not ast_backend_available(), reason="Go toolchain AST worker not available")
def test_ast_does_not_invent_string_call(force_ast):
    m = build_go_map(pathlib.Path("examples/go_toy"))
    pe = next(k for k in m["functions"] if k.endswith(":processEvent"))
    assert not any(
        (isinstance(c, str) and (c.endswith(":helper") or c == "helper"))
        for c in m["functions"][pe]["calls"]
    )


@pytest.mark.skipif(not ast_backend_available(), reason="Go toolchain AST worker not available")
def test_ast_does_not_invent_cross_package(force_ast, tmp_path: pathlib.Path):
    pkg_a = tmp_path / "a"
    pkg_b = tmp_path / "b"
    pkg_a.mkdir()
    pkg_b.mkdir()
    (pkg_a / "a.go").write_text(
        "package a\n\nfunc Shared() int { return 1 }\n\nfunc Run() int { return Shared() }\n",
        encoding="utf-8",
    )
    (pkg_b / "b.go").write_text(
        "package b\n\nfunc Shared() int { return 2 }\n\nfunc Run() int { return Shared() }\n",
        encoding="utf-8",
    )
    m = build_go_map(tmp_path)
    for run_qn, meta in m["functions"].items():
        if not run_qn.endswith(":Run"):
            continue
        for c in meta["calls"]:
            if isinstance(c, str) and c.endswith(":Shared"):
                caller_file = meta["file"]
                callee_file = m["functions"][c]["file"]
                assert pathlib.Path(caller_file).parent == pathlib.Path(callee_file).parent


@pytest.mark.skipif(not ast_backend_available(), reason="Go toolchain AST worker not available")
def test_dispatcher_preserves_go_ast(force_ast):
    via = build_repo_map(pathlib.Path("examples/go_toy"), languages=["go"])
    assert via["analyzer"] == "go-ast"
    assert via["complexity_kind"] == "ast-cyclomatic"
    assert via["analyzer_fidelity"]["go"] == "ast"
    assert via["language"] == "go"


def test_mixed_repo_analyzes_go_and_counts_unsupported(tmp_path: pathlib.Path, monkeypatch):
    monkeypatch.setenv("UF_GO_ANALYZER", "regex")
    monkeypatch.setenv("UF_JS_ANALYZER", "regex")
    (tmp_path / "a.py").write_text("def py_only():\n    return 1\n", encoding="utf-8")
    (tmp_path / "b.js").write_text("function jsOnly() {\n  return 1;\n}\n", encoding="utf-8")
    (tmp_path / "c.go").write_text("package main\n\nfunc GoSeen() {}\n", encoding="utf-8")
    (tmp_path / "d.zig").write_text("fn zig_skip() void {}\n", encoding="utf-8")

    repo = build_repo_map(tmp_path)
    assert repo["language"] == "mixed"
    assert "go" in repo["languages_analyzed"]
    assert "python" in repo["languages_analyzed"]
    assert "javascript" in repo["languages_analyzed"]
    assert repo["unsupported"].get("zig") == 1
    assert "go" not in (repo.get("unsupported") or {})
    fns = repo["functions"]
    assert any(k.endswith(":GoSeen") for k in fns)
    assert not any("zig_skip" in k for k in fns)


def test_lang_filter_go(tmp_path: pathlib.Path, monkeypatch):
    monkeypatch.setenv("UF_GO_ANALYZER", "regex")
    (tmp_path / "a.py").write_text("def hidden():\n    return 1\n", encoding="utf-8")
    (tmp_path / "b.go").write_text("package main\n\nfunc Visible() {}\n", encoding="utf-8")
    repo = build_repo_map(tmp_path, languages=["go"])
    assert repo["languages_analyzed"] == ["go"]
    assert any(k.endswith(":Visible") for k in repo["functions"])
    assert not any(k.endswith(":hidden") for k in repo["functions"])


def test_scan_complexity_label_mentions_go():
    label = _complexity_kind_label({"complexity_kind": "ast-cyclomatic", "analyzer": "go-ast"})
    assert "ast-cyclomatic" in label.lower()
    assert "go" in label.lower() or "structural" in label.lower()


def test_report_includes_go_fidelity(force_regex):
    m = build_go_map(pathlib.Path("examples/go_toy"))
    md = make_report_md(m)
    assert "Map fidelity" in md or "best-effort" in md or "go" in md.lower()


def test_ci_mentions_go_smoke():
    ci = pathlib.Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "go_toy" in ci
    assert "UF_GO_ANALYZER" in ci or "--lang go" in ci


def test_schema_documents_go():
    ref = pathlib.Path("schemas/SCHEMA_REFERENCE.md").read_text(encoding="utf-8")
    assert "go-ast" in ref or "go-best-effort" in ref
    assert "UF_GO_ANALYZER" in ref
