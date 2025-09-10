from cli.ucli.trace.pytrace import analyze_errors_static
import tempfile, os


def test_analyze_errors_static_finds_raises_and_catches():
    src = """
def f(x):
    try:
        if x < 0:
            raise ValueError('bad')
    except ValueError:
        return 0
    return 1
"""
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "m.py")
        open(p, "w", encoding="utf-8").write(src)
        data = analyze_errors_static(p)
        assert any(r.get("exc") in ("ValueError", "Exception") for r in data.get("raises", []))
        assert any(c.get("catch") in ("ValueError", "Exception") for c in data.get("catches", []))
