"""C# analyzer (Wave 24).

Preferred path: ``dotnet run`` + Roslyn worker → ``csharp-ast``,
``ast-cyclomatic``. Requires a .NET SDK on PATH.

Fallback: conservative regex → ``csharp-best-effort``,
``keyword-heuristic``. Override with ``UF_CSHARP_ANALYZER=regex|ast|auto``.

Call edges: same-file unique short names, plus high-confidence same-namespace
unique simple names. Never invents cross-namespace / using edges.
"""

from __future__ import annotations

import os
import pathlib
import re
from typing import Any

from ucli.analyzers.csharp_ast_bridge import (
    ast_backend_available,
    csharp_analyzer_mode,
    run_csharp_ast_worker,
)

CSHARP_EXTENSIONS = frozenset({".cs"})

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
        "bin",
        "obj",
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
        "foreach",
        "while",
        "switch",
        "case",
        "catch",
        "return",
        "new",
        "throw",
        "class",
        "struct",
        "interface",
        "enum",
        "record",
        "namespace",
        "using",
        "public",
        "private",
        "protected",
        "internal",
        "static",
        "readonly",
        "const",
        "volatile",
        "sealed",
        "abstract",
        "virtual",
        "override",
        "async",
        "await",
        "void",
        "int",
        "long",
        "short",
        "byte",
        "sbyte",
        "uint",
        "ulong",
        "ushort",
        "float",
        "double",
        "decimal",
        "bool",
        "char",
        "string",
        "object",
        "var",
        "dynamic",
        "true",
        "false",
        "null",
        "this",
        "base",
        "typeof",
        "nameof",
        "sizeof",
        "default",
        "checked",
        "unchecked",
        "lock",
        "fixed",
        "unsafe",
        "stackalloc",
        "try",
        "finally",
        "else",
        "do",
        "break",
        "continue",
        "goto",
        "yield",
        "when",
        "where",
        "in",
        "out",
        "ref",
        "params",
        "is",
        "as",
        "get",
        "set",
        "init",
        "add",
        "remove",
        "partial",
        "required",
        "file",
        "nint",
        "nuint",
        "global",
        "alias",
        "notnull",
        "unmanaged",
        "and",
        "or",
        "not",
        "with",
        "select",
        "from",
        "group",
        "into",
        "orderby",
        "join",
        "let",
        "ascending",
        "descending",
        "on",
        "equals",
        "by",
    }
)

_TYPE_KEYWORDS = frozenset(
    {
        "return",
        "if",
        "for",
        "foreach",
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
        "yield",
        "namespace",
        "using",
        "class",
        "struct",
        "interface",
        "enum",
        "record",
        "this",
        "base",
        "true",
        "false",
        "null",
        "typeof",
        "nameof",
        "sizeof",
        "checked",
        "unchecked",
        "lock",
        "await",
        "get",
        "set",
        "init",
    }
)

_RE_NAMESPACE = re.compile(r"(?m)^(?:file\s+)?namespace\s+([\w.]+)\s*[;{]")
_RE_CLASS = re.compile(
    r"(?m)^[ \t]*(?:(?:public|protected|private|internal|static|abstract|sealed|"
    r"partial|readonly|file)\s+)*"
    r"(?:class|struct|interface|enum|record(?:\s+class|\s+struct)?)\s+"
    r"([A-Za-z_][\w]*)\b"
)
# Method: modifiers + optional generics + return type + name(
_RE_METHOD = re.compile(
    r"(?m)^[ \t]*(?:(?:public|protected|private|internal|static|virtual|override|"
    r"abstract|sealed|async|partial|extern|new|unsafe|required)\s+)*"
    r"(?:<[^>]+>\s+)?"
    r"([\w.\[\]?<>,\s]+?)\s+"
    r"([A-Za-z_][\w]*)\s*(?:<[^>]+>)?\s*\("
)
# Constructors: TypeName(
_RE_CTOR = re.compile(
    r"(?m)^[ \t]*(?:(?:public|protected|private|internal|static)\s+)*"
    r"([A-Za-z_][\w]*)\s*\("
)
_RE_CALL = re.compile(r"(?<![.\w])([A-Za-z_][\w]*)\s*\(")
_RE_COMPLEXITY = re.compile(
    r"\b(?:if|for|foreach|while|switch|case|catch)\b|\&\&|\|\||\?(?![?.])"
)


def _is_csharp_file(path: pathlib.Path) -> bool:
    if path.suffix.lower() not in CSHARP_EXTENSIONS:
        return False
    return not any(part.startswith(".") for part in path.parts if part not in (".", ".."))


