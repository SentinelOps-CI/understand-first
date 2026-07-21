"""Java analyzer (Wave 20–21).

Preferred path (Wave 21): optional ``javalang`` AST → ``java-ast``,
``ast-cyclomatic``. Install via ``pip install 'understand-first[analyzers]'``
or ``pip install javalang``.

Fallback (Wave 20): conservative regex → ``java-best-effort``,
``keyword-heuristic``. Override with ``UF_JAVA_ANALYZER=regex|ast|auto``.

Call edges: same-file unique short names, plus high-confidence same-package
unique simple names. Never invents cross-package / import edges.
"""

from __future__ import annotations

import os
import pathlib
import re
from typing import Any

JAVA_EXTENSIONS = frozenset({".java"})

_ENV_MODE = "UF_JAVA_ANALYZER"

_SKIP_DIR_NAMES = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        "dist",
        "build",
        "target",
        "out",
        "coverage",
        ".tox",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
    }
)

_KEYWORD_CALLEES = frozenset(
    {
        "if",
        "for",
        "while",
        "switch",
        "case",
        "catch",
        "return",
        "new",
        "throw",
        "class",
        "interface",
        "enum",
        "extends",
        "implements",
        "package",
        "import",
        "public",
        "private",
        "protected",
        "static",
        "final",
        "void",
        "int",
        "long",
        "double",
        "float",
        "boolean",
        "char",
        "byte",
        "short",
        "true",
        "false",
        "null",
        "this",
        "super",
        "try",
        "finally",
        "else",
        "do",
        "break",
        "continue",
        "default",
        "instanceof",
        "synchronized",
        "volatile",
        "transient",
        "native",
        "abstract",
        "strictfp",
        "assert",
        "var",
        "record",
        "yield",
        "permits",
        "sealed",
        "non-sealed",
    }
)

_RE_PACKAGE = re.compile(r"(?m)^package\s+([\w.]+)\s*;")
_RE_CLASS = re.compile(
    r"(?m)^(?:public\s+|protected\s+|private\s+)?(?:abstract\s+|final\s+|sealed\s+)?"
    r"(?:class|interface|enum|record)\s+([A-Za-z_][\w]*)\b"
)
_TYPE_KEYWORDS = frozenset(
    {
        "return",
        "if",
        "for",
        "while",
        "switch",
        "case",
        "catch",
        "throw",
        "new",
        "else",
        "try",
        "finally",
        "do",
        "break",
        "continue",
        "default",
        "assert",
        "yield",
        "package",
        "import",
        "class",
        "interface",
        "enum",
        "record",
        "extends",
        "implements",
        "this",
        "super",
        "true",
        "false",
        "null",
    }
)

# Method: modifiers + optional generics + type + name(
_RE_METHOD = re.compile(
    r"(?m)^[ \t]*(?:(?:public|protected|private|static|final|abstract|synchronized|"
    r"native|default|strictfp)\s+)*"
    r"(?:<[^>]+>\s+)?"
    r"([\w.\[\]]+)\s+"
    r"([A-Za-z_][\w]*)\s*\("
)
# Constructors: ClassName(
_RE_CTOR = re.compile(r"(?m)^[ \t]*(?:(?:public|protected|private)\s+)*([A-Za-z_][\w]*)\s*\(")
_RE_CALL = re.compile(r"(?<![.\w])([A-Za-z_][\w]*)\s*\(")
_RE_COMPLEXITY = re.compile(r"\b(?:if|for|while|switch|case|catch)\b|\&\&|\|\||\?(?![?.])")


def _is_java_file(path: pathlib.Path) -> bool:
    if path.suffix.lower() not in JAVA_EXTENSIONS:
        return False
    return not any(part.startswith(".") for part in path.parts if part not in (".", ".."))


def _should_skip_dir(name: str) -> bool:
    return name in _SKIP_DIR_NAMES or name.startswith(".")


