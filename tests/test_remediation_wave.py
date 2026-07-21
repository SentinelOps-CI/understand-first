"""Focused regressions for Phase 0/1 remediation wave."""

from __future__ import annotations

import pathlib
import zipfile

from cli.ucli.analyzers.python_analyzer import _parse_file, build_python_map
from cli.ucli.config import filter_config_to_schema, validate_config_dict
from cli.ucli.contracts.contracts import lean_stubs


def test_lean_stubs_write_real_newlines(tmp_path: pathlib.Path):
    contracts = tmp_path / "c.yaml"
    contracts.write_text(
        "module: demo\nfunctions:\n  foo:\n    pre: []\n    post: []\n    side_effects: []\n",
        encoding="utf-8",
    )
    out_dir = tmp_path / "lean"
    count = lean_stubs(str(contracts), str(out_dir))
    assert count >= 1
    lean_files = list(out_dir.glob("*.lean"))
    assert lean_files
    text = lean_files[0].read_text(encoding="utf-8")
    assert "\\n" not in text
    assert "\n" in text
    assert "namespace Contracts" in text
    assert "Prop := True" in text


def test_verify_lean_is_presence_only(tmp_path: pathlib.Path):
    from cli.ucli.contracts.contracts import verify_lean

    contracts = tmp_path / "c.yaml"
    contracts.write_text(
        "module: demo\nfunctions:\n  foo:\n    pre: []\n    post: []\n    side_effects: []\n",
        encoding="utf-8",
    )
    lean_dir = tmp_path / "lean"
    lean_stubs(str(contracts), str(lean_dir))
    data = verify_lean(str(contracts), str(lean_dir))
    assert data["mode"] == "presence-only"
    assert data["missing_invariants"] == []
    assert data["functions_total"] >= 1


def test_async_function_def_parsed_like_sync(tmp_path: pathlib.Path):
    src = tmp_path / "async_mod.py"
    src.write_text(
        "async def fetch():\n    await helper()\n\nasync def helper():\n    return 1\n",
        encoding="utf-8",
    )
    parsed = _parse_file(src)
    assert "fetch" in parsed
    assert "helper" in parsed["fetch"]["calls"]

    repo = build_python_map(tmp_path)
    keys = "\n".join(repo.get("functions", {}))
    assert ":fetch" in keys
    assert ":helper" in keys


def test_config_schema_filter_drops_theater_keys():
    dirty = {
        "hops": 2,
        "seeds": ["main"],
        "metrics": {"enabled": True, "weekly_reports": True},
        "exclude_patterns": ["**/tmp/**"],
        "ci_integration": {"enabled": True},
    }
    clean = filter_config_to_schema(dirty)
    assert "exclude_patterns" not in clean
    assert "ci_integration" not in clean
    assert clean["metrics"] == {"enabled": True}
    assert validate_config_dict(clean) == []


def test_packaging_top_level_is_cli_only():
    """Wheel top-level must be cli (not tests/examples/maps/...)."""
    root = pathlib.Path(__file__).resolve().parents[1]
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert 'include = ["cli*"]' in pyproject

    # Prefer inspecting a freshly built wheel when present (CI/local verify).
    dist = root / "dist_verify"
    wheels = sorted(dist.glob("*.whl")) if dist.is_dir() else []
    if not wheels:
        return
    with zipfile.ZipFile(wheels[-1]) as zf:
        top = zf.read(next(n for n in zf.namelist() if n.endswith("top_level.txt"))).decode()
        assert top.strip().splitlines() == ["cli"]
        foreign = [
            n
            for n in zf.namelist()
            if not n.startswith("cli/") and not n.startswith("understand_first")
        ]
        assert foreign == []
