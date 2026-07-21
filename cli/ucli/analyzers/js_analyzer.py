"""JavaScript / TypeScript analyzer (Wave 15–17).

Preferred path (Wave 17): Node + TypeScript compiler API via
``js_ast/parse_worker.mjs`` → analyzer id ``javascript-ast``, fidelity
``ast``, complexity ``ast-cyclomatic`` (decision-point formula documented on
the map). Requires Node 18+ and ``npm install`` in ``cli/ucli/analyzers/js_ast``.

Fallback (Wave 15): conservative regex / heuristics → ``javascript-best-effort``.
Override with ``UF_JS_ANALYZER=regex|ast|auto`` (default ``auto``).

Call edges: same-file unique short-name qualification. AST path may also
resolve high-confidence relative imports (``./foo`` / ``../foo``), nearest
``package.json`` ``"exports"`` / ``"imports"``, and nearest ``tsconfig`` /
``jsconfig`` ``paths`` aliases when uniquely mapped — never bare npm packages
or typechecked resolution. Ambiguous or dotted callees stay bare. Not
Python-parity (no typed ``obj.method`` resolution).
"""

from __future__ import annotations

import os
import pathlib
import re
from typing import Any

from ucli.analyzers.js_ast_bridge import (
    ast_backend_available,
    js_analyzer_mode,
    run_js_ast_worker,
)

# Extensions handled by this adapter (JS + light TS/JSX).
JS_EXTENSIONS = frozenset({".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx"})

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
        "catch",
        "return",
        "typeof",
        "new",
        "await",
        "void",
        "delete",
        "throw",
        "class",
        "function",
        "of",
        "in",
        "case",
        "else",
        "do",
        "try",
        "finally",
        "with",
        "yield",
        "import",
        "export",
        "from",
        "as",
        "let",
        "const",
        "var",
        "async",
        "super",
        "this",
        "true",
        "false",
        "null",
        "undefined",
        "debugger",
        "instanceof",
    }
)

# function name( / async function name(
_RE_FUNCTION = re.compile(
    r"(?:^|[^.\w$])(?:async\s+)?function\s*\*?\s*([A-Za-z_$][\w$]*)\s*\(",
    re.MULTILINE,
)
# const/let/var name = [async] (params) =>  OR  name = [async] function
_RE_ARROW_OR_FN_EXPR = re.compile(
    r"(?:^|[^.\w$])(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*"
    r"(?:async\s+)?(?:function\s*\*?|(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*(?::\s*[^=;{]+?)?\s*=>)",
    re.MULTILINE,
)
# class Name {
_RE_CLASS = re.compile(
    r"(?:^|[^.\w$])class\s+([A-Za-z_$][\w$]*)\s*(?:extends\s+[^{]+)?\{",
    re.MULTILINE,
)
# method-like inside class body: name( or async name( or get/set name(
_RE_METHOD = re.compile(
    r"(?:^|\n)\s*(?:async\s+)?(?:get\s+|set\s+|static\s+)?(\*?[A-Za-z_$][\w$]*)\s*\(",
)
# bare call: name(
_RE_CALL = re.compile(r"(?<![.\w$])([A-Za-z_$][\w$]*)\s*\(")
# complexity keyword hits
_RE_COMPLEXITY = re.compile(
    r"\b(?:if|for|while|case|catch)\b|\&\&|\|\||\?(?![?.])",
)


def _is_js_file(path: pathlib.Path) -> bool:
    if path.suffix.lower() not in JS_EXTENSIONS:
        return False
    return not any(part.startswith(".") for part in path.parts if part not in (".", ".."))


def _should_skip_dir(name: str) -> bool:
    return name in _SKIP_DIR_NAMES or name.startswith(".")


def _strip_comments_and_strings(src: str) -> str:
    """Replace comments and string/template literals with spaces (keep newlines)."""

    out: list[str] = []
    i = 0
    n = len(src)
    while i < n:
        ch = src[i]
        # line comment
        if ch == "/" and i + 1 < n and src[i + 1] == "/":
            i += 2
            while i < n and src[i] not in "\n\r":
                out.append(" ")
                i += 1
            continue
        # block comment
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
        # strings / templates
        if ch in {'"', "'", "`"}:
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