def _strip_comments_and_strings(src: str) -> str:
    out: list[str] = []
    i = 0
    n = len(src)
    while i < n:
        ch = src[i]
        if ch == "/" and i + 1 < n and src[i + 1] == "/":
            i += 2
            while i < n and src[i] not in "\n\r":
                out.append(" ")
                i += 1
            continue
        if ch == "/" and i + 1 < n and src[i + 1] == "*":
            out.append(" ")
            out.append(" ")
            i += 2
            while i + 1 < n and not (src[i] == "*" and src[i + 1] == "/"):
                out.append("\n" if src[i] in "\n\r" else " ")
                i += 1
            if i + 1 < n:
                out.append(" ")
                out.append(" ")
                i += 2
            continue
        if ch in {'"', "'"}:
            quote = ch
            out.append(" ")
            i += 1
            while i < n:
                c = src[i]
                if c == "\\" and i + 1 < n:
                    out.append(" ")
                    out.append(" ")
                    i += 2
                    continue
                if c == quote:
                    out.append(" ")
                    i += 1
                    break
                out.append("\n" if c in "\n\r" else " ")
                i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _line_of(src: str, idx: int) -> int:
    return src.count("\n", 0, max(0, idx)) + 1


def _brace_block_end(src: str, open_idx: int) -> int:
    if open_idx >= len(src) or src[open_idx] != "{":
        return len(src)
    depth = 0
    i = open_idx
    n = len(src)
    while i < n:
        c = src[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return n


def _complexity_heuristic(body: str) -> int:
    return 1 + len(_RE_COMPLEXITY.findall(body))


def _calls_in_body(body: str) -> list[str]:
    calls: list[str] = []
    for m in _RE_CALL.finditer(body):
        name = m.group(1)
        if name in _KEYWORD_CALLEES:
            continue
        calls.append(name)
    return list(dict.fromkeys(calls))


def _parse_java_source(src: str, file_path: pathlib.Path) -> tuple[dict[str, Any], str]:
    pkg_m = _RE_PACKAGE.search(src)
    package = pkg_m.group(1) if pkg_m else ""
    cleaned = _strip_comments_and_strings(src)
    out: dict[str, Any] = {}

    # Collect class/interface/enum/record names for ctor detection & qnames.
    classes: list[tuple[str, int, int]] = []  # name, start, end of body
    for m in _RE_CLASS.finditer(cleaned):
        name = m.group(1)
        open_brace = cleaned.find("{", m.end() - 1)
        if open_brace < 0:
            continue
        end = _brace_block_end(cleaned, open_brace)
        classes.append((name, open_brace, end))

    def add(local: str, simple: str, body: str, line: int, enclosing: str) -> None:
        out[local] = {
            "simple_name": simple,
            "file": file_path.as_posix(),
            "calls": _calls_in_body(body),
            "callers": [],
            "complexity": _complexity_heuristic(body),
            "line": line,
            "language": "java",
            "package": package,
            "enclosing": enclosing,
            "analyzer": "java-best-effort",
            "complexity_kind": "keyword-heuristic",
        }

    # Methods / ctors inside each type body
    for class_name, body_start, body_end in classes:
        body = cleaned[body_start:body_end]
        # Relative offsets → absolute
        for m in _RE_METHOD.finditer(body):
            type_tok, name = m.group(1), m.group(2)
            if name in _KEYWORD_CALLEES or type_tok in _TYPE_KEYWORDS:
                continue
            # Skip constructors here (handled by _RE_CTOR).
            if name == class_name and type_tok in {class_name, "void"}:
                continue
            abs_start = body_start + m.start()
            open_brace = body.find("{", m.end() - 1)
            # Abstract / interface method without body
            if open_brace < 0 or open_brace > (m.end() - body_start + 200):
                # Look for ; abstract
                semi = body.find(";", m.end() - 1)
                if semi >= 0 and (open_brace < 0 or semi < open_brace):
                    local = f"{class_name}.{name}"
                    add(local, name, "", _line_of(src, abs_start), class_name)
                    continue
            if open_brace < 0:
                continue
            # Ensure brace is within this class body
            abs_brace = body_start + open_brace
            if abs_brace >= body_end:
                continue
            # Reject if another '{' or method-ish noise before this brace on same span
            between = body[m.end() - 1 : open_brace]
            if ";" in between:
                continue
            meth_end = _brace_block_end(cleaned, abs_brace)
            if meth_end > body_end:
                meth_end = body_end
            meth_body = cleaned[abs_brace:meth_end]
            local = f"{class_name}.{name}"
            add(local, name, meth_body, _line_of(src, abs_start), class_name)

        # Constructors: ClassName( ... ) {
        for m in _RE_CTOR.finditer(body):
            name = m.group(1)
            if name != class_name:
                continue
            abs_start = body_start + m.start()
            open_brace = body.find("{", m.end() - 1)
            if open_brace < 0:
                continue
            abs_brace = body_start + open_brace
            if abs_brace >= body_end:
                continue
            meth_end = _brace_block_end(cleaned, abs_brace)
            meth_body = cleaned[abs_brace:meth_end]
            local = f"{class_name}.<init>"
            # Avoid double-add if method regex already caught ClassName as return type miss
            if local not in out:
                add(local, "<init>", meth_body, _line_of(src, abs_start), class_name)

    return out, package


def _parse_file(file_path: pathlib.Path) -> tuple[dict[str, Any], str]:
    try:
        src = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return {}, ""
    try:
        return _parse_java_source(src, file_path)
    except Exception:
        return {}, ""


def _build_file_indexes(
    functions: dict[str, Any],
) -> dict[str, dict[str, list[str]]]:
    by_file_short: dict[str, dict[str, list[str]]] = {}
    for qn, meta in functions.items():
        file = meta.get("file", "")
        short = qn.rsplit(":", 1)[-1]
        simple = meta.get("simple_name") or short.rsplit(".", 1)[-1]
        bucket = by_file_short.setdefault(file, {})
        bucket.setdefault(short, []).append(qn)
        if simple != short and simple != "<init>":
            bucket.setdefault(simple, []).append(qn)
    return by_file_short


def _attach_and_qualify_same_file(functions: dict[str, Any]) -> None:
    by_file_short = _build_file_indexes(functions)
    for caller_qn, meta in functions.items():
        caller_file = meta.get("file", "")
        local_map = by_file_short.get(caller_file, {})
        qualified: list[str] = []
        for token in meta.get("calls") or []:
            if "." in token and ":" not in token:
                qualified.append(token)
                continue
            candidates = list(dict.fromkeys(local_map.get(token, [])))
            exact = [c for c in candidates if c.rsplit(":", 1)[-1] == token]
            pick = exact if len(exact) == 1 else (candidates if len(candidates) == 1 else [])
            if len(pick) == 1 and pick[0] != caller_qn:
                callee = pick[0]
                qualified.append(callee)
                functions[callee].setdefault("callers", []).append(caller_qn)
            else:
                qualified.append(token)
        meta["calls"] = list(dict.fromkeys(qualified))
    for meta in functions.values():
        meta["callers"] = sorted(set(meta.get("callers") or []))


def _attach_same_package_edges(
    functions: dict[str, Any],
    file_packages: dict[str, str],
) -> None:
    """Qualify bare calls to unique same-package simple names (fail closed)."""
    by_pkg_short: dict[str, dict[str, list[str]]] = {}
    qn_pkg: dict[str, str] = {}
    for qn, meta in functions.items():
        file = meta.get("file", "")
        pkg = meta.get("package") or file_packages.get(file) or ""
        if not pkg:
            continue
        qn_pkg[qn] = pkg
        short = qn.rsplit(":", 1)[-1]
        simple = meta.get("simple_name") or short.rsplit(".", 1)[-1]
        if simple == "<init>":
            continue
        bucket = by_pkg_short.setdefault(pkg, {})
        bucket.setdefault(short, []).append(qn)
        if simple != short:
            bucket.setdefault(simple, []).append(qn)

    for caller_qn, meta in functions.items():
        pkg = qn_pkg.get(caller_qn) or meta.get("package") or ""
        if not pkg:
            continue
        pkg_map = by_pkg_short.get(pkg, {})
        new_calls: list[str] = []
        for token in meta.get("calls") or []:
            if ":" in token or "." in token:
                new_calls.append(token)
                continue
            candidates = list(dict.fromkeys(pkg_map.get(token, [])))
            exact = [c for c in candidates if c.rsplit(":", 1)[-1] == token]
            pick = exact if len(exact) == 1 else (candidates if len(candidates) == 1 else [])
            if len(pick) == 1 and pick[0] != caller_qn:
                callee = pick[0]
                new_calls.append(callee)
                functions[callee].setdefault("callers", []).append(caller_qn)
            else:
                new_calls.append(token)
        meta["calls"] = list(dict.fromkeys(new_calls))
    for meta in functions.values():
        meta["callers"] = sorted(set(meta.get("callers") or []))


def _collect_java_files(root: pathlib.Path) -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    if root.is_file():
        return [root] if _is_java_file(root) else []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not _should_skip_dir(d)]
        for name in filenames:
            path = pathlib.Path(dirpath) / name
            if _is_java_file(path):
                files.append(path)
    return files