def _should_skip_dir(name: str) -> bool:
    return name in _SKIP_DIR_NAMES or name.startswith(".")


def _strip_comments_and_strings(src: str) -> str:
    """Strip //, /* */, \"...\", and @"..." / \"\"\"...\"\"\" raw strings (best-effort)."""
    out: list[str] = []
    i = 0
    n = len(src)
    while i < n:
        ch = src[i]
        # Verbatim string @"..."
        if ch == "@" and i + 1 < n and src[i + 1] == '"':
            out.append(" ")
            out.append(" ")
            i += 2
            while i < n:
                if src[i] == '"' and i + 1 < n and src[i + 1] == '"':
                    out.append(" ")
                    out.append(" ")
                    i += 2
                    continue
                if src[i] == '"':
                    out.append(" ")
                    i += 1
                    break
                out.append("\n" if src[i] in "\n\r" else " ")
                i += 1
            continue
        # Raw string literal """..."""
        if ch == '"' and i + 2 < n and src[i : i + 3] == '"""':
            quote_len = 0
            while i + quote_len < n and src[i + quote_len] == '"':
                quote_len += 1
            for _ in range(quote_len):
                out.append(" ")
            i += quote_len
            while i + quote_len <= n:
                if src[i : i + quote_len] == '"' * quote_len:
                    for _ in range(quote_len):
                        out.append(" ")
                    i += quote_len
                    break
                out.append("\n" if src[i] in "\n\r" else " ")
                i += 1
            continue
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
        if ch == "'":
            out.append(" ")
            i += 1
            while i < n:
                c = src[i]
                if c == "\\" and i + 1 < n:
                    out.append(" ")
                    out.append(" ")
                    i += 2
                    continue
                if c == "'":
                    out.append(" ")
                    i += 1
                    break
                out.append("\n" if c in "\n\r" else " ")
                i += 1
            continue
        if ch == '"':
            out.append(" ")
            i += 1
            while i < n:
                c = src[i]
                if c == "\\" and i + 1 < n:
                    out.append(" ")
                    out.append(" ")
                    i += 2
                    continue
                if c == '"':
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


def _normalize_type_token(tok: str) -> str:
    return re.sub(r"\s+", " ", tok.strip())


def _parse_csharp_source(src: str, file_path: pathlib.Path) -> tuple[dict[str, Any], str]:
    ns_m = _RE_NAMESPACE.search(src)
    namespace = ns_m.group(1) if ns_m else ""
    cleaned = _strip_comments_and_strings(src)
    out: dict[str, Any] = {}

    classes: list[tuple[str, int, int]] = []
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
            "language": "csharp",
            "namespace": namespace,
            "enclosing": enclosing,
            "analyzer": "csharp-best-effort",
            "complexity_kind": "keyword-heuristic",
        }

    for class_name, body_start, body_end in classes:
        body = cleaned[body_start:body_end]
        for m in _RE_METHOD.finditer(body):
            type_tok, name = _normalize_type_token(m.group(1)), m.group(2)
            if name in _KEYWORD_CALLEES or type_tok in _TYPE_KEYWORDS:
                continue
            # Properties / indexers / operators — skip when return type looks like get/set
            if name in {"get", "set", "init", "add", "remove"}:
                continue
            if name == class_name:
                continue
            # Skip operator / implicit / explicit
            if "operator" in type_tok.lower() or name in {"operator", "implicit", "explicit"}:
                continue
            abs_start = body_start + m.start()
            # Expression-bodied: ) => expr;
            after = body[m.end() - 1 : m.end() - 1 + 400]
            arrow = after.find("=>")
            open_brace = body.find("{", m.end() - 1)
            semi = body.find(";", m.end() - 1)

            if arrow >= 0 and (open_brace < 0 or arrow < open_brace - (m.end() - 1)):
                # Expression body until semicolon
                abs_arrow = body_start + (m.end() - 1) + arrow
                end_semi = cleaned.find(";", abs_arrow)
                if end_semi < 0 or end_semi > body_end:
                    end_semi = body_end
                meth_body = cleaned[abs_arrow:end_semi]
                local = f"{class_name}.{name}"
                add(local, name, meth_body, _line_of(src, abs_start), class_name)
                continue

            if open_brace < 0 or open_brace > (m.end() - body_start + 250):
                if semi >= 0 and (open_brace < 0 or semi < open_brace):
                    # Abstract / interface method without body
                    local = f"{class_name}.{name}"
                    add(local, name, "", _line_of(src, abs_start), class_name)
                    continue
            if open_brace < 0:
                continue
            abs_brace = body_start + open_brace
            if abs_brace >= body_end:
                continue
            between = body[m.end() - 1 : open_brace]
            if ";" in between and "=>" not in between:
                continue
            meth_end = _brace_block_end(cleaned, abs_brace)
            if meth_end > body_end:
                meth_end = body_end
            meth_body = cleaned[abs_brace:meth_end]
            local = f"{class_name}.{name}"
            add(local, name, meth_body, _line_of(src, abs_start), class_name)

        for m in _RE_CTOR.finditer(body):
            name = m.group(1)
            if name != class_name:
                continue
            abs_start = body_start + m.start()
            open_brace = body.find("{", m.end() - 1)
            if open_brace < 0:
                # Expression-bodied ctor
                after = body[m.end() - 1 : m.end() - 1 + 200]
                arrow = after.find("=>")
                if arrow >= 0:
                    abs_arrow = body_start + (m.end() - 1) + arrow
                    end_semi = cleaned.find(";", abs_arrow)
                    if end_semi < 0 or end_semi > body_end:
                        end_semi = body_end
                    local = f"{class_name}.<init>"
                    if local not in out:
                        add(
                            local,
                            "<init>",
                            cleaned[abs_arrow:end_semi],
                            _line_of(src, abs_start),
                            class_name,
                        )
                continue
            abs_brace = body_start + open_brace
            if abs_brace >= body_end:
                continue
            meth_end = _brace_block_end(cleaned, abs_brace)
            meth_body = cleaned[abs_brace:meth_end]
            local = f"{class_name}.<init>"
            if local not in out:
                add(local, "<init>", meth_body, _line_of(src, abs_start), class_name)

    return out, namespace