def _brace_block_end(src: str, open_idx: int) -> int:
    """Return index after matching ``}`` for ``{`` at open_idx, or len(src)."""
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


def _find_body_after_paren(src: str, paren_open: int) -> tuple[int, int] | None:
    """Given index of ``(`` for a function signature, find ``{...}`` body span."""
    n = len(src)
    i = paren_open
    depth = 0
    while i < n:
        c = src[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                i += 1
                break
        i += 1
    else:
        return None
    while i < n and src[i] in " \t\r\n:":
        # skip optional return type-ish ``: Type`` then whitespace
        if src[i] == ":":
            i += 1
            while i < n and src[i] not in "{;=\n":
                i += 1
            continue
        i += 1
    # arrow with expression body — treat until semicolon / newline as body
    if i < n and src.startswith("=>", i):
        i += 2
        while i < n and src[i] in " \t":
            i += 1
        if i < n and src[i] == "{":
            end = _brace_block_end(src, i)
            return i, end
        start = i
        while i < n and src[i] not in ";\n\r":
            i += 1
        return start, i
    if i < n and src[i] == "{":
        end = _brace_block_end(src, i)
        return i, end
    return None


def _heuristic_complexity(body: str) -> int:
    """Keyword / operator complexity heuristic (not AST McCabe)."""
    return 1 + len(_RE_COMPLEXITY.findall(body))


def _extract_calls(body: str, self_name: str) -> list[str]:
    calls: list[str] = []
    for m in _RE_CALL.finditer(body):
        name = m.group(1)
        if name == self_name or name in _KEYWORD_CALLEES:
            continue
        # Skip the function keyword match at definition start — already filtered.
        calls.append(name)
    # Preserve order, unique
    return list(dict.fromkeys(calls))


def _line_of(src: str, idx: int) -> int:
    return src.count("\n", 0, idx) + 1


def _strip_ts_type_noise(src: str) -> str:
    """Best-effort removal of common TypeScript surface syntax (not a typechecker).

    Strips ``interface`` / ``type`` blocks and simple parameter/return annotations
    so regex def/call extraction can see JS-shaped tokens. Generics, mapped types,
    and ambient declarations may still confuse the heuristic parser — that is
    documented as a limit, not silently claimed away.
    """
    # Drop interface / type alias declarations (brace- or semicolon-terminated).
    out = re.sub(
        r"(?:^|\n)\s*(?:export\s+)?(?:interface|type)\s+[A-Za-z_$][\w$]*"
        r"[^{;\n]*(?:\{[^}]*\}|;)",
        "\n",
        src,
        flags=re.MULTILINE,
    )
    # Rough ``): Type {`` / ``): Type =>`` return annotations → ``) {`` / ``) =>``.
    out = re.sub(r"\)\s*:\s*[A-Za-z_$][\w$<>\[\]|&.,\s]*?(?=\{|=>)", ") ", out)
    # Rough param ``name: Type`` inside parens — only simple identifiers/types.
    out = re.sub(
        r"([,(]\s*[A-Za-z_$][\w$]*)\s*:\s*[A-Za-z_$][\w$<>\[\]|&.?]*",
        r"\1",
        out,
    )
    return out


def _parse_js_source(src: str, file_path: pathlib.Path) -> dict[str, Any]:
    """Parse one file into local_name -> meta (pre-qualification)."""
    cleaned = _strip_comments_and_strings(src)
    if file_path.suffix.lower() in {".ts", ".tsx"}:
        cleaned = _strip_ts_type_noise(cleaned)
    out: dict[str, Any] = {}

    def add_func(local: str, body: str, line: int) -> None:
        if not local or local.startswith("*"):
            local = local.lstrip("*")
        if not local or local in out:
            # Duplicate local names: keep first; avoid inventing disambiguation.
            if local in out:
                return
        simple = local.rsplit(".", 1)[-1]
        out[local] = {
            "file": str(file_path.as_posix()),
            "calls": _extract_calls(body, simple),
            "callers": [],
            "complexity": _heuristic_complexity(body),
            "side_effects": [],
            "has_docstring": False,
            "has_return_annotation": False,
            "has_type_hints": False,
            "typed_params": 0,
            "total_params": 0,
            "fully_typed_params": False,
            "simple_name": simple,
            "line": line,
            "analyzer": "javascript-best-effort",
            "complexity_kind": "keyword-heuristic",
            "language": (
                "typescript" if file_path.suffix.lower() in {".ts", ".tsx"} else "javascript"
            ),
        }

    # Top-level function declarations
    for m in _RE_FUNCTION.finditer(cleaned):
        name = m.group(1)
        paren = cleaned.find("(", m.start())
        if paren < 0:
            continue
        span = _find_body_after_paren(cleaned, paren)
        body = cleaned[span[0] : span[1]] if span else ""
        add_func(name, body, _line_of(src, m.start()))

    # const/let/var bindings to functions / arrows
    for m in _RE_ARROW_OR_FN_EXPR.finditer(cleaned):
        name = m.group(1)
        # Find ``(`` or ``=>`` region from assignment
        eq = cleaned.find("=", m.start())
        if eq < 0:
            continue
        rest = cleaned[eq + 1 :].lstrip()
        abs_start = eq + 1 + (len(cleaned[eq + 1 :]) - len(rest))
        paren = cleaned.find("(", abs_start)
        arrow = cleaned.find("=>", abs_start)
        # function expression: function(
        fn_kw = re.search(r"\bfunction\b", cleaned[abs_start : abs_start + 40])
        if fn_kw and paren >= 0 and (arrow < 0 or paren < arrow):
            span = _find_body_after_paren(cleaned, paren)
        elif arrow >= 0:
            # params may be single ident without paren
            if paren >= 0 and paren < arrow:
                span = _find_body_after_paren(cleaned, paren)
            else:
                # name = x => body
                i = arrow + 2
                while i < len(cleaned) and cleaned[i] in " \t":
                    i += 1
                if i < len(cleaned) and cleaned[i] == "{":
                    end = _brace_block_end(cleaned, i)
                    span = (i, end)
                else:
                    start = i
                    while i < len(cleaned) and cleaned[i] not in ";\n\r":
                        i += 1
                    span = (start, i)
        else:
            span = None
        body = cleaned[span[0] : span[1]] if span else ""
        add_func(name, body, _line_of(src, m.start()))

    # Class methods (best-effort brace matching)
    for cm in _RE_CLASS.finditer(cleaned):
        class_name = cm.group(1)
        brace = cleaned.find("{", cm.end() - 1)
        if brace < 0:
            continue
        class_end = _brace_block_end(cleaned, brace)
        class_body = cleaned[brace + 1 : class_end - 1]
        # Offset for line numbers
        body_offset = brace + 1
        for mm in _RE_METHOD.finditer(class_body):
            method = mm.group(1).lstrip("*")
            if method in {"if", "for", "while", "switch", "catch", "function"}:
                continue
            # constructor kept as Class.constructor locally? use Class.method
            local = f"{class_name}.{method}"
            abs_paren = body_offset + class_body.find("(", mm.start())
            if abs_paren < body_offset:
                continue
            span = _find_body_after_paren(cleaned, abs_paren)
            body = cleaned[span[0] : span[1]] if span else ""
            add_func(local, body, _line_of(src, body_offset + mm.start()))

    return out


def _parse_file(file_path: pathlib.Path) -> dict[str, Any]:
    try:
        src = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return {}
    try:
        return _parse_js_source(src, file_path)
    except Exception:
        return {}


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
        if simple != short:
            bucket.setdefault(simple, []).append(qn)
    return by_file_short


def _attach_and_qualify_same_file(functions: dict[str, Any]) -> None:
    """Same-file unique short-name edges only — no cross-file invention."""
    by_file_short = _build_file_indexes(functions)
    for caller_qn, meta in functions.items():
        caller_file = meta.get("file", "")
        local_map = by_file_short.get(caller_file, {})
        qualified: list[str] = []
        for token in meta.get("calls", []):
            if "." in token:
                # Dotted: leave bare; do not invent method resolution.
                qualified.append(token)
                continue
            candidates = list(dict.fromkeys(local_map.get(token, [])))
            # Prefer exact local key match over simple_name collisions.
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
        meta["callers"] = sorted(set(meta.get("callers", [])))


def _attach_relative_import_edges(
    functions: dict[str, Any],
    file_imports: dict[str, list[dict[str, Any]]],
    file_exports: dict[str, list[str]],
    file_reexports: dict[str, list[dict[str, Any]]] | None = None,
) -> None:
    """Qualify bare calls via high-confidence relative imports only.

    Rules (fail closed):
    - Specifier must already be resolved to a real file by the worker.
    - Binding must map local name → exported name (not ``*`` / default-only).
    - Exported name must appear exactly once as a top-level function simple
      name in the target file map, **or** uniquely via one/two-hop re-export
      barrels (``export { x } from './mod'``) when the defining file is unique.
    """
    file_reexports = file_reexports or {}
    # qn index by file + simple/local
    by_file_local: dict[str, dict[str, list[str]]] = {}
    for qn, meta in functions.items():
        file = meta.get("file", "")
        local = qn.rsplit(":", 1)[-1]
        simple = meta.get("simple_name") or local.rsplit(".", 1)[-1]
        bucket = by_file_local.setdefault(file, {})
        bucket.setdefault(local, []).append(qn)
        if simple != local:
            bucket.setdefault(simple, []).append(qn)

    def resolve_export_qns(
        file_key: str, export_name: str, *, depth: int = 0, seen: set[str] | None = None
    ) -> list[str]:
        if depth > 2:
            return []
        seen = set(seen or ())
        if file_key in seen:
            return []
        seen.add(file_key)
        target = by_file_local.get(file_key) or {}
        cands = list(dict.fromkeys(target.get(export_name, [])))
        exact = [c for c in cands if c.rsplit(":", 1)[-1] == export_name]
        pick = exact if len(exact) == 1 else (cands if len(cands) == 1 else [])
        if len(pick) == 1:
            return pick
        # Barrel re-export chase (Wave 21)
        for rex in file_reexports.get(file_key) or []:
            if not isinstance(rex, dict):
                continue
            if rex.get("name") != export_name:
                continue
            from_file = rex.get("from")
            imported = rex.get("imported") or export_name
            if not isinstance(from_file, str) or not from_file:
                continue
            nested = resolve_export_qns(from_file, str(imported), depth=depth + 1, seen=seen)
            if len(nested) == 1:
                return nested
        return []

    for caller_qn, meta in functions.items():
        caller_file = meta.get("file", "")
        imports = file_imports.get(caller_file) or []
        # local binding -> list of candidate qns in imported file
        import_map: dict[str, list[str]] = {}
        for imp in imports:
            resolved = imp.get("resolved")
            bindings = imp.get("bindings") or {}
            if not resolved or not isinstance(bindings, dict):
                continue
            exports = set(file_exports.get(resolved) or [])
            for local_name, imported_name in bindings.items():
                if imported_name in {"*", "default"}:
                    continue
                if exports and imported_name not in exports:
                    # If we have an export list, require membership.
                    continue
                pick = resolve_export_qns(str(resolved), str(imported_name))
                if len(pick) == 1:
                    import_map.setdefault(local_name, []).append(pick[0])

        new_calls: list[str] = []
        for token in meta.get("calls") or []:
            if ":" in token or "." in token:
                new_calls.append(token)
                continue
            cands = list(dict.fromkeys(import_map.get(token, [])))
            if len(cands) == 1 and cands[0] != caller_qn:
                callee = cands[0]
                new_calls.append(callee)
                functions[callee].setdefault("callers", []).append(caller_qn)
            else:
                new_calls.append(token)
        meta["calls"] = list(dict.fromkeys(new_calls))
    for meta in functions.values():
        meta["callers"] = sorted(set(meta.get("callers", [])))


def _collect_js_files(root: pathlib.Path) -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    if root.is_file():
        return [root] if _is_js_file(root) else []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not _should_skip_dir(d)]
        for name in filenames:
            path = pathlib.Path(dirpath) / name
            if _is_js_file(path):
                files.append(path)
    return files


