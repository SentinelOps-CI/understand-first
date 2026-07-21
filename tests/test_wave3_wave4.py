"""Wave 3/4 remediation regressions: side_effects, callers, delta, contracts AST."""

from __future__ import annotations

import pathlib

from cli.ucli.analyzers.python_analyzer import _parse_file, build_python_map
from cli.ucli.commands.diff_ops import compute_map_delta
from cli.ucli.contracts.contracts import _exists_module_func, check_contracts
from cli.ucli.glossary.build import build_glossary


def test_side_effects_heuristics(tmp_path: pathlib.Path):
    src = tmp_path / "effects.py"
    src.write_text(
        "COUNTER = 0\n"
        "\n"
        "def pure(a, b):\n"
        "    return a + b\n"
        "\n"
        "def mutator(obj, path):\n"
        "    global COUNTER\n"
        "    COUNTER += 1\n"
        "    obj.x = 1\n"
        "    with open(path, 'w') as f:\n"
        "        f.write('hi')\n"
        "    print('done')\n"
        "\n"
        "def netty():\n"
        "    import requests\n"
        "    return requests.get('https://example.com')\n"
        "\n"
        "def loggy(logger):\n"
        "    logger.info('x')\n",
        encoding="utf-8",
    )
    parsed = _parse_file(src)
    assert parsed["pure"]["side_effects"] == []
    assert "writes_global" in parsed["mutator"]["side_effects"]
    assert "writes_attribute" in parsed["mutator"]["side_effects"]
    assert "io_open" in parsed["mutator"]["side_effects"]
    assert "io_write" in parsed["mutator"]["side_effects"]
    assert "io_print" in parsed["mutator"]["side_effects"]
    assert "network_call" in parsed["netty"]["side_effects"]
    assert "logging" in parsed["loggy"]["side_effects"]

    repo = build_python_map(tmp_path)
    mut_qn = next(k for k in repo["functions"] if k.endswith(":mutator"))
    assert repo["functions"][mut_qn]["side_effects"]


def test_callers_prefer_same_file(tmp_path: pathlib.Path):
    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    a.write_text(
        "def helper():\n    return 1\n\ndef caller():\n    return helper()\n",
        encoding="utf-8",
    )
    b.write_text(
        "def helper():\n    return 2\n",
        encoding="utf-8",
    )
    repo = build_python_map(tmp_path)
    a_helper = next(
        k for k in repo["functions"] if k.endswith("a:helper") or k.endswith("/a:helper")
    )
    b_helper = next(
        k for k in repo["functions"] if k.endswith("b:helper") or k.endswith("/b:helper")
    )
    a_caller = next(k for k in repo["functions"] if k.endswith(":caller"))
    # Same-file preference: only a.helper gets the caller edge
    assert a_caller in repo["functions"][a_helper]["callers"]
    assert a_caller not in repo["functions"][b_helper]["callers"]


def test_compute_map_delta_complexity_and_side_effects():
    old = {
        "functions": {
            "m:foo": {"complexity": 2, "side_effects": []},
            "m:bar": {"complexity": 8, "side_effects": ["io_print"]},
        }
    }
    new = {
        "functions": {
            "m:foo": {"complexity": 5, "side_effects": ["io_open"]},
            "m:baz": {"complexity": 1, "side_effects": []},
        }
    }
    delta = compute_map_delta(old, new, policy_threshold=3)
    assert delta["summary"]["added"] == 1
    assert delta["summary"]["removed"] == 1
    assert delta["summary"]["modified"] == 1
    assert delta["complexity_delta"]["net_change"] == (5 + 1) - (2 + 8)
    assert any(x["function"] == "m:foo" for x in delta["complexity_delta"]["increased"])
    assert delta["summary"]["side_effects_added"] >= 1
    assert any(b["function"] == "m:foo" for b in delta["policy_breaches"])


def test_check_contracts_uses_ast_not_exec(tmp_path: pathlib.Path):
    mod = tmp_path / "safe_mod.py"
    mod.write_text(
        "RAISE = (_ for _ in ()).throw(RuntimeError('must not exec'))\ndef ok():\n    return 1\n",
        encoding="utf-8",
    )
    # Top-level throw would run on import/exec_module; AST check must still see `ok`.
    assert _exists_module_func(str(mod), "ok") is True
    assert _exists_module_func(str(mod), "missing") is False

    contracts = tmp_path / "c.yaml"
    contracts.write_text(
        f"module: {mod.as_posix()}\nfunctions:\n  ok:\n    pre: []\n    post: []\n    side_effects: []\n",
        encoding="utf-8",
    )
    ok, report = check_contracts(str(contracts))
    assert ok is True
    assert "[ok]" in report


def test_glossary_scaffold_label(tmp_path: pathlib.Path):
    (tmp_path / "api.proto").write_text('syntax = "proto3";\nmessage Order {}\n', encoding="utf-8")
    md = build_glossary(str(tmp_path))
    assert "scaffold" in md.lower()
    assert "TODO: define" not in md
    assert "Order" in md


def test_toy_scan_emits_side_effects_field():
    root = pathlib.Path("examples/python_toy")
    m = build_python_map(root)
    assert m["functions"]
    # Every function from the analyzer should carry the field (possibly empty).
    for meta in m["functions"].values():
        assert "side_effects" in meta
        assert isinstance(meta["side_effects"], list)
