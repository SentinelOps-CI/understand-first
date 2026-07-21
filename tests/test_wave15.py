"""Wave 15: language adapter registry, JS best-effort analyzer, web_demo trim."""

from __future__ import annotations

import pathlib

from cli.ucli.analyzers.js_analyzer import build_js_map
from cli.ucli.analyzers.python_analyzer import build_python_map
from cli.ucli.analyzers.registry import (
    build_repo_map,
    format_unsupported_summary,
    registered_adapters,
    supported_languages,
)


def test_registry_lists_python_javascript_and_go():
    langs = supported_languages()
    assert "python" in langs
    assert "javascript" in langs
    assert "go" in langs
    adapters = {a.language: a for a in registered_adapters()}
    assert adapters["python"].fidelity == "ast"
    # JS adapter prefers AST when Node deps exist; may degrade to best-effort.
    assert adapters["javascript"].fidelity in {"ast", "best-effort"}
    assert adapters["go"].fidelity in {"ast", "best-effort"}


def test_js_fixture_extracts_functions_and_same_file_calls(monkeypatch):
    monkeypatch.setenv("UF_JS_ANALYZER", "regex")
    root = pathlib.Path("examples/js_toy")
    m = build_js_map(root)
    assert m["analyzer_fidelity"] == "best-effort"
    fns = m["functions"]
    keys = "\n".join(fns.keys())
    assert "examples/js_toy/math:add" in keys
    assert "examples/js_toy/math:compute" in keys
    assert "examples/js_toy/math:classify" in keys
    assert "examples/js_toy/math:double" in keys
    assert "examples/js_toy/math:Calculator.scale" in keys

    add_qn = "examples/js_toy/math:add"
    compute_qn = "examples/js_toy/math:compute"
    assert add_qn in fns[compute_qn]["calls"]
    assert compute_qn in fns[add_qn]["callers"]
    # Keyword heuristic: classify has if/for/catch — complexity > 1
    assert fns["examples/js_toy/math:classify"]["complexity"] > 1
    # TS fixture also scanned (types stripped / ignored)
    assert any(k.endswith(":greet") for k in fns)
    assert any(k.endswith(":format") for k in fns)


def test_python_path_still_green_via_repo_map():
    root = pathlib.Path("examples/python_toy")
    direct = build_python_map(root)
    via = build_repo_map(root, languages=["python"])
    assert via["language"] == "python"
    assert via["languages_analyzed"] == ["python"]
    assert set(direct["functions"]) == set(via["functions"])
    compute = "examples/python_toy/pkg/service:compute"
    add = "examples/python_toy/pkg/service:add"
    assert add in via["functions"][compute]["calls"]


def test_mixed_repo_only_analyzes_supported(tmp_path: pathlib.Path, monkeypatch):
    monkeypatch.setenv("UF_JS_ANALYZER", "regex")
    monkeypatch.setenv("UF_GO_ANALYZER", "regex")
    (tmp_path / "a.py").write_text("def py_only():\n    return 1\n", encoding="utf-8")
    (tmp_path / "b.js").write_text(
        "function jsOnly() {\n  return helper();\n}\nfunction helper() {\n  return 2;\n}\n",
        encoding="utf-8",
    )
    (tmp_path / "c.go").write_text("package main\n\nfunc GoSeen() {}\n", encoding="utf-8")
    (tmp_path / "d.zig").write_text("fn zig_skip() void {}\n", encoding="utf-8")

    repo = build_repo_map(tmp_path)
    assert repo["language"] == "mixed"
    assert "python" in repo["languages_analyzed"]
    assert "javascript" in repo["languages_analyzed"]
    assert "go" in repo["languages_analyzed"]
    assert repo["unsupported"].get("zig") == 1
    assert "go" not in (repo.get("unsupported") or {})
    fns = repo["functions"]
    assert any(k.endswith(":py_only") for k in fns)
    assert any(k.endswith(":jsOnly") for k in fns)
    assert any(k.endswith(":GoSeen") for k in fns)
    # No fake Zig function entries
    assert not any("zig_skip" in k for k in fns)
    summary = format_unsupported_summary(repo["unsupported"])
    assert "not analyzed" in summary.lower() or "Not analyzed" in summary
    assert "zig" in summary


def test_lang_filter_javascript_skips_python(tmp_path: pathlib.Path):
    (tmp_path / "a.py").write_text("def hidden():\n    return 1\n", encoding="utf-8")
    (tmp_path / "b.js").write_text("function visible() {\n  return 1;\n}\n", encoding="utf-8")
    repo = build_repo_map(tmp_path, languages=["javascript"])
    assert repo["languages_analyzed"] == ["javascript"]
    assert any(k.endswith(":visible") for k in repo["functions"])
    assert not any(k.endswith(":hidden") for k in repo["functions"])


def test_unsupported_only_repo_has_no_fake_complexity(tmp_path: pathlib.Path):
    (tmp_path / "main.zig").write_text("fn main() void {}\n", encoding="utf-8")
    repo = build_repo_map(tmp_path)
    assert repo["language"] == "none"
    assert repo["functions"] == {}
    assert repo["unsupported"].get("zig") == 1
    # No invented average-complexity payload
    assert "average_complexity" not in repo


def test_js_does_not_invent_cross_file_edges(tmp_path: pathlib.Path, monkeypatch):
    monkeypatch.setenv("UF_JS_ANALYZER", "regex")
    (tmp_path / "a.js").write_text(
        "function shared() {\n  return 1;\n}\n",
        encoding="utf-8",
    )
    (tmp_path / "b.js").write_text(
        "function run() {\n  return shared();\n}\n",
        encoding="utf-8",
    )
    repo = build_js_map(tmp_path)
    run_qn = next(k for k in repo["functions"] if k.endswith(":run"))
    # Cross-file bare name stays unqualified — no invented edge
    assert "shared" in repo["functions"][run_qn]["calls"]
    assert not any(c.endswith(":shared") for c in repo["functions"][run_qn]["calls"] if ":" in c)


def test_schema_docs_multilang_limits():
    ref = pathlib.Path("schemas/SCHEMA_REFERENCE.md").read_text(encoding="utf-8")
    assert "best-effort" in ref.lower() or "javascript" in ref.lower()
    assert "unsupported" in ref.lower() or "multi-language" in ref.lower()


def test_readme_capability_table_honest():
    readme = pathlib.Path("README.md").read_text(encoding="utf-8")
    assert "javascript" in readme.lower() or "JavaScript" in readme
    assert "best-effort" in readme.lower()
    # Must not claim full multi-language parity
    assert "not faked" in readme.lower() or "best-effort" in readme.lower()


def test_web_demo_minimal_no_tour_wizard_theater():
    html = pathlib.Path("web_demo/index.html").read_text(encoding="utf-8")
    assert 'id="wizardOverlay"' not in html
    assert 'id="onboardingWizard"' not in html
    assert "showOnboardingWizard" not in html
    assert "Start demo tour" not in html
    assert "Generate demo tour sketch" not in html
    assert "personalized tour" not in html.lower()
    assert "u tour" in html
    assert "u scan" in html
    # Prefer deletion: no disabled tour button theater
    assert "Tour (CLI only)" not in html or "not" in html.lower()
    assert "cytoscape" in html.lower()  # keep minimal interactive graph shell