def _build_regex_map(root: pathlib.Path, files: list[pathlib.Path]) -> dict[str, Any]:
    """Best-effort regex map (Wave 15 fallback)."""
    functions: dict[str, Any] = {}
    suffixes = {p.suffix.lower() for p in files}
    lang = "typescript" if suffixes and suffixes <= {".ts", ".tsx"} else "javascript"
    analyzer_id = _analyzer_id_for(lang, "best-effort")

    for file_path in files:
        parsed = _parse_file(file_path)
        for func, meta in parsed.items():
            # Keep path-as-walked keys (matches Wave 15 fixtures / qnames).
            key = f"{file_path.with_suffix('').as_posix()}:{func}"
            m = dict(meta)
            # Per-file language; map-level analyzer uses tree primary language.
            file_lang = (
                "typescript" if file_path.suffix.lower() in {".ts", ".tsx"} else "javascript"
            )
            m["analyzer"] = _analyzer_id_for(file_lang, "best-effort")
            m["complexity_kind"] = "keyword-heuristic"
            m["language"] = file_lang
            functions[key] = m

    _attach_and_qualify_same_file(functions)
    return {
        "language": lang,
        "functions": functions,
        "analyzer": analyzer_id,
        "analyzer_fidelity": "best-effort",
        "complexity_kind": "keyword-heuristic",
        "analyzer_note": (
            "JavaScript/TypeScript map via regex heuristics — not a full parser; "
            "complexity is keyword-based (not structural AST); call edges are same-file "
            "unique names only; TypeScript types are stripped best-effort and not "
            "interpreted; no parity with Python AST / import-gated resolution. "
            "Set UF_JS_ANALYZER=auto and install Node + cli/ucli/analyzers/js_ast "
            "deps for the AST path."
        ),
    }


