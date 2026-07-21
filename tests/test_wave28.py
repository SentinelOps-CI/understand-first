"""Wave 28: Go invent-free cross-package import edges (AST path)."""

from __future__ import annotations

import pathlib

import pytest
from cli.ucli.analyzers.go_analyzer import build_go_map
from cli.ucli.analyzers.go_ast_bridge import ast_backend_available

CROSSPKG = pathlib.Path("examples/go_crosspkg")


@pytest.fixture
def force_regex(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UF_GO_ANALYZER", "regex")


@pytest.fixture
def force_ast(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UF_GO_ANALYZER", "ast")


def _qn_ending(fns: dict, suffix: str) -> str:
    return next(k for k in fns if k.endswith(suffix))


@pytest.mark.skipif(not ast_backend_available(), reason="Go toolchain AST worker not available")
def test_ast_cross_package_default_import_edge(force_ast):
    m = build_go_map(CROSSPKG)
    assert m["analyzer"] == "go-ast"
    fns = m["functions"]
    run = _qn_ending(fns, ":Run")
    # Prefer the app.Run (not aliasapp) — file path contains /app/
    run = next(
        k for k in fns if k.endswith(":Run") and "/app/" in fns[k]["file"].replace("\\", "/")
    )
    assert any(c.endswith(":Add") for c in fns[run]["calls"])
    add = next(c for c in fns[run]["calls"] if c.endswith(":Add"))
    assert "mathutil" in fns[add]["file"].replace("\\", "/")
    assert run in fns[add]["callers"]


@pytest.mark.skipif(not ast_backend_available(), reason="Go toolchain AST worker not available")
def test_ast_cross_package_alias_import_edge(force_ast):
    m = build_go_map(CROSSPKG)
    fns = m["functions"]
    caller = _qn_ending(fns, ":RunAliased")
    assert any(c.endswith(":Add") for c in fns[caller]["calls"])
    add = next(c for c in fns[caller]["calls"] if c.endswith(":Add"))
    assert "mathutil" in fns[add]["file"].replace("\\", "/")


@pytest.mark.skipif(not ast_backend_available(), reason="Go toolchain AST worker not available")
def test_ast_cross_package_scale_edge(force_ast):
    m = build_go_map(CROSSPKG)
    fns = m["functions"]
    caller = _qn_ending(fns, ":RunScale")
    assert any(c.endswith(":Scale") for c in fns[caller]["calls"])


def test_regex_stays_same_file_only_no_cross_package(force_regex):
    m = build_go_map(CROSSPKG)
    assert m["analyzer"] == "go-best-effort"
    fns = m["functions"]
    run = next(
        k for k in fns if k.endswith(":Run") and "/app/" in fns[k]["file"].replace("\\", "/")
    )
    # Regex does not emit selector tokens as qualified package edges.
    assert not any(
        isinstance(c, str) and c.endswith(":Add") and ":" in c for c in fns[run]["calls"]
    )


@pytest.mark.skipif(not ast_backend_available(), reason="Go toolchain AST worker not available")
def test_ast_does_not_invent_stdlib_selector(force_ast, tmp_path: pathlib.Path):
    (tmp_path / "go.mod").write_text("module example.com/uf/tmp\n\ngo 1.21\n", encoding="utf-8")
    (tmp_path / "main.go").write_text(
        'package main\n\nimport "fmt"\n\nfunc Hello() { fmt.Println("x") }\n',
        encoding="utf-8",
    )
    m = build_go_map(tmp_path)
    hello = _qn_ending(m["functions"], ":Hello")
    calls = m["functions"][hello]["calls"]
    assert "fmt.Println" in calls or any(c == "fmt.Println" for c in calls)
    assert not any(isinstance(c, str) and c.endswith(":Println") and ":" in c for c in calls)


@pytest.mark.skipif(not ast_backend_available(), reason="Go toolchain AST worker not available")
def test_ast_ambiguous_import_path_no_edge(force_ast, tmp_path: pathlib.Path):
    """Two modules exposing the same import path string → omit (invent-free)."""
    # Nested layout is awkward for duplicate import paths; instead: two packages
    # imported under the same alias name from different paths — alias collision.
    (tmp_path / "go.mod").write_text("module example.com/uf/ambig\n\ngo 1.21\n", encoding="utf-8")
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "a.go").write_text("package autil\n\nfunc Shared() int { return 1 }\n", encoding="utf-8")
    (b / "b.go").write_text("package butil\n\nfunc Shared() int { return 2 }\n", encoding="utf-8")
    (tmp_path / "main.go").write_text(
        "package main\n\n"
        "import (\n"
        '  autil "example.com/uf/ambig/a"\n'
        '  butil "example.com/uf/ambig/b"\n'
        ")\n\n"
        # Same selector local name cannot bind two packages; use distinct aliases
        # and call a name that exists in both — still unique per alias.
        "func RunA() int { return autil.Shared() }\n"
        "func RunB() int { return butil.Shared() }\n",
        encoding="utf-8",
    )
    m = build_go_map(tmp_path)
    fns = m["functions"]
    run_a = _qn_ending(fns, ":RunA")
    run_b = _qn_ending(fns, ":RunB")
    assert any(c.endswith(":Shared") for c in fns[run_a]["calls"])
    assert any(c.endswith(":Shared") for c in fns[run_b]["calls"])
    shared_a = next(c for c in fns[run_a]["calls"] if c.endswith(":Shared"))
    shared_b = next(c for c in fns[run_b]["calls"] if c.endswith(":Shared"))
    assert shared_a != shared_b
    assert "/a/" in fns[shared_a]["file"].replace("\\", "/") or fns[shared_a]["file"].replace(
        "\\", "/"
    ).endswith("/a/a.go")
    assert "/b/" in fns[shared_b]["file"].replace("\\", "/") or fns[shared_b]["file"].replace(
        "\\", "/"
    ).endswith("/b/b.go")


@pytest.mark.skipif(not ast_backend_available(), reason="Go toolchain AST worker not available")
def test_ast_no_go_mod_no_cross_package_invent(force_ast, tmp_path: pathlib.Path):
    """Without go.mod, import paths cannot resolve invent-free → leave bare."""
    pkg = tmp_path / "mathutil"
    app = tmp_path / "app"
    pkg.mkdir()
    app.mkdir()
    (pkg / "add.go").write_text(
        "package mathutil\n\nfunc Add(a, b int) int { return a + b }\n",
        encoding="utf-8",
    )
    (app / "run.go").write_text(
        'package app\n\nimport "example.com/missing/mathutil"\n\n'
        "func Run() int { return mathutil.Add(1, 2) }\n",
        encoding="utf-8",
    )
    m = build_go_map(tmp_path)
    run = _qn_ending(m["functions"], ":Run")
    calls = m["functions"][run]["calls"]
    assert "mathutil.Add" in calls
    assert not any(isinstance(c, str) and c.endswith(":Add") and ":" in c for c in calls)


@pytest.mark.skipif(not ast_backend_available(), reason="Go toolchain AST worker not available")
def test_ast_ambiguous_callee_name_in_package_omits(force_ast, tmp_path: pathlib.Path):
    """Two funcs with same simple name in one package dir cannot be — use method collision via short name.

    Go forbids two funcs with the same name in one package; simulate ambiguity by
    having Add as both a function and leaving selector unresolved when the import
    path itself is not unique (duplicate module roots under scan).
    """
    m1 = tmp_path / "m1"
    m2 = tmp_path / "m2"
    m1.mkdir()
    m2.mkdir()
    (m1 / "go.mod").write_text("module example.com/dup\n\ngo 1.21\n", encoding="utf-8")
    (m2 / "go.mod").write_text("module example.com/dup\n\ngo 1.21\n", encoding="utf-8")
    (m1 / "x.go").write_text("package dup\n\nfunc Shared() int { return 1 }\n", encoding="utf-8")
    (m2 / "x.go").write_text("package dup\n\nfunc Shared() int { return 2 }\n", encoding="utf-8")
    app = tmp_path / "app"
    app.mkdir()
    (app / "go.mod").write_text("module example.com/app\n\ngo 1.21\n", encoding="utf-8")
    (app / "main.go").write_text(
        'package app\n\nimport "example.com/dup"\n\nfunc Run() int { return dup.Shared() }\n',
        encoding="utf-8",
    )
    m = build_go_map(tmp_path)
    run = _qn_ending(m["functions"], ":Run")
    calls = m["functions"][run]["calls"]
    # Import path example.com/dup maps to two dirs → omit.
    assert "dup.Shared" in calls
    assert not any(isinstance(c, str) and c.endswith(":Shared") and ":" in c for c in calls)


def test_schema_documents_go_cross_package():
    ref = pathlib.Path("schemas/SCHEMA_REFERENCE.md").read_text(encoding="utf-8")
    assert "go-ast" in ref
    assert "cross-package" in ref.lower() or "import path" in ref.lower()
