"""Wave 20: Java best-effort adapter, same-package edges, registry honesty."""

from __future__ import annotations

import pathlib

import pytest
from cli.ucli.analyzers.java_analyzer import build_java_map
from cli.ucli.analyzers.registry import build_repo_map, supported_languages


def test_java_in_supported_languages():
    assert "java" in supported_languages()


def test_java_map_metadata_and_defs(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UF_JAVA_ANALYZER", "regex")
    m = build_java_map(pathlib.Path("examples/java_toy"))
    assert m["analyzer"] == "java-best-effort"
    assert m["analyzer_fidelity"] == "best-effort"
    assert m["complexity_kind"] == "keyword-heuristic"
    assert m["language"] == "java"
    keys = m["functions"]
    assert any(k.endswith(":MathUtil.add") for k in keys)
    assert any(k.endswith(":MathUtil.compute") for k in keys)
    assert any(k.endswith(":MathUtil.classify") for k in keys)
    assert any(k.endswith(":Calc.scale") for k in keys)
    assert any(k.endswith(":Helper.helper") for k in keys)
    assert any(k.endswith(":Importer.runShared") for k in keys)

    add = next(k for k in keys if k.endswith(":MathUtil.add"))
    compute = next(k for k in keys if k.endswith(":MathUtil.compute"))
    assert any(
        isinstance(c, str) and (c == add or c.endswith(":MathUtil.add"))
        for c in keys[compute]["calls"]
    )

    classify = next(k for k in keys if k.endswith(":MathUtil.classify"))
    assert keys[classify]["complexity"] > 1


def test_java_same_package_unique_edge(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UF_JAVA_ANALYZER", "regex")
    m = build_java_map(pathlib.Path("examples/java_toy"))
    run = next(k for k in m["functions"] if k.endswith(":Importer.runShared"))
    assert any(
        isinstance(c, str) and c.endswith(":Helper.helper") for c in m["functions"][run]["calls"]
    )


def test_java_does_not_invent_dotted_cross_type_edges(monkeypatch: pytest.MonkeyPatch):
    """MathUtil.add via MathUtil.add(...) stays unresolved (dotted), not invented."""
    monkeypatch.setenv("UF_JAVA_ANALYZER", "regex")
    m = build_java_map(pathlib.Path("examples/java_toy"))
    scale = next(k for k in m["functions"] if k.endswith(":Calc.scale"))
    # Must not invent a qualified edge from a Type.method call expression.
    assert not any(
        isinstance(c, str) and c.endswith(":MathUtil.add") for c in m["functions"][scale]["calls"]
    )


def test_repo_map_lang_java(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UF_JAVA_ANALYZER", "regex")
    m = build_repo_map(pathlib.Path("examples/java_toy"), languages=["java"])
    assert m["language"] == "java"
    assert "java" in m["languages_analyzed"]
    assert m.get("analyzer") == "java-best-effort"
    assert "java" not in (m.get("unsupported") or {})


def test_java_not_in_unsupported_inventory(tmp_path: pathlib.Path):
    (tmp_path / "Main.java").write_text(
        "package p;\npublic class Main { public void run() {} }\n",
        encoding="utf-8",
    )
    (tmp_path / "x.zig").write_text("fn main() void {}\n", encoding="utf-8")
    m = build_repo_map(tmp_path)
    assert "java" in m["languages_analyzed"]
    assert (m.get("unsupported") or {}).get("zig") == 1