def java_analyzer_mode() -> str:
    raw = (os.environ.get(_ENV_MODE) or "auto").strip().lower()
    if raw in {"auto", "ast", "regex", "best-effort"}:
        return "regex" if raw == "best-effort" else raw
    return "auto"


def javalang_available() -> bool:
    try:
        import javalang  # noqa: F401
    except ImportError:
        return False
    return True


def _javalang_decision_complexity(method_node: Any) -> int:
    """Structural decision-point count (not Python McCabe visitor parity)."""
    if method_node is None:
        return 1
    import javalang.tree as jtree

    score = 1
    for _path, _node in method_node.filter(jtree.IfStatement):
        score += 1
    for _path, _node in method_node.filter(jtree.ForStatement):
        score += 1
    for _path, _node in method_node.filter(jtree.WhileStatement):
        score += 1
    for _path, _node in method_node.filter(jtree.DoStatement):
        score += 1
    for _path, _node in method_node.filter(jtree.SwitchStatementCase):
        score += 1
    for _path, _node in method_node.filter(jtree.CatchClause):
        score += 1
    for _path, _node in method_node.filter(jtree.TernaryExpression):
        score += 1
    for _path, node in method_node.filter(jtree.BinaryOperation):
        if getattr(node, "operator", None) in {"&&", "||"}:
            score += 1
    return score


