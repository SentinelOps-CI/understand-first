import re
from typing import List, Tuple


def strategy_for_java_type(t: str) -> str:
    t = t.strip()
    if t in {"int", "long", "short", "byte"}:
        return "st.integers()"
    if t in {"double", "float"}:
        return "st.floats(allow_nan=False, allow_infinity=False)"
    if t == "boolean":
        return "st.booleans()"
    if t == "String":
        return "st.text()"
    m = re.match(r"List<(.+)>", t)
    if m:
        inner = strategy_for_java_type(m.group(1))
        return f"st.lists({inner})"
    m = re.match(r"Map<(.+?),(.+?)>", t)
    if m:
        k = strategy_for_java_type(m.group(1))
        v = strategy_for_java_type(m.group(2))
        return f"st.dictionaries({k}, {v})"
    return "st.none()"


def infer_java_method_args(src: str) -> List[Tuple[str, str]]:
    # naive regex for: public static Return foo(Type a, Type2 b)
    m = re.search(r"\b(\w+)\s*\(([^)]*)\)", src)
    if not m:
        return []
    params = m.group(2).strip()
    if not params:
        return []
    out: List[Tuple[str, str]] = []
    for part in params.split(","):
        part = part.strip()
        pm = re.match(r"([\w<>?, ]+)\s+(\w+)$", part)
        if pm:
            t, name = pm.group(1).strip(), pm.group(2)
            out.append((name, t))
    return out


def strategy_for_csharp_type(t: str) -> str:
    t = t.strip()
    if t in {"int", "long", "short", "byte"}:
        return "st.integers()"
    if t in {"double", "float", "decimal"}:
        return "st.floats(allow_nan=False, allow_infinity=False)"
    if t.lower() == "bool":
        return "st.booleans()"
    if t in {"string", "String"}:
        return "st.text()"
    m = re.match(r"List<(.+)>", t)
    if m:
        inner = strategy_for_csharp_type(m.group(1))
        return f"st.lists({inner})"
    m = re.match(r"Dictionary<(.+?),(.+?)>", t)
    if m:
        k = strategy_for_csharp_type(m.group(1))
        v = strategy_for_csharp_type(m.group(2))
        return f"st.dictionaries({k}, {v})"
    return "st.none()"


def infer_csharp_method_args(src: str) -> List[Tuple[str, str]]:
    # naive: public static Return Foo(Type a, Type2 b)
    m = re.search(r"\b(\w+)\s*\(([^)]*)\)", src)
    if not m:
        return []
    params = m.group(2).strip()
    if not params:
        return []
    out: List[Tuple[str, str]] = []
    for part in params.split(","):
        part = part.strip()
        pm = re.match(r"([\w<>?, ]+)\s+(\w+)$", part)
        if pm:
            t, name = pm.group(1).strip(), pm.group(2)
            out.append((name, t))
    return out
