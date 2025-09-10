import sys, time, importlib.util
from typing import Any, Dict, List
import ast


def run_callable_with_trace(pyfile: str, func_name: str, a=None, b=None) -> Dict[str, Any]:
    spec = importlib.util.spec_from_file_location("_mod", pyfile)
    mod = importlib.util.module_from_spec(spec)  # type: ignore
    assert spec.loader is not None
    spec.loader.exec_module(mod)  # type: ignore

    target = getattr(mod, func_name)
    events: List[Dict[str, Any]] = []
    start = time.time()

    def tracer(frame, event, arg):
        if event == "call":
            code = frame.f_code
            fn = code.co_name
            file = code.co_filename
            events.append({"type": "call", "func": fn, "file": file})
        return tracer

    sys.setprofile(tracer)
    try:
        if a is None and b is None:
            target()
        elif b is None:
            target(_coerce(a))
        else:
            target(_coerce(a), _coerce(b))
    finally:
        sys.setprofile(None)
    end = time.time()
    return {"events": events, "duration_sec": end - start}


def analyze_errors_static(pyfile: str) -> Dict[str, Any]:
    src = open(pyfile, "r", encoding="utf-8", errors="ignore").read()
    tree = ast.parse(src)
    raises: List[Dict[str, Any]] = []
    try_catches: List[Dict[str, Any]] = []

    class V(ast.NodeVisitor):
        def visit_Raise(self, node: ast.Raise):
            name = (
                getattr(getattr(node.exc, "func", None), "id", None)
                or getattr(getattr(node.exc, "func", None), "attr", None)
                or getattr(getattr(node.exc, "id", None), "id", None)
            )
            raises.append({"line": getattr(node, "lineno", 0), "exc": name or "Exception"})
            self.generic_visit(node)

        def visit_Try(self, node: ast.Try):
            for h in node.handlers:
                et = getattr(h.type, "id", None) if h.type is not None else "Exception"
                try_catches.append({"line": getattr(h, "lineno", 0), "catch": et or "Exception"})
            self.generic_visit(node)

    V().visit(tree)
    return {"raises": raises, "catches": try_catches}


def _coerce(x):
    try:
        return int(x)
    except Exception:
        return x