def _javalang_calls(method_node: Any) -> list[str]:
    if method_node is None:
        return []
    import javalang.tree as jtree

    calls: list[str] = []
    seen: set[str] = set()
    for _, node in method_node.filter(jtree.MethodInvocation):
        name = getattr(node, "member", None)
        if not name or name in _KEYWORD_CALLEES or name in seen:
            continue
        seen.add(name)
        calls.append(name)
    return calls


def _parse_java_javalang(src: str, file_path: pathlib.Path) -> tuple[dict[str, Any], str] | None:
    """Return (functions, package) or None if parse fails / javalang missing."""
    try:
        import javalang
        import javalang.tree as jtree
    except ImportError:
        return None
    try:
        tree = javalang.parse.parse(src)
    except (javalang.parser.JavaSyntaxError, javalang.tokenizer.LexerError, RecursionError):
        return None
    except Exception:
        return None

    package = ""
    pkg = getattr(tree, "package", None)
    if pkg is not None and getattr(pkg, "name", None):
        package = str(pkg.name)

    out: dict[str, Any] = {}

    def add(local: str, simple: str, method_node: Any, line: int, enclosing: str) -> None:
        out[local] = {
            "simple_name": simple,
            "file": file_path.as_posix(),
            "calls": _javalang_calls(method_node),
            "callers": [],
            "complexity": _javalang_decision_complexity(method_node),
            "line": line or 1,
            "language": "java",
            "package": package,
            "enclosing": enclosing,
            "analyzer": "java-ast",
            "complexity_kind": "ast-cyclomatic",
        }

    for type_decl in getattr(tree, "types", None) or []:
        if not isinstance(
            type_decl,
            (jtree.ClassDeclaration, jtree.InterfaceDeclaration, jtree.EnumDeclaration),
        ):
            continue
        class_name = str(getattr(type_decl, "name", "") or "")
        if not class_name:
            continue
        for method in getattr(type_decl, "methods", None) or []:
            if not isinstance(method, jtree.MethodDeclaration):
                continue
            pos = getattr(method, "position", None)
            line = int(getattr(pos, "line", 1) or 1)
            method_name = str(getattr(method, "name", "") or "")
            if not method_name:
                continue
            local = f"{class_name}.{method_name}"
            add(local, method_name, method, line, class_name)
        for ctor in getattr(type_decl, "constructors", None) or []:
            if not isinstance(ctor, jtree.ConstructorDeclaration):
                continue
            pos = getattr(ctor, "position", None)
            line = int(getattr(pos, "line", 1) or 1)
            local = f"{class_name}.<init>"
            add(local, "<init>", ctor, line, class_name)

    return out, package