def _parse_file(file_path: pathlib.Path) -> tuple[dict[str, Any], str]:
    try:
        src = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return {}, ""
    try:
        return _parse_csharp_source(src, file_path)
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


def _attach_same_namespace_edges(
    functions: dict[str, Any],
    file_namespaces: dict[str, str],
) -> None:
    """Qualify bare calls to unique same-namespace simple names (fail closed)."""
    by_ns_short: dict[str, dict[str, list[str]]] = {}
    qn_ns: dict[str, str] = {}
    for qn, meta in functions.items():
        file = meta.get("file", "")
        ns = meta.get("namespace") or file_namespaces.get(file) or ""
        if not ns:
            continue
        qn_ns[qn] = ns
        short = qn.rsplit(":", 1)[-1]
        simple = meta.get("simple_name") or short.rsplit(".", 1)[-1]
        if simple == "<init>":
            continue
        bucket = by_ns_short.setdefault(ns, {})
        bucket.setdefault(short, []).append(qn)
        if simple != short:
            bucket.setdefault(simple, []).append(qn)

    for caller_qn, meta in functions.items():
        ns = qn_ns.get(caller_qn) or meta.get("namespace") or ""
        if not ns:
            continue
        ns_map = by_ns_short.get(ns, {})
        new_calls: list[str] = []
        for token in meta.get("calls") or []:
            if ":" in token or "." in token:
                new_calls.append(token)
                continue
            candidates = list(dict.fromkeys(ns_map.get(token, [])))
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


def _collect_csharp_files(root: pathlib.Path) -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    if root.is_file():
        return [root] if _is_csharp_file(root) else []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not _should_skip_dir(d)]
        for name in filenames:
            path = pathlib.Path(dirpath) / name
            if _is_csharp_file(path):
                files.append(path)
    return files


def _build_regex_map(files: list[pathlib.Path]) -> dict[str, Any]:
    functions: dict[str, Any] = {}
    file_namespaces: dict[str, str] = {}

    for file_path in files:
        parsed, namespace = _parse_file(file_path)
        file_namespaces[file_path.as_posix()] = namespace
        for func, meta in parsed.items():
            key = f"{file_path.with_suffix('').as_posix()}:{func}"
            m = dict(meta)
            m["analyzer"] = "csharp-best-effort"
            m["complexity_kind"] = "keyword-heuristic"
            functions[key] = m

    _attach_and_qualify_same_file(functions)
    _attach_same_namespace_edges(functions, file_namespaces)

    return {
        "language": "csharp",
        "functions": functions,
        "analyzer": "csharp-best-effort",
        "analyzer_fidelity": "best-effort",
        "complexity_kind": "keyword-heuristic",
        "analyzer_note": (
            "C# map via regex heuristics — not Roslyn/dotnet AST; complexity is "
            "keyword-based; call edges are same-file unique names, plus "
            "high-confidence same-namespace unique simple names across scanned "
            "files. No cross-namespace / using invent; not Python-parity. "
            "Set UF_CSHARP_ANALYZER=auto with a .NET SDK on PATH for csharp-ast."
        ),
    }


