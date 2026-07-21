"""Wave 24: C# best-effort adapter + optional Roslyn AST path."""

from __future__ import annotations

import pathlib

import pytest
from cli.ucli.analyzers.csharp_analyzer import build_csharp_map
from cli.ucli.analyzers.csharp_ast_bridge import ast_backend_available
from cli.ucli.analyzers.registry import build_repo_map, supported_languages


@pytest.fixture
def force_regex(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UF_CSHARP_ANALYZER", "regex")


@pytest.fixture
def force_ast(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UF_CSHARP_ANALYZER", "ast")


def test_csharp_in_supported_languages():
    assert "csharp" in supported_languages()


def test_csharp_map_metadata_and_edges(force_regex):
    m = build_csharp_map(pathlib.Path("examples/csharp_toy"))
    assert m["analyzer"] == "csharp-best-effort"
    assert m["analyzer_fidelity"] == "best-effort"
    assert m["complexity_kind"] == "keyword-heuristic"
    assert m["language"] == "csharp"
    keys = m["functions"]
    assert any(k.endswith(":MathUtil.Add") for k in keys)
    assert any(k.endswith(":MathUtil.Compute") for k in keys)
    assert any(k.endswith(":MathUtil.Classify") for k in keys)
    assert any(k.endswith(":Calc.Scale") for k in keys)
    assert any(k.endswith(":Calc.Run") for k in keys)

    add = next(k for k in keys if k.endswith(":MathUtil.Add"))
    compute = next(k for k in keys if k.endswith(":MathUtil.Compute"))
    assert any(
        isinstance(c, str) and (c == add or c.endswith(":MathUtil.Add"))
        for c in keys[compute]["calls"]
    )

    classify = next(k for k in keys if k.endswith(":MathUtil.Classify"))
    assert keys[classify]["complexity"] > 1

    run = next(k for k in keys if k.endswith(":Calc.Run"))
    assert any(
        isinstance(c, str) and (c.endswith(":Calc.Scale") or c == "Scale")
        for c in keys[run]["calls"]
    )


def test_csharp_same_namespace_unique_edge(force_regex):
    m = build_csharp_map(pathlib.Path("examples/csharp_toy"))
    run_shared = next(k for k in m["functions"] if k.endswith(":Importer.RunShared"))
    assert any(
        isinstance(c, str) and c.endswith(":Helper.HelperFn")
        for c in m["functions"][run_shared]["calls"]
    )


def test_csharp_does_not_invent_cross_namespace_edges(tmp_path: pathlib.Path, force_regex):
    (tmp_path / "a.cs").write_text(
        "\n".join(
            [
                "namespace A;",
                "public static class X",
                "{",
                "  public static int Helper()",
                "  {",
                "    return 1;",
                "  }",
                "}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "b.cs").write_text(
        "\n".join(
            [
                "namespace B;",
                "public static class Y",
                "{",
                "  public static int Run()",
                "  {",
                "    return Helper();",
                "  }",
                "}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    m = build_csharp_map(tmp_path)
    run = next(k for k in m["functions"] if k.endswith(":Y.Run"))
    assert "Helper" in m["functions"][run]["calls"]
    assert not any(
        isinstance(c, str) and c.endswith(":X.Helper") and ":" in c
        for c in m["functions"][run]["calls"]
    )


def test_csharp_unique_type_method_edge(force_regex):
    """Wave 27: unique Type.Method in the same namespace is qualified (not invented)."""
    m = build_csharp_map(pathlib.Path("examples/csharp_toy"))
    scale = next(k for k in m["functions"] if k.endswith(":Calc.Scale"))
    assert any(
        isinstance(c, str) and c.endswith(":MathUtil.Add") for c in m["functions"][scale]["calls"]
    )


def test_repo_map_lang_csharp(force_regex):
    m = build_repo_map(pathlib.Path("examples/csharp_toy"), languages=["csharp"])
    assert m["language"] == "csharp"
    assert "csharp" in m["languages_analyzed"]
    assert m.get("analyzer") == "csharp-best-effort"
    assert "cs" not in (m.get("unsupported") or {})


def test_csharp_not_in_unsupported_inventory(tmp_path: pathlib.Path, force_regex):
    (tmp_path / "Main.cs").write_text(
        "\n".join(
            [
                "namespace T;",
                "public class Main",
                "{",
                "  public static void Run()",
                "  {",
                "  }",
                "}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    m = build_repo_map(tmp_path)
    assert "csharp" in m["languages_analyzed"]
    assert "cs" not in (m.get("unsupported") or {})


@pytest.mark.skipif(not ast_backend_available(), reason="dotnet SDK C# AST worker not available")
def test_csharp_ast_path_metadata(force_ast):
    m = build_csharp_map(pathlib.Path("examples/csharp_toy"))
    assert m["analyzer"] == "csharp-ast"
    assert m["analyzer_fidelity"] == "ast"
    assert m["complexity_kind"] == "ast-cyclomatic"
    assert any(k.endswith(":MathUtil.Add") for k in m["functions"])
    assert any(k.endswith(":Calc.Scale") for k in m["functions"])
    compute = next(k for k in m["functions"] if k.endswith(":MathUtil.Compute"))
    assert any(
        isinstance(c, str) and c.endswith(":MathUtil.Add") for c in m["functions"][compute]["calls"]
    )
    classify = next(k for k in m["functions"] if k.endswith(":MathUtil.Classify"))
    assert m["functions"][classify]["complexity"] > 1
    run = next(k for k in m["functions"] if k.endswith(":Calc.Run"))
    assert any(
        isinstance(c, str) and (c.endswith(":Calc.Scale") or c == "Scale")
        for c in m["functions"][run]["calls"]
    )