def _build_regex_map(files: list[pathlib.Path]) -> dict[str, Any]:
    functions: dict[str, Any] = {}
    file_packages: dict[str, str] = {}

    for file_path in files:
        parsed, package = _parse_file(file_path)
        file_packages[file_path.as_posix()] = package
        for func, meta in parsed.items():
            key = f"{file_path.with_suffix('').as_posix()}:{func}"
            m = dict(meta)
            m["analyzer"] = "java-best-effort"
            m["complexity_kind"] = "keyword-heuristic"
            functions[key] = m

    _attach_and_qualify_same_file(functions)
    _attach_same_package_edges(functions, file_packages)

    return {
        "language": "java",
        "functions": functions,
        "analyzer": "java-best-effort",
        "analyzer_fidelity": "best-effort",
        "complexity_kind": "keyword-heuristic",
        "analyzer_note": (
            "Java map via regex heuristics — not JavaParser/javac AST; "
            "complexity is keyword-based; call edges are same-file unique names, "
            "plus high-confidence same-package unique simple names across scanned "
            "files. No cross-package invent; not Python/Go-AST parity. "
            "Install javalang (pip install javalang) for java-ast."
        ),
    }


def _build_javalang_map(files: list[pathlib.Path]) -> dict[str, Any] | None:
    functions: dict[str, Any] = {}
    file_packages: dict[str, str] = {}
    any_ok = False

    for file_path in files:
        try:
            src = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        parsed = _parse_java_javalang(src, file_path)
        if parsed is None:
            continue
        funcs, package = parsed
        any_ok = True
        file_packages[file_path.as_posix()] = package
        for func, meta in funcs.items():
            key = f"{file_path.with_suffix('').as_posix()}:{func}"
            functions[key] = meta

    if not any_ok and files:
        return None

    _attach_and_qualify_same_file(functions)
    _attach_same_package_edges(functions, file_packages)

    return {
        "language": "java",
        "functions": functions,
        "analyzer": "java-ast",
        "analyzer_fidelity": "ast",
        "complexity_kind": "ast-cyclomatic",
        "analyzer_note": (
            "Java map via javalang (parse only, not typechecked). "
            "Complexity is ast-cyclomatic: 1 + If/For/While/Do/Switch/SwitchCase/"
            "Catch/Ternary/&&/||. Call edges: same-file unique names plus "
            "same-package unique simple names. No cross-package invent; "
            "not Python-parity. Falls back to java-best-effort without javalang."
        ),
    }


def build_java_map(root: pathlib.Path) -> dict[str, Any]:
    """Build a Java map for ``root`` (javalang AST preferred, regex fallback)."""
    root = pathlib.Path(root)
    mode = java_analyzer_mode()
    files = _collect_java_files(root)

    if mode != "regex":
        if javalang_available():
            ast_map = _build_javalang_map(files)
            if ast_map is not None:
                return ast_map
            if mode == "ast":
                raise RuntimeError("UF_JAVA_ANALYZER=ast but javalang parse produced no map")
        elif mode == "ast":
            raise RuntimeError(
                "UF_JAVA_ANALYZER=ast requires javalang; "
                "pip install javalang or understand-first[analyzers]"
            )

    return _build_regex_map(files)


class JavaAdapter:
    """Registry-facing adapter for Java (javalang AST preferred, regex fallback)."""

    language = "java"
    extensions = JAVA_EXTENSIONS
    fidelity = "ast"
    note = (
        "Prefers javalang AST (java-ast, ast-cyclomatic) when installed; "
        "degrades to regex (java-best-effort, keyword-heuristic). "
        "Same-file + same-package unique call edges. Not typechecked / not Python-parity."
    )

    def build_map(self, root: pathlib.Path) -> dict[str, Any]:
        return build_java_map(root)


def java_ast_status() -> dict[str, Any]:
    return {
        "mode": java_analyzer_mode(),
        "javalang_available": javalang_available(),
    }