def _build_ast_map(
    root: pathlib.Path,
    files: list[pathlib.Path],
    worker_payload: dict[str, Any],
) -> dict[str, Any]:
    """Assemble map from AST worker per-file results."""
    functions: dict[str, Any] = {}
    file_imports: dict[str, list[dict[str, Any]]] = {}
    file_exports: dict[str, list[str]] = {}
    file_reexports: dict[str, list[dict[str, Any]]] = {}

    # Map worker-relative file paths back to walk paths for stable qnames.
    # Worker emits paths relative to scan root; fixtures expect root-prefixed
    # paths when root is itself relative (e.g. examples/js_toy/math:add).
    root_posix = root.as_posix().rstrip("/")

    for entry in worker_payload.get("files") or []:
        if not isinstance(entry, dict):
            continue
        rel_file = str(entry.get("file") or "")
        # Prefer walk path that matches this relative file.
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

        file_exports[display_file] = list(entry.get("exports") or [])
        remapped_reexports: list[dict[str, Any]] = []
        for rex in entry.get("reexports") or []:
            if not isinstance(rex, dict):
                continue
            rex2 = dict(rex)
            from_rel = rex2.get("from")
            if isinstance(from_rel, str) and from_rel:
                for p in files:
                    if p.as_posix().endswith(from_rel) or p.as_posix() == from_rel:
                        rex2["from"] = p.as_posix()
                        break
                else:
                    if root_posix and not from_rel.startswith(root_posix):
                        rex2["from"] = f"{root_posix}/{from_rel}"
            remapped_reexports.append(rex2)
        file_reexports[display_file] = remapped_reexports
        remapped_imports: list[dict[str, Any]] = []
        for imp in entry.get("imports") or []:
            if not isinstance(imp, dict):
                continue
            imp2 = dict(imp)
            resolved = imp2.get("resolved")
            if isinstance(resolved, str) and resolved:
                for p in files:
                    if p.as_posix().endswith(resolved) or p.as_posix() == resolved:
                        imp2["resolved"] = p.as_posix()
                        break
                else:
                    if root_posix and not resolved.startswith(root_posix):
                        imp2["resolved"] = f"{root_posix}/{resolved}"
            remapped_imports.append(imp2)
        file_imports[display_file] = remapped_imports

        locals_map = entry.get("functions") or {}
        for local, meta in locals_map.items():
            if not isinstance(meta, dict):
                continue
            qn = f"{stem}:{local}"
            m = dict(meta)
            file_lang = str(
                m.get("language")
                or (
                    "typescript"
                    if pathlib.Path(display_file).suffix.lower() in {".ts", ".tsx"}
                    else "javascript"
                )
            )
            m["file"] = display_file
            m["analyzer"] = _analyzer_id_for(file_lang, "ast")
            m["complexity_kind"] = "ast-cyclomatic"
            m["language"] = file_lang
            functions[qn] = m

    _attach_and_qualify_same_file(functions)
    _attach_relative_import_edges(functions, file_imports, file_exports, file_reexports)

    suffixes = {p.suffix.lower() for p in files}
    lang = "typescript" if suffixes and suffixes <= {".ts", ".tsx"} else "javascript"
    analyzer_id = _analyzer_id_for(lang, "ast")
    formula = worker_payload.get("complexity_formula") or (
        "1 + If/For/ForIn/ForOf/While/DoWhile/CaseClause/CatchClause/"
        "ConditionalExpression/&&/||; nested function bodies excluded"
    )
    return {
        "language": lang,
        "functions": functions,
        "analyzer": analyzer_id,
        "analyzer_fidelity": "ast",
        "complexity_kind": "ast-cyclomatic",
        "analyzer_note": (
            "JavaScript/TypeScript map via Node TypeScript compiler API (parse only). "
            f"Complexity is ast-cyclomatic (structural decision points): {formula}. "
            "Call edges: same-file unique names, plus high-confidence relative "
            "imports (./ / ../) to unique exports when resolved, including "
            "one/two-hop re-export barrels (export { x } from './mod'), nearest "
            'package.json "exports"/"imports", and nearest tsconfig/jsconfig '
            "paths aliases when uniquely mapped. No typed obj.method; no bare npm "
            "invent; not typechecked; not Python-parity. "
            "Falls back to *-best-effort regex when Node/typescript unavailable."
        ),
    }


