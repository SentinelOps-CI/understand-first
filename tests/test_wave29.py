"""Wave 29: JS/TS invent-free path-mapping (tsconfig paths + package.json imports)."""

from __future__ import annotations

import pathlib

import pytest
from cli.ucli.analyzers.js_analyzer import build_js_map
from cli.ucli.analyzers.js_ast_bridge import ast_backend_available


@pytest.fixture
def force_js_ast(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UF_JS_ANALYZER", "ast")


@pytest.fixture
def force_js_regex(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("UF_JS_ANALYZER", "regex")


@pytest.mark.skipif(not ast_backend_available(), reason="Node+typescript AST worker not installed")
def test_tsconfig_paths_alias_unique(force_js_ast):
    m = build_js_map(pathlib.Path("examples/js_toy"))
    run = next(k for k in m["functions"] if k.endswith(":runPathMapped"))
    assert any(
        isinstance(c, str) and c.endswith(":pathMappedUtil") for c in m["functions"][run]["calls"]
    )
    assert any(
        isinstance(c, str) and "pathmapped_util" in c and c.endswith(":pathMappedUtil")
        for c in m["functions"][run]["calls"]
    )


@pytest.mark.skipif(not ast_backend_available(), reason="Node+typescript AST worker not installed")
def test_package_json_imports_hash_unique(force_js_ast):
    m = build_js_map(pathlib.Path("examples/js_toy"))
    run = next(k for k in m["functions"] if k.endswith(":runHashMapped"))
    assert any(
        isinstance(c, str) and c.endswith(":hashMappedUtil") for c in m["functions"][run]["calls"]
    )
    assert any(
        isinstance(c, str) and "hash_mapped" in c and c.endswith(":hashMappedUtil")
        for c in m["functions"][run]["calls"]
    )


@pytest.mark.skipif(not ast_backend_available(), reason="Node+typescript AST worker not installed")
def test_ambiguous_tsconfig_paths_do_not_invent(
    tmp_path: pathlib.Path, force_js_ast, monkeypatch: pytest.MonkeyPatch
):
    """Two path targets that both exist → omit cross-file edge (fail closed)."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "tsconfig.json").write_text(
        '{\n  "compilerOptions": {\n    "baseUrl": ".",\n'
        '    "paths": { "@dup/*": ["a/*", "b/*"] }\n  }\n}\n',
        encoding="utf-8",
    )
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    (tmp_path / "a" / "util.ts").write_text(
        "export function shared() { return 1; }\n",
        encoding="utf-8",
    )
    (tmp_path / "b" / "util.ts").write_text(
        "export function shared() { return 2; }\n",
        encoding="utf-8",
    )
    (tmp_path / "consumer.ts").write_text(
        'import { shared } from "@dup/util";\nexport function run() { return shared(); }\n',
        encoding="utf-8",
    )
    m = build_js_map(tmp_path)
    run = next(k for k in m["functions"] if k.endswith(":run"))
    calls = m["functions"][run]["calls"]
    assert "shared" in calls or any(c == "shared" for c in calls)
    assert not any(isinstance(c, str) and ":" in c and c.endswith(":shared") for c in calls)


@pytest.mark.skipif(not ast_backend_available(), reason="Node+typescript AST worker not installed")
def test_bare_npm_package_not_invented(
    tmp_path: pathlib.Path, force_js_ast, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "tsconfig.json").write_text(
        '{\n  "compilerOptions": { "baseUrl": ".", "paths": { "@lib/*": ["lib/*"] } }\n}\n',
        encoding="utf-8",
    )
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "ok.ts").write_text(
        "export function ok() { return 1; }\n",
        encoding="utf-8",
    )
    (tmp_path / "consumer.ts").write_text(
        'import { ok } from "@lib/ok";\n'
        'import { map } from "lodash";\n'
        "export function run() { return ok() + map([]); }\n",
        encoding="utf-8",
    )
    m = build_js_map(tmp_path)
    run = next(k for k in m["functions"] if k.endswith(":run"))
    calls = m["functions"][run]["calls"]
    assert any(isinstance(c, str) and c.endswith(":ok") for c in calls)
    assert not any(isinstance(c, str) and "lodash" in c and ":" in c for c in calls)
    assert "map" in calls or any(c == "map" for c in calls)


def test_regex_path_does_not_invent_pathmap_edges(force_js_regex):
    m = build_js_map(pathlib.Path("examples/js_toy"))
    run = next((k for k in m["functions"] if k.endswith(":runPathMapped")), None)
    if run is None:
        pytest.skip("pathmap_importer.ts not visible to regex path")
    calls = m["functions"][run]["calls"]
    assert "pathMappedUtil" in calls or any(c == "pathMappedUtil" for c in calls)
    assert not any(isinstance(c, str) and ":" in c and c.endswith(":pathMappedUtil") for c in calls)


@pytest.mark.skipif(not ast_backend_available(), reason="Node+typescript AST worker not installed")
def test_analyzer_note_documents_path_mapping_limits(force_js_ast):
    m = build_js_map(pathlib.Path("examples/js_toy"))
    note = (m.get("analyzer_note") or "").lower()
    assert "paths" in note or "tsconfig" in note
    assert "not typechecked" in note or "typecheck" in note