def _build_ast_map(
    root: pathlib.Path,
    files: list[pathlib.Path],
    worker_payload: dict[str, Any],
) -> dict[str, Any]:
    functions: dict[str, Any] = {}
    file_namespaces: dict[str, str] = {}
    root_posix = root.as_posix().rstrip("/")

    for entry in worker_payload.get("files") or []:
        if not isinstance(entry, dict):
            continue
        rel_file = str(entry.get("file") or "")
        walk_match = next(
            (
                p
                for p in files
                if p.as_posix() == rel_file
                or p.as_posix().endswith("/" + rel_file)
                or (
                    p.name == pathlib.Path(rel_file).name
                    and p.as_posix().endswith(rel_file.replace("\\", "/"))
                )
            ),
            None,
        )
        if walk_match is not None:
            display_file = walk_match.as_posix()
            stem = walk_match.with_suffix("").as_posix()
        else:
            display_file = (
                f"{root_posix}/{rel_file}"
                if root_posix and not rel_file.startswith(root_posix)
                else rel_file
            )
            stem = str(pathlib.PurePosixPath(display_file).with_suffix(""))

        ns = str(entry.get("namespace") or "")
        file_namespaces[display_file] = ns
        locals_map = entry.get("functions") or {}
        for local, meta in locals_map.items():
            if not isinstance(meta, dict):
                continue
            qn = f"{stem}:{local}"
            m = dict(meta)
            m["file"] = display_file
            m["analyzer"] = "csharp-ast"
            m["complexity_kind"] = "ast-cyclomatic"
            m["language"] = "csharp"
            m["namespace"] = ns or m.get("namespace") or ""
            if m.get("calls") is None:
                m["calls"] = []
            m.setdefault("callers", [])
            m.setdefault("simple_name", local.rsplit(".", 1)[-1])
            functions[qn] = m

    _attach_and_qualify_same_file(functions)
    _attach_same_namespace_edges(functions, file_namespaces)
    formula = worker_payload.get("complexity_formula") or (
        "1 + If/For/ForEach/While/Do/Case/Catch/Conditional/&&/||; nested local funcs excluded"
    )
    return {
        "language": "csharp",
        "functions": functions,
        "analyzer": "csharp-ast",
        "analyzer_fidelity": "ast",
        "complexity_kind": "ast-cyclomatic",
        "analyzer_note": (
            "C# map via Roslyn (parse only, not typechecked / not MSBuild). "
            f"Complexity is ast-cyclomatic: {formula}. "
            "Call edges: same-file unique names plus same-namespace unique simple "
            "names. No cross-namespace / using invent; not Python-parity. "
            "Falls back to csharp-best-effort when the .NET SDK is unavailable."
        ),
    }


def build_csharp_map(root: pathlib.Path) -> dict[str, Any]:
    """Build a C# map for ``root`` (Roslyn AST preferred, regex fallback)."""
    root = pathlib.Path(root)
    mode = csharp_analyzer_mode()
    files = _collect_csharp_files(root)
    scan_root = root if root.is_dir() else root.parent

    if mode != "regex":
        payload = run_csharp_ast_worker(scan_root, files)
        if payload is not None:
            worker_files = payload.get("files") or []
            if worker_files or not files:
                return _build_ast_map(root, files, payload)
            if mode == "ast":
                raise RuntimeError("UF_CSHARP_ANALYZER=ast but worker returned no file results")
        elif mode == "ast":
            raise RuntimeError("UF_CSHARP_ANALYZER=ast but AST worker did not succeed")

    return _build_regex_map(files)


class CSharpAdapter:
    """Registry-facing adapter for C# (Roslyn AST preferred, regex fallback)."""

    language = "csharp"
    extensions = CSHARP_EXTENSIONS
    fidelity = "ast"
    note = (
        "Prefers Roslyn AST via dotnet run worker (csharp-ast, ast-cyclomatic); "
        "degrades to regex (csharp-best-effort, keyword-heuristic) if .NET SDK missing. "
        "Same-file + same-namespace unique call edges. Not typechecked / not Python-parity."
    )

    def build_map(self, root: pathlib.Path) -> dict[str, Any]:
        return build_csharp_map(root)


def csharp_ast_status() -> dict[str, Any]:
    return {
        "mode": csharp_analyzer_mode(),
        "ast_available": ast_backend_available(),
    }