def _analyzer_id_for(lang: str, kind: str) -> str:
    """Distinct javascript vs typescript analyzer labels (Wave 18)."""
    prefix = "typescript" if lang == "typescript" else "javascript"
    if kind == "ast":
        return f"{prefix}-ast"
    return f"{prefix}-best-effort"


def build_js_map(root: pathlib.Path) -> dict[str, Any]:
    """Build a JS/TS map for ``root`` (AST preferred, regex fallback)."""
    root = pathlib.Path(root)
    files = _collect_js_files(root)
    mode = js_analyzer_mode()
    scan_root = root if root.is_dir() else root.parent

    if mode != "regex":
        payload = run_js_ast_worker(scan_root, files)
        if payload is not None:
            # Empty worker result with non-empty inputs → degrade in auto mode.
            worker_files = payload.get("files") or []
            if worker_files or not files:
                return _build_ast_map(root, files, payload)
            if mode == "ast":
                raise RuntimeError("UF_JS_ANALYZER=ast but worker returned no file results")
        elif mode == "ast":
            raise RuntimeError("UF_JS_ANALYZER=ast but AST worker did not succeed")

    return _build_regex_map(root, files)


class JavaScriptAdapter:
    """Registry-facing adapter for JS/TS analysis (AST preferred, regex fallback)."""

    language = "javascript"
    extensions = JS_EXTENSIONS
    # Preferred fidelity when the Node AST path is available; actual map metadata
    # always records the path that ran (javascript-ast vs javascript-best-effort).
    fidelity = "ast"
    note = (
        "Prefers Node + TypeScript compiler API (javascript-ast, ast-cyclomatic); "
        "degrades to regex (javascript-best-effort, keyword-heuristic) if Node or "
        "cli/ucli/analyzers/js_ast deps are missing. Same-file call edges; optional "
        "relative-import / package.json exports|imports / tsconfig paths edges on "
        "the AST path when uniquely resolved. TypeScript types are not typechecked."
    )

    def build_map(self, root: pathlib.Path) -> dict[str, Any]:
        return build_js_map(root)


def js_ast_status() -> dict[str, Any]:
    """Small status dict for tests / doctor-style probes."""
    return {
        "mode": js_analyzer_mode(),
        "ast_available": ast_backend_available(),
    }
