import json, os, tempfile, pathlib
from cli.ucli.config import validate_config_dict
from cli.ucli.contracts.contracts import from_openapi
from cli.ucli.lens.lens import explain_node


def test_config_validate_suggestions():
    bad = {"seed_for": ["x"], "hops": 2}
    errs = validate_config_dict(bad)
    assert any("did you mean 'seeds_for'" in e for e in errs)


def test_openapi_enriches_contracts():
    txt = from_openapi("examples/apis/petstore-mini.yaml")
    assert "request_meta" in txt or "response_meta" in txt


def test_lens_explain_basic():
    # tiny repo map and lens
    repo_map = {
        "functions": {
            "a:file": {"file": "a.py", "calls": ["b"]},
            "b:file": {"file": "b.py", "calls": []},
        }
    }
    lens = {"lens": {"seeds": ["a:file"]}, "functions": repo_map["functions"]}
    info = explain_node("a:file", lens, repo_map)
    assert "edges" in info and "callers" in info["edges"] and "callees" in info["edges"]
