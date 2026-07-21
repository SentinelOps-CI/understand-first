"""Wave 23: Rust syn AST path + regex fallback."""

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


def test_rust_regex_fallback(force_regex):
    m = build_rust_map(pathlib.Path("examples/rust_toy"))
    assert m["analyzer"] == "rust-best-effort"
    assert m["complexity_kind"] == "keyword-heuristic"


@pytest.mark.skipif(not ast_backend_available(), reason="cargo Rust AST worker not available")
def test_rust_ast_path_metadata(force_ast):
    m = build_rust_map(pathlib.Path("examples/rust_toy"))
    assert m["analyzer"] == "rust-ast"
    assert m["analyzer_fidelity"] == "ast"
    assert m["complexity_kind"] == "ast-cyclomatic"
    assert any(k.endswith(":add") for k in m["functions"])
    assert any(k.endswith(":Calc.scale") for k in m["functions"])
    compute = next(k for k in m["functions"] if k.endswith(":compute"))
    assert any(isinstance(c, str) and c.endswith(":add") for c in m["functions"][compute]["calls"])
    classify = next(k for k in m["functions"] if k.endswith(":classify"))
    assert m["functions"][classify]["complexity"] > 1
    # Method call self.scale → bare "scale" may resolve to Calc.scale same-file.
    run = next(k for k in m["functions"] if k.endswith(":Calc.run"))
    assert any(
        isinstance(c, str) and (c.endswith(":Calc.scale") or c.endswith(":compute") or c == "scale")
        for c in m["functions"][run]["calls"]
    )
