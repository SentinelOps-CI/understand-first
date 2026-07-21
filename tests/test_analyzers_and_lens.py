import ast
import pathlib

from cli.ucli.analyzers.python_analyzer import (
    _cyclomatic_complexity,
    _parse_file,
    build_python_map,
)
from cli.ucli.lens.lens import lens_from_seeds, merge_trace_into_lens, rank_by_error_proximity


def test_python_analyzer_builds_map():
    root = pathlib.Path("examples/python_toy")
    m = build_python_map(root)
    assert m.get("language") == "python"
    fns = m.get("functions", {})
    # ensure qualified names from service.py are present
    keys = "\n".join(fns.keys())
    assert "examples/python_toy/pkg/service:add" in keys
    assert "examples/python_toy/pkg/service:compute" in keys
    assert "examples/python_toy/pkg/service:classify" in keys

    add_qn = "examples/python_toy/pkg/service:add"
    compute_qn = "examples/python_toy/pkg/service:compute"
    classify_qn = "examples/python_toy/pkg/service:classify"

    assert fns[add_qn]["complexity"] == 1
    assert fns[compute_qn]["complexity"] == 1
    assert fns[classify_qn]["complexity"] >= 3
    assert compute_qn in fns[add_qn]["callers"]
    # File-local unambiguous callees are qualified for consumers.
    assert add_qn in fns[compute_qn]["calls"]


def test_cyclomatic_complexity_branches_and_boolops(tmp_path: pathlib.Path):
    src = tmp_path / "branchy.py"
    src.write_text(
        "def simple():\n"
        "    return 1\n"
        "\n"
        "def branchy(x, y):\n"
        "    if x and y:\n"
        "        return 1\n"
        "    for i in range(x):\n"
        "        if i > 0:\n"
        "            return i\n"
        "    try:\n"
        "        return x\n"
        "    except ValueError:\n"
        "        return 0\n"
        "\n"
        "async def async_branch(flag):\n"
        "    if flag:\n"
        "        return await helper()\n"
        "    return 0\n"
        "\n"
        "async def helper():\n"
        "    return 1\n",
        encoding="utf-8",
    )
    parsed = _parse_file(src)
    assert parsed["simple"]["complexity"] == 1
    # 1 + if + and(+1) + for + if + except = 6
    assert parsed["branchy"]["complexity"] == 6
    assert parsed["async_branch"]["complexity"] == 2
    assert "helper" in parsed["async_branch"]["calls"]

    tree = ast.parse(src.read_text(encoding="utf-8"))
    funcs = {n.name: n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert _cyclomatic_complexity(funcs["simple"]) == 1
    assert _cyclomatic_complexity(funcs["branchy"]) == 6

    repo = build_python_map(tmp_path)
    helper_qn = next(k for k in repo["functions"] if k.endswith(":helper"))
    async_qn = next(k for k in repo["functions"] if k.endswith(":async_branch"))
    assert async_qn in repo["functions"][helper_qn]["callers"]
    assert repo["functions"][async_qn]["complexity"] == 2


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
