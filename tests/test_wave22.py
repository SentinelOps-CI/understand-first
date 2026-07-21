"""Wave 22: Rust best-effort adapter + JS package.json exports resolve."""

from __future__ import annotations

import pathlib

import pytest
from cli.ucli.analyzers.js_analyzer import build_js_map
from cli.ucli.analyzers.js_ast_bridge import ast_backend_available
from cli.ucli.analyzers.registry import build_repo_map, supported_languages
from cli.ucli.analyzers.rust_analyzer import build_rust_map


def test_rust_in_supported_languages():
    assert "rust" in supported_languages()


def test_rust_map_metadata_and_edges(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UF_RUST_ANALYZER", "regex")
    m = build_rust_map(pathlib.Path("examples/rust_toy"))
    assert m["analyzer"] == "rust-best-effort"
    assert m["analyzer_fidelity"] == "best-effort"
    assert m["complexity_kind"] == "keyword-heuristic"
    assert m["language"] == "rust"
    keys = m["functions"]
    assert any(k.endswith(":add") for k in keys)
    assert any(k.endswith(":compute") for k in keys)
    assert any(k.endswith(":classify") for k in keys)
    assert any(k.endswith(":Calc.scale") for k in keys)
    assert any(k.endswith(":Calc.run") for k in keys)

    add = next(k for k in keys if k.endswith(":add"))
    compute = next(k for k in keys if k.endswith(":compute"))
    assert any(
        isinstance(c, str) and (c == add or c.endswith(":add")) for c in keys[compute]["calls"]
    )

    classify = next(k for k in keys if k.endswith(":classify"))
    assert keys[classify]["complexity"] > 1


def test_rust_does_not_invent_cross_file_edges(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("UF_RUST_ANALYZER", "regex")
    (tmp_path / "a.rs").write_text("pub fn helper() -> i32 { 1 }\n", encoding="utf-8")
    (tmp_path / "b.rs").write_text(
        "pub fn run() -> i32 { helper() }\n",
        encoding="utf-8",
    )
    m = build_rust_map(tmp_path)
    run = next(k for k in m["functions"] if k.endswith(":run"))
    assert "helper" in m["functions"][run]["calls"]
    assert not any(
        isinstance(c, str) and c.endswith(":helper") and ":" in c
        for c in m["functions"][run]["calls"]
    )


def test_repo_map_lang_rust(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UF_RUST_ANALYZER", "regex")
    m = build_repo_map(pathlib.Path("examples/rust_toy"), languages=["rust"])
    assert m["language"] == "rust"
    assert "rust" in m["languages_analyzed"]
    assert m.get("analyzer") == "rust-best-effort"
    assert "rs" not in (m.get("unsupported") or {})


@pytest.mark.skipif(not ast_backend_available(), reason="Node+typescript AST worker not installed")
def test_js_package_json_exports_subpath(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UF_JS_ANALYZER", "ast")
    m = build_js_map(pathlib.Path("examples/js_toy"))
    run = next(k for k in m["functions"] if k.endswith(":runMapped"))
    assert any(
        isinstance(c, str) and c.endswith(":mappedUtil") for c in m["functions"][run]["calls"]
    )
    assert any(
        isinstance(c, str) and "exports_target" in c and c.endswith(":mappedUtil")
        for c in m["functions"][run]["calls"]
    )
