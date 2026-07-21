"""Wave 16: JS adapter hardening, lens/tour/diff honesty, CI multilang smoke."""

from __future__ import annotations

import os
import pathlib

from cli.ucli.analyzers.js_analyzer import build_js_map
from cli.ucli.analyzers.map_meta import (
    annotate_lens_from_map,
    lens_runtime_trace_supported,
    map_fidelity_label,
)
from cli.ucli.analyzers.registry import build_repo_map
from cli.ucli.commands.diff_ops import compute_map_delta
from cli.ucli.lens.lens import lens_from_seeds, write_tour_md


def test_js_map_metadata_and_complexity_kind():
    # Force regex so this Wave 16 contract stays stable when AST deps are present.
    os.environ["UF_JS_ANALYZER"] = "regex"
    try:
        m = build_js_map(pathlib.Path("examples/js_toy"))
        assert m["analyzer"] in {"javascript-best-effort", "typescript-best-effort"}
        assert m["analyzer_fidelity"] == "best-effort"
        assert m["complexity_kind"] == "keyword-heuristic"
        assert m["language"] in {"javascript", "typescript"}
        for meta in m["functions"].values():
            assert "best-effort" in meta.get("analyzer", "")
            assert meta.get("complexity_kind") == "keyword-heuristic"
            assert meta.get("language") in {"javascript", "typescript"}
        via = build_repo_map(pathlib.Path("examples/js_toy"), languages=["javascript"])
        assert via["analyzer"] in {"javascript-best-effort", "typescript-best-effort"}
        assert via["complexity_kind"] == "keyword-heuristic"
    finally:
        os.environ.pop("UF_JS_ANALYZER", None)


def test_js_async_mjs_and_cjs_fixtures():
    m = build_js_map(pathlib.Path("examples/js_toy"))
    keys = "\n".join(m["functions"])
    assert "async_mod:fetchLabel" in keys or "examples/js_toy/async_mod:fetchLabel" in keys
    assert any(k.endswith(":pipe") for k in m["functions"])
    assert any(k.endswith(":double") for k in m["functions"])
    fetch = next(k for k in m["functions"] if k.endswith(":fetchLabel"))
    # same-file calls qualify when unique
    assert any(
        c.endswith(":loadRaw") or c.endswith(":formatLabel") or c in {"loadRaw", "formatLabel"}
        for c in m["functions"][fetch]["calls"]
    )


def test_ts_types_demo_best_effort_strip():
    m = build_js_map(pathlib.Path("examples/js_toy"))
    assert any(k.endswith(":summarize") for k in m["functions"])
    assert any(k.endswith(":joinName") for k in m["functions"])
    # interface/type names must not appear as fake functions
    assert not any(k.endswith(":Person") or k.endswith(":Id") for k in m["functions"])


def test_lens_and_tour_on_js_map():
    os.environ["UF_JS_ANALYZER"] = "regex"
    try:
        repo = build_repo_map(pathlib.Path("examples/js_toy"), languages=["javascript"])
        lens = lens_from_seeds(["compute"], repo)
        assert lens["language"] in {"javascript", "typescript"}
        assert lens["lens"].get("fidelity") == "best-effort"
        assert (
            "keyword" in (lens["lens"].get("complexity_note") or "").lower()
            or "heuristic" in (lens["lens"].get("complexity_note") or "").lower()
        )
        assert any(k.endswith(":compute") for k in lens["functions"])
        # qualified same-file edge expands neighborhood to add
        assert any(k.endswith(":add") for k in lens["functions"])
        md = write_tour_md(lens)
        assert "Map fidelity" in md
        assert "Python-only" in md or "best-effort" in md.lower()
    finally:
        os.environ.pop("UF_JS_ANALYZER", None)


def test_tour_run_refuses_js_only_lens():
    repo = build_repo_map(pathlib.Path("examples/js_toy"), languages=["javascript"])
    lens = lens_from_seeds(["compute"], repo)
    assert lens_runtime_trace_supported(lens) is False


