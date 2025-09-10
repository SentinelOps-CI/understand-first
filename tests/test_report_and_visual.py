from cli.ucli.report.report import make_report_md
from cli.ucli.visual.delta import lens_delta_svg
from cli.ucli.analyzers.python_analyzer import build_python_map
import json, tempfile, os, pathlib


def test_make_report_md_lists_hotspots():
    m = build_python_map(pathlib.Path("examples/python_toy"))
    md = make_report_md(m)
    assert "# Understanding Report" in md
    assert "Hotspots" in md


def test_lens_delta_svg_outputs_svg():
    a = {"functions": {"A:file": {"file": "x", "calls": []}}}
    b = {"functions": {"A:file": {"file": "x", "calls": []}, "B:file": {"file": "y", "calls": []}}}
    with tempfile.TemporaryDirectory() as tmp:
        p1 = os.path.join(tmp, "a.json")
        p2 = os.path.join(tmp, "b.json")
        json.dump(a, open(p1, "w"))
        json.dump(b, open(p2, "w"))
        svg = lens_delta_svg(p1, p2)
        assert svg.startswith("<svg") and "Lens delta" in svg
