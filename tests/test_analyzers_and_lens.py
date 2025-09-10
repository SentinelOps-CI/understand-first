from cli.ucli.analyzers.python_analyzer import build_python_map
from cli.ucli.lens.lens import lens_from_seeds, merge_trace_into_lens, rank_by_error_proximity
import pathlib


def test_python_analyzer_builds_map():
    root = pathlib.Path("examples/python_toy")
    m = build_python_map(root)
    assert m.get("language") == "python"
    fns = m.get("functions", {})
    # ensure qualified names from service.py are present
    keys = "\n".join(fns.keys())
    assert "examples/python_toy/pkg/service:add" in keys
    assert "examples/python_toy/pkg/service:compute" in keys


def test_lens_rank_and_merge_trace():
    root = pathlib.Path("examples/python_toy")
    repo_map = build_python_map(root)
    lens = lens_from_seeds(["compute"], repo_map)
    # fake a trace that hits 'add'
    trace = {
        "events": [{"type": "call", "func": "add", "file": "examples/python_toy/pkg/service.py"}]
    }
    merged = merge_trace_into_lens(lens, trace)
    rank_by_error_proximity(merged)
    fns = merged.get("functions", {})
    # at least one function should carry runtime_hit
    assert any(meta.get("runtime_hit") for meta in fns.values())
    # error_proximity should be computed
    assert all("error_proximity" in meta for meta in fns.values())