def test_diff_labels_js_heuristic_complexity(tmp_path: pathlib.Path):
    os.environ["UF_JS_ANALYZER"] = "regex"
    try:
        (tmp_path / "a.js").write_text(
            "function a() {\n  return 1;\n}\n",
            encoding="utf-8",
        )
        old = build_js_map(tmp_path)
        (tmp_path / "a.js").write_text(
            "function a() {\n  if (true) {\n    return 1;\n  }\n  return 0;\n}\n"
            "function b() {\n  return a();\n}\n",
            encoding="utf-8",
        )
        new = build_js_map(tmp_path)
        delta = compute_map_delta(old, new)
        assert delta["summary"]["old_fidelity"] == "best-effort"
        assert delta["summary"]["new_fidelity"] == "best-effort"
        note = delta["summary"]["complexity_note"].lower()
        assert "heuristic" in note or "not mccabe" in note
        assert "mccabe" not in note or "not" in note
    finally:
        os.environ.pop("UF_JS_ANALYZER", None)


def test_diff_python_still_mccabe_note():
    repo = build_repo_map(pathlib.Path("examples/python_toy"), languages=["python"])
    delta = compute_map_delta(repo, repo)
    assert delta["summary"]["old_fidelity"] == "ast"
    assert "McCabe" in delta["summary"]["complexity_note"]


def test_repo_map_complexity_kind_fields():
    os.environ["UF_JS_ANALYZER"] = "regex"
    try:
        mixed = build_repo_map(pathlib.Path("examples"))
        # examples/ has both python_toy and js_toy (+ more)
        assert mixed["language"] in {"mixed", "python", "javascript"}
        if mixed["language"] == "mixed":
            assert mixed["complexity_kind"] == "mixed"
        py = build_repo_map(pathlib.Path("examples/python_toy"))
        assert py["complexity_kind"] == "mccabe"
        js = build_repo_map(pathlib.Path("examples/js_toy"), languages=["javascript"])
        assert js["complexity_kind"] == "keyword-heuristic"
    finally:
        os.environ.pop("UF_JS_ANALYZER", None)


def test_annotate_preserves_unsupported():
    repo = {
        "language": "javascript",
        "analyzer_fidelity": {"javascript": "best-effort"},
        "unsupported": {"go": 2},
        "functions": {},
    }
    lens = annotate_lens_from_map({"lens": {"seeds": []}, "functions": {}}, repo)
    assert lens["lens"]["unsupported"] == {"go": 2}
    assert map_fidelity_label(lens) == "best-effort"


def test_web_demo_only_index_remains():
    demo = pathlib.Path("web_demo")
    names = sorted(p.name for p in demo.iterdir() if p.is_file())
    assert names == ["index.html"]
    html = (demo / "index.html").read_text(encoding="utf-8")
    assert "cytoscape" in html.lower()
    assert "performance.js" not in html
    assert "u scan" in html


def test_schema_documents_complexity_kind():
    schema = pathlib.Path("schemas/map-schema.json").read_text(encoding="utf-8")
    ref = pathlib.Path("schemas/SCHEMA_REFERENCE.md").read_text(encoding="utf-8")
    assert "complexity_kind" in schema or "keyword-heuristic" in ref.lower()
    assert "best-effort" in ref.lower()


def test_ci_has_multilang_smoke():
    ci = pathlib.Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "multilang-smoke" in ci
    assert "examples/js_toy" in ci
    assert "tour_run" in ci


def test_cli_tour_run_underscore_name_refuses_js(tmp_path: pathlib.Path):
    """Docs/CI invoke ``u tour_run`` (underscore); Typer must not only expose tour-run."""
    import json
    import os
    import subprocess
    import sys

    repo = build_repo_map(pathlib.Path("examples/js_toy"), languages=["javascript"])
    lens = lens_from_seeds(["compute"], repo)
    lens_path = tmp_path / "lens.json"
    lens_path.write_text(json.dumps(lens), encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONPATH"] = "cli"
    proc = subprocess.run(
        [sys.executable, "-m", "ucli.main", "tour_run", str(lens_path)],
        cwd=pathlib.Path.cwd(),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 1
    combined = (proc.stdout or "") + (proc.stderr or "")
    assert "refused" in combined.lower() or "Python-only" in combined
