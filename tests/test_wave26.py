"""Wave 26: Rust invent-free cross-module mod/use edges."""

from __future__ import annotations

import pathlib

import pytest
from cli.ucli.analyzers.rust_analyzer import build_rust_map
from cli.ucli.analyzers.rust_ast_bridge import ast_backend_available


@pytest.fixture
def force_regex(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UF_RUST_ANALYZER", "regex")


@pytest.fixture
def force_ast(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UF_RUST_ANALYZER", "ast")


def test_rust_use_gated_cross_module_edge(force_regex):
    m = build_rust_map(pathlib.Path("examples/rust_toy"))
    run = next(k for k in m["functions"] if k.endswith(":run_imported"))
    assert any(
        isinstance(c, str) and c.endswith(":helper_fn") for c in m["functions"][run]["calls"]
    )


def test_rust_mod_path_cross_module_edge(force_regex):
    m = build_rust_map(pathlib.Path("examples/rust_toy"))
    run = next(k for k in m["functions"] if k.endswith(":run_mod_path"))
    assert any(isinstance(c, str) and c.endswith(":other_fn") for c in m["functions"][run]["calls"])


def test_rust_same_file_baseline_still_works(force_regex):
    m = build_rust_map(pathlib.Path("examples/rust_toy"))
    compute = next(k for k in m["functions"] if k.endswith(":compute"))
    assert any(isinstance(c, str) and c.endswith(":add") for c in m["functions"][compute]["calls"])


def test_rust_does_not_invent_without_mod_use(tmp_path: pathlib.Path, force_regex):
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


def test_rust_omits_ambiguous_cross_module_edges(tmp_path: pathlib.Path, force_regex):
    (tmp_path / "lib.rs").write_text(
        "\n".join(
            [
                "mod left;",
                "mod right;",
                "use left::shared;",
                "use right::shared as shared_r;",
                "pub fn run() -> i32 { shared() }",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "left.rs").write_text(
        "pub fn shared() -> i32 { 1 }\n",
        encoding="utf-8",
    )
    (tmp_path / "right.rs").write_text(
        "pub fn shared() -> i32 { 2 }\n",
        encoding="utf-8",
    )
    m = build_rust_map(tmp_path)
    run = next(k for k in m["functions"] if k.endswith(":run"))
    # use left::shared uniquely binds `shared` → left::shared only.
    assert any(
        isinstance(c, str) and "left" in c and c.endswith(":shared")
        for c in m["functions"][run]["calls"]
    )
    assert not any(
        isinstance(c, str) and "right" in c and c.endswith(":shared")
        for c in m["functions"][run]["calls"]
    )


def test_rust_omits_when_two_mods_export_same_bare_name(tmp_path: pathlib.Path, force_regex):
    """Bare call with only `mod` evidence and duplicate names → omit."""
    (tmp_path / "lib.rs").write_text(
        "\n".join(
            [
                "mod left;",
                "mod right;",
                "pub fn run() -> i32 { twin() }",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "left.rs").write_text("pub fn twin() -> i32 { 1 }\n", encoding="utf-8")
    (tmp_path / "right.rs").write_text("pub fn twin() -> i32 { 2 }\n", encoding="utf-8")
    m = build_rust_map(tmp_path)
    run = next(k for k in m["functions"] if k.endswith(":run"))
    assert "twin" in m["functions"][run]["calls"]
    assert not any(
        isinstance(c, str) and c.endswith(":twin") and ":" in c
        for c in m["functions"][run]["calls"]
    )


@pytest.mark.skipif(not ast_backend_available(), reason="cargo Rust AST worker not available")
def test_rust_ast_cross_module_edges(force_ast):
    m = build_rust_map(pathlib.Path("examples/rust_toy"))
    assert m["analyzer"] == "rust-ast"
    run_imported = next(k for k in m["functions"] if k.endswith(":run_imported"))
    assert any(
        isinstance(c, str) and c.endswith(":helper_fn")
        for c in m["functions"][run_imported]["calls"]
    )
    run_mod = next(k for k in m["functions"] if k.endswith(":run_mod_path"))
    assert any(
        isinstance(c, str) and c.endswith(":other_fn") for c in m["functions"][run_mod]["calls"]
    )
