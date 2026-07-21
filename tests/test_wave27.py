"""Wave 27: C# invent-free using / ProjectReference edges."""

from __future__ import annotations

import pathlib

import pytest
from cli.ucli.analyzers.csharp_analyzer import build_csharp_map
from cli.ucli.analyzers.csharp_ast_bridge import ast_backend_available

CROSS_NS = pathlib.Path("examples/csharp_toy/cross_ns")


@pytest.fixture
def force_regex(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UF_CSHARP_ANALYZER", "regex")


@pytest.fixture
def force_ast(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UF_CSHARP_ANALYZER", "ast")


def test_using_unique_simple_name_edge(force_regex):
    m = build_csharp_map(CROSS_NS)
    run = next(k for k in m["functions"] if k.endswith(":Consumer.RunUnique"))
    assert any(
        isinstance(c, str) and c.endswith(":UniqueSvc.UniqueOp")
        for c in m["functions"][run]["calls"]
    )


def test_using_unique_type_method_edge(force_regex):
    m = build_csharp_map(CROSS_NS)
    run = next(k for k in m["functions"] if k.endswith(":Consumer.RunTyped"))
    assert any(
        isinstance(c, str) and c.endswith(":UniqueSvc.UniqueOp")
        for c in m["functions"][run]["calls"]
    )


def test_using_alias_type_target(force_regex):
    m = build_csharp_map(CROSS_NS)
    run = next(k for k in m["functions"] if k.endswith(":Consumer.RunAliased"))
    assert any(
        isinstance(c, str) and c.endswith(":UniqueSvc.UniqueOp")
        for c in m["functions"][run]["calls"]
    )


def test_project_ref_makes_clash_unique(force_regex):
    """App refs Lib only; Toy.Other Clash is not project-visible → Lib Clash wins."""
    m = build_csharp_map(CROSS_NS)
    run = next(k for k in m["functions"] if k.endswith(":Consumer.RunClashVisible"))
    assert any(
        isinstance(c, str) and c.endswith(":UniqueSvc.Clash") for c in m["functions"][run]["calls"]
    )
    assert not any(
        isinstance(c, str) and c.endswith(":OtherSvc.Clash") for c in m["functions"][run]["calls"]
    )


def test_orphan_using_without_project_ref_does_not_invent(force_regex):
    m = build_csharp_map(CROSS_NS)
    run = next(k for k in m["functions"] if k.endswith(":OrphanConsumer.Run"))
    assert "UniqueOp" in m["functions"][run]["calls"]
    assert not any(
        isinstance(c, str) and c.endswith(":UniqueSvc.UniqueOp") and ":" in c
        for c in m["functions"][run]["calls"]
    )


def test_ambiguous_using_simple_names_not_invented(tmp_path: pathlib.Path, force_regex):
    """Two imported namespaces each define Clash — leave bare (no invent)."""
    (tmp_path / "a.cs").write_text(
        "\n".join(
            [
                "namespace Ns.A;",
                "public static class A",
                "{",
                "  public static int Clash() => 1;",
                "}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "b.cs").write_text(
        "\n".join(
            [
                "namespace Ns.B;",
                "public static class B",
                "{",
                "  public static int Clash() => 2;",
                "}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "c.cs").write_text(
        "\n".join(
            [
                "namespace Ns.C;",
                "using Ns.A;",
                "using Ns.B;",
                "public static class C",
                "{",
                "  public static int Run() => Clash();",
                "}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    m = build_csharp_map(tmp_path)
    run = next(k for k in m["functions"] if k.endswith(":C.Run"))
    assert "Clash" in m["functions"][run]["calls"]
    assert not any(
        isinstance(c, str) and c.endswith(":Clash") and ":" in c
        for c in m["functions"][run]["calls"]
    )


def test_ambiguous_type_method_not_invented(tmp_path: pathlib.Path, force_regex):
    """Two types named Twin in different imported namespaces — Twin.Go stays bare."""
    (tmp_path / "a.cs").write_text(
        "\n".join(
            [
                "namespace Ns.A;",
                "public static class Twin",
                "{",
                "  public static int Go() => 1;",
                "}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "b.cs").write_text(
        "\n".join(
            [
                "namespace Ns.B;",
                "public static class Twin",
                "{",
                "  public static int Go() => 2;",
                "}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "c.cs").write_text(
        "\n".join(
            [
                "namespace Ns.C;",
                "using Ns.A;",
                "using Ns.B;",
                "public static class C",
                "{",
                "  public static int Run() => Twin.Go();",
                "}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    m = build_csharp_map(tmp_path)
    run = next(k for k in m["functions"] if k.endswith(":C.Run"))
    assert "Twin.Go" in m["functions"][run]["calls"]
    assert not any(
        isinstance(c, str) and c.endswith(":Twin.Go") and ":" in c
        for c in m["functions"][run]["calls"]
    )


def test_same_namespace_unique_type_method(force_regex):
    """Wave 27: MathUtil.Add is a unique type target in namespace Toy."""
    m = build_csharp_map(pathlib.Path("examples/csharp_toy"))
    scale = next(k for k in m["functions"] if k.endswith(":Calc.Scale"))
    assert any(
        isinstance(c, str) and c.endswith(":MathUtil.Add") for c in m["functions"][scale]["calls"]
    )


def test_cross_namespace_without_using_still_omitted(tmp_path: pathlib.Path, force_regex):
    (tmp_path / "a.cs").write_text(
        "\n".join(
            [
                "namespace A;",
                "public static class X",
                "{",
                "  public static int Helper() => 1;",
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
                "  public static int Run() => Helper();",
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


@pytest.mark.skipif(not ast_backend_available(), reason="dotnet SDK C# AST worker not available")
def test_using_edges_on_ast_path(force_ast):
    m = build_csharp_map(CROSS_NS)
    assert m["analyzer"] == "csharp-ast"
    run = next(k for k in m["functions"] if k.endswith(":Consumer.RunUnique"))
    assert any(
        isinstance(c, str) and c.endswith(":UniqueSvc.UniqueOp")
        for c in m["functions"][run]["calls"]
    )
    typed = next(k for k in m["functions"] if k.endswith(":Consumer.RunTyped"))
    assert any(
        isinstance(c, str) and c.endswith(":UniqueSvc.UniqueOp")
        for c in m["functions"][typed]["calls"]
    )
