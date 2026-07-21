"""Go analyzer (Wave 19 / Wave 28).

Preferred path: ``go run`` + ``go/ast`` worker → ``go-ast``, fidelity ``ast``,
complexity ``ast-cyclomatic``. Requires Go 1.21+ on PATH.

Fallback: conservative regex / heuristics → ``go-best-effort``,
``keyword-heuristic``. Override with ``UF_GO_ANALYZER=regex|ast|auto``.

Call edges: same-file unique short-name qualification. AST path may also
qualify **same-package** unique names across files in the scan set, and
**cross-package** selector calls (``alias.Func``) when the import path
uniquely maps to a package directory under the scan root (nearest
``go.mod``). Regex stays same-file-only. Not Python-parity.
"""

from __future__ import annotations

import os
import pathlib
import re
from typing import Any

from ucli.analyzers.go_ast_bridge import (
    ast_backend_available,
    go_analyzer_mode,
    run_go_ast_worker,
)

GO_EXTENSIONS = frozenset({".go"})

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
        "vendor",
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
        "switch",
        "select",
        "case",
        "default",
        "return",
        "go",
        "defer",
        "range",
        "func",
        "type",
        "struct",
        "interface",
        "map",
        "chan",
        "var",
        "const",
        "package",
        "import",
        "make",
        "new",
        "len",
        "cap",
        "append",
        "copy",
        "delete",
        "close",
        "panic",
        "recover",
        "print",
        "println",
        "complex",
        "real",
        "imag",
        "min",
        "max",
        "clear",
        "true",
        "false",
        "nil",
        "iota",
        "break",
        "continue",
        "fallthrough",
        "goto",
        "else",
    }
)

# func Name(  OR  func (x *T) Name( / func (x T) Name(
_RE_FUNC = re.compile(
    r"(?m)^func\s+(?:\(\s*\w+\s+\*?([A-Za-z_][\w]*)\s*\)\s+)?([A-Za-z_][\w]*)\s*\(",
)
_RE_CALL = re.compile(r"(?<![.\w])([A-Za-z_][\w]*)\s*\(")
_RE_COMPLEXITY = re.compile(r"\b(?:if|for|switch|case|select)\b|\&\&|\|\|")
_RE_PACKAGE = re.compile(r"(?m)^package\s+([A-Za-z_][\w]*)\b")
_RE_GOMOD_MODULE = re.compile(r"(?m)^module\s+(\S+)\s*$")


def _is_go_file(path: pathlib.Path) -> bool:
    if path.suffix.lower() not in GO_EXTENSIONS:
        return False
    name = path.name
    if name.endswith("_test.go"):
        # Include tests — they are real Go; still same honesty rules.
        pass
    return not any(part.startswith(".") for part in path.parts if part not in (".", ".."))


def _should_skip_dir(name: str) -> bool:
    return name in _SKIP_DIR_NAMES or name.startswith(".")


def _strip_comments_and_strings(src: str) -> str:
    """Replace comments and string/raw literals with spaces (keep newlines)."""
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
        if ch in {'"', "'", "`"}:
            quote = ch
            out.append(" ")
            i += 1
            while i < n:
                c = src[i]
                if quote != "`" and c == "\\" and i + 1 < n:
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


def _parse_go_source(src: str, file_path: pathlib.Path) -> tuple[dict[str, Any], str]:
    """Return (functions_by_local_name, package_name)."""
    pkg_m = _RE_PACKAGE.search(src)
    package = pkg_m.group(1) if pkg_m else ""
    cleaned = _strip_comments_and_strings(src)
    out: dict[str, Any] = {}

    def add(local: str, simple: str, body: str, line: int) -> None:
        ftype = "method" if "." in local else "function"
        calls = [c for c in _calls_in_body(body) if c != simple]
        out[local] = {
            "name": local,
            "simple_name": simple,
            "file": file_path.as_posix(),
            "type": ftype,
            "calls": calls,
            "callers": [],
            "complexity": _complexity_heuristic(body),
            "line": line,
            "language": "go",
            "package": package,
            "side_effects": [],
        }

    for m in _RE_FUNC.finditer(cleaned):
        recv, name = m.group(1), m.group(2)
        local = f"{recv}.{name}" if recv else name
        open_brace = cleaned.find("{", m.end() - 1)
        if open_brace < 0:
            add(local, name, "", _line_of(src, m.start()))
            continue
        end = _brace_block_end(cleaned, open_brace)
        body = cleaned[open_brace:end]
        add(local, name, body, _line_of(src, m.start()))

    return out, package


def _parse_file(file_path: pathlib.Path) -> tuple[dict[str, Any], str]:
    try:
        src = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return {}, ""
    try:
        return _parse_go_source(src, file_path)
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
        if simple != short:
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
                # Selector / dotted — leave bare (no invent).
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
        meta["callers"] = sorted(set(meta.get("callers", [])))


def _attach_same_package_edges(
    functions: dict[str, Any],
    file_packages: dict[str, str],
) -> None:
    """Qualify bare calls to unique same-package names across files (AST path).

    Fail closed: package name must match; callee short/simple name must be unique
    within that package's scanned functions.
    """
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
            if ":" in token:
                new_calls.append(token)
                continue
            if "." in token:
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
        meta["callers"] = sorted(set(meta.get("callers", [])))


def _read_module_path(gomod: pathlib.Path) -> str | None:
    try:
        text = gomod.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    m = _RE_GOMOD_MODULE.search(text)
    if not m:
        return None
    return m.group(1).strip()


def _nearest_go_mod(file_path: pathlib.Path, scan_root: pathlib.Path) -> pathlib.Path | None:
    """Walk parents from file dir up to scan_root inclusive for go.mod."""
    try:
        start = file_path if file_path.is_dir() else file_path.parent
        root = scan_root.resolve()
        cur = start.resolve()
    except OSError:
        return None
    while True:
        candidate = cur / "go.mod"
        if candidate.is_file():
            return candidate
        if cur == root or cur.parent == cur:
            break
        if root not in cur.parents and cur != root:
            break
        cur = cur.parent
    root_mod = scan_root / "go.mod"
    if root_mod.is_file():
        return root_mod
    return None


def _package_dir_of(file_posix: str) -> str:
    return str(pathlib.PurePosixPath(file_posix).parent)


def _resolve_scan_path(sample: str, scan_root: pathlib.Path) -> pathlib.Path:
    """Resolve a display/file path that may be cwd-relative or scan-root-relative."""
    p = pathlib.Path(sample)
    if p.is_absolute():
        return p.resolve()
    if p.exists():
        return p.resolve()
    cand = scan_root / sample
    if cand.exists():
        return cand.resolve()
    # Display sometimes embeds the scan root prefix already (cwd-relative walk).
    try:
        root_res = scan_root.resolve()
        joined = (pathlib.Path.cwd() / sample).resolve()
        if root_res == joined or root_res in joined.parents:
            return joined
    except OSError:
        pass
    return p.resolve()


def _import_path_for_dir(
    pkg_dir_posix: str,
    scan_root: pathlib.Path,
    file_packages: dict[str, str],
) -> str | None:
    """Compute Go import path for a package directory via nearest go.mod.

    Returns None when no module file is found under the scan root.
    """
    sample = next(
        (f for f in file_packages if _package_dir_of(f) == pkg_dir_posix),
        None,
    )
    if sample is None:
        return None
    sample_path = _resolve_scan_path(sample, scan_root)
    gomod = _nearest_go_mod(sample_path, scan_root)
    if gomod is None:
        return None
    module = _read_module_path(gomod)
    if not module:
        return None
    try:
        mod_root = gomod.parent.resolve()
        pkg_abs = sample_path.resolve().parent
        rel = pkg_abs.relative_to(mod_root).as_posix()
    except (ValueError, OSError):
        return None
    if rel in {".", ""}:
        return module
    return f"{module}/{rel}"


def _build_import_path_index(
    functions: dict[str, Any],
    file_packages: dict[str, str],
    scan_root: pathlib.Path,
) -> tuple[dict[str, str], dict[str, str], dict[str, dict[str, list[str]]]]:
    """Return (import_path→pkg_dir, pkg_dir→package_name, pkg_dir→short→[qns]).

    Import paths that map to more than one package directory are omitted
    (invent-free).
    """
    pkg_dirs: set[str] = set()
    pkg_dir_name: dict[str, str] = {}
    by_dir_short: dict[str, dict[str, list[str]]] = {}

    for qn, meta in functions.items():
        file = str(meta.get("file") or "")
        if not file:
            continue
        pkg_dir = _package_dir_of(file)
        pkg_dirs.add(pkg_dir)
        pkg = str(meta.get("package") or file_packages.get(file) or "")
        if pkg and pkg_dir not in pkg_dir_name:
            pkg_dir_name[pkg_dir] = pkg
        short = qn.rsplit(":", 1)[-1]
        simple = meta.get("simple_name") or short.rsplit(".", 1)[-1]
        bucket = by_dir_short.setdefault(pkg_dir, {})
        bucket.setdefault(short, []).append(qn)
        if simple != short:
            bucket.setdefault(simple, []).append(qn)

    path_to_dirs: dict[str, list[str]] = {}
    for pkg_dir in pkg_dirs:
        ipath = _import_path_for_dir(pkg_dir, scan_root, file_packages)
        if not ipath:
            continue
        path_to_dirs.setdefault(ipath, []).append(pkg_dir)

    unique_path_to_dir: dict[str, str] = {}
    for ipath, dirs in path_to_dirs.items():
        uniq = list(dict.fromkeys(dirs))
        if len(uniq) == 1:
            unique_path_to_dir[ipath] = uniq[0]

    return unique_path_to_dir, pkg_dir_name, by_dir_short


def _unique_pick(candidates: list[str], token: str) -> str | None:
    candidates = list(dict.fromkeys(candidates))
    exact = [c for c in candidates if c.rsplit(":", 1)[-1] == token]
    pick = exact if len(exact) == 1 else (candidates if len(candidates) == 1 else [])
    return pick[0] if len(pick) == 1 else None


def _attach_cross_package_import_edges(
    functions: dict[str, Any],
    file_packages: dict[str, str],
    file_imports: dict[str, list[dict[str, str]]],
    scan_root: pathlib.Path,
) -> None:
    """Qualify ``alias.Func`` (and unique dot-import bare names) invent-free.

    Rules (fail closed):
    - Import path must uniquely map to one package directory under the scan
      root via nearest ``go.mod`` module path + relative dir.
    - Selector local name must match the import binding (explicit alias, or
      default = package clause name of the resolved package).
    - Callee short/simple name must be unique within that package directory.
    - Blank imports are ignored; ambiguous paths / names stay bare.
    """
    path_to_dir, pkg_dir_name, by_dir_short = _build_import_path_index(
        functions, file_packages, scan_root
    )
    if not path_to_dir:
        return

    for caller_qn, meta in functions.items():
        caller_file = str(meta.get("file") or "")
        imports = file_imports.get(caller_file) or []
        binding_to_dir: dict[str, str] = {}
        dot_dirs: list[str] = []
        for imp in imports:
            ipath = str(imp.get("path") or "").strip()
            if not ipath:
                continue
            pkg_dir = path_to_dir.get(ipath)
            if not pkg_dir:
                continue
            name = str(imp.get("name") or "")
            if name == "_":
                continue
            if name == ".":
                dot_dirs.append(pkg_dir)
                continue
            if name:
                prev = binding_to_dir.get(name)
                if prev is not None and prev != pkg_dir:
                    binding_to_dir.pop(name, None)
                    continue
                binding_to_dir[name] = pkg_dir
                continue
            pkg_name = pkg_dir_name.get(pkg_dir) or ""
            if not pkg_name:
                continue
            prev = binding_to_dir.get(pkg_name)
            if prev is not None and prev != pkg_dir:
                binding_to_dir.pop(pkg_name, None)
                continue
            binding_to_dir[pkg_name] = pkg_dir

        new_calls: list[str] = []
        for token in meta.get("calls") or []:
            if ":" in token:
                new_calls.append(token)
                continue
            if "." in token:
                alias, _, sel = token.partition(".")
                if not alias or not sel or "." in sel:
                    new_calls.append(token)
                    continue
                pkg_dir = binding_to_dir.get(alias)
                if not pkg_dir:
                    new_calls.append(token)
                    continue
                pick = _unique_pick(by_dir_short.get(pkg_dir, {}).get(sel, []), sel)
                if pick and pick != caller_qn:
                    new_calls.append(pick)
                    functions[pick].setdefault("callers", []).append(caller_qn)
                else:
                    new_calls.append(token)
                continue
            if not dot_dirs:
                new_calls.append(token)
                continue
            picks: list[str] = []
            for d in dict.fromkeys(dot_dirs):
                p = _unique_pick(by_dir_short.get(d, {}).get(token, []), token)
                if p:
                    picks.append(p)
            picks = list(dict.fromkeys(picks))
            if len(picks) == 1 and picks[0] != caller_qn:
                callee = picks[0]
                new_calls.append(callee)
                functions[callee].setdefault("callers", []).append(caller_qn)
            else:
                new_calls.append(token)
        meta["calls"] = list(dict.fromkeys(new_calls))
    for meta in functions.values():
        meta["callers"] = sorted(set(meta.get("callers", [])))


def _collect_go_files(root: pathlib.Path) -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    if root.is_file():
        return [root] if _is_go_file(root) else []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not _should_skip_dir(d)]
        for name in filenames:
            path = pathlib.Path(dirpath) / name
            if _is_go_file(path):
                files.append(path)
    return files


def _build_regex_map(root: pathlib.Path, files: list[pathlib.Path]) -> dict[str, Any]:
    functions: dict[str, Any] = {}
    for file_path in files:
        parsed, package = _parse_file(file_path)
        for func, meta in parsed.items():
            key = f"{file_path.with_suffix('').as_posix()}:{func}"
            m = dict(meta)
            m["analyzer"] = "go-best-effort"
            m["complexity_kind"] = "keyword-heuristic"
            m["language"] = "go"
            m["package"] = package or m.get("package") or ""
            functions[key] = m

    _attach_and_qualify_same_file(functions)
    return {
        "language": "go",
        "functions": functions,
        "analyzer": "go-best-effort",
        "analyzer_fidelity": "best-effort",
        "complexity_kind": "keyword-heuristic",
        "analyzer_note": (
            "Go map via regex heuristics — not go/parser; complexity is keyword-based "
            "(not structural AST); call edges are same-file unique names only; "
            "no cross-package invent. Set UF_GO_ANALYZER=auto with Go 1.21+ on PATH "
            "for the go-ast path."
        ),
    }


def _remap_display_file(
    rel_file: str,
    files: list[pathlib.Path],
    root_posix: str,
) -> tuple[str, str]:
    rel_norm = rel_file.replace("\\", "/").lstrip("./")
    walk_match = next(
        (p for p in files if p.as_posix() == rel_norm or p.as_posix().endswith("/" + rel_norm)),
        None,
    )
    if walk_match is not None:
        display_file = walk_match.as_posix()
        stem = walk_match.with_suffix("").as_posix()
    else:
        display_file = (
            f"{root_posix}/{rel_norm}"
            if root_posix and not rel_norm.startswith(root_posix)
            else rel_norm
        )
        stem = str(pathlib.PurePosixPath(display_file).with_suffix(""))
    return display_file, stem


def _build_ast_map(
    root: pathlib.Path,
    files: list[pathlib.Path],
    worker_payload: dict[str, Any],
) -> dict[str, Any]:
    functions: dict[str, Any] = {}
    file_packages: dict[str, str] = {}
    file_imports: dict[str, list[dict[str, str]]] = {}
    root_posix = root.as_posix().rstrip("/")
    scan_root = root if root.is_dir() else root.parent

    for entry in worker_payload.get("files") or []:
        if not isinstance(entry, dict):
            continue
        rel_file = str(entry.get("file") or "")
        display_file, stem = _remap_display_file(rel_file, files, root_posix)

        pkg = str(entry.get("package") or "")
        file_packages[display_file] = pkg

        remapped: list[dict[str, str]] = []
        for imp in entry.get("imports") or []:
            if not isinstance(imp, dict):
                continue
            path = str(imp.get("path") or "").strip()
            if not path:
                continue
            remapped.append({"path": path, "name": str(imp.get("name") or "")})
        file_imports[display_file] = remapped

        locals_map = entry.get("functions") or {}
        for local, meta in locals_map.items():
            if not isinstance(meta, dict):
                continue
            qn = f"{stem}:{local}"
            m = dict(meta)
            m["name"] = str(m.get("name") or local)
            m["file"] = display_file
            m["type"] = str(m.get("type") or ("method" if "." in local else "function"))
            m["analyzer"] = "go-ast"
            m["complexity_kind"] = "ast-cyclomatic"
            m["language"] = "go"
            m["package"] = pkg
            m.setdefault("callers", [])
            m.setdefault("side_effects", [])
            m.setdefault("simple_name", local.rsplit(".", 1)[-1])
            if m.get("calls") is None:
                m["calls"] = []
            if "complexity" in m:
                m["complexity"] = int(m["complexity"] or 1)
            if "line" in m:
                m["line"] = int(m["line"] or 1)
            functions[qn] = m

    _attach_and_qualify_same_file(functions)
    _attach_same_package_edges(functions, file_packages)
    _attach_cross_package_import_edges(functions, file_packages, file_imports, scan_root)

    formula = worker_payload.get("complexity_formula") or (
        "1 + IfStmt/ForStmt/RangeStmt/CaseClause + &&/|| extras; nested FuncLit excluded"
    )
    return {
        "language": "go",
        "functions": functions,
        "analyzer": "go-ast",
        "analyzer_fidelity": "ast",
        "complexity_kind": "ast-cyclomatic",
        "analyzer_note": (
            "Go map via go/parser + go/ast (parse only). "
            f"Complexity is ast-cyclomatic: {formula}. "
            "Call edges: same-file unique names, same-package unique names across "
            "scanned files, and invent-free cross-package selector edges when an "
            "import path uniquely maps under the scan root (nearest go.mod). "
            "Not Python-parity; not typechecked / no packages.Load. "
            "Falls back to go-best-effort regex when the Go toolchain is unavailable."
        ),
    }


def build_go_map(root: pathlib.Path) -> dict[str, Any]:
    """Build a Go map for ``root`` (AST preferred, regex fallback)."""
    root = pathlib.Path(root)
    files = _collect_go_files(root)
    mode = go_analyzer_mode()
    scan_root = root if root.is_dir() else root.parent

    if mode != "regex":
        payload = run_go_ast_worker(scan_root, files)
        if payload is not None:
            worker_files = payload.get("files") or []
            if worker_files or not files:
                return _build_ast_map(root, files, payload)
            if mode == "ast":
                raise RuntimeError("UF_GO_ANALYZER=ast but worker returned no file results")
        elif mode == "ast":
            raise RuntimeError("UF_GO_ANALYZER=ast but AST worker did not succeed")

    return _build_regex_map(root, files)


class GoAdapter:
    """Registry-facing adapter for Go analysis (AST preferred, regex fallback)."""

    language = "go"
    extensions = GO_EXTENSIONS
    fidelity = "ast"
    note = (
        "Prefers go/parser AST via `go run` worker (go-ast, ast-cyclomatic); "
        "degrades to regex (go-best-effort, keyword-heuristic) if Go toolchain missing. "
        "Same-file + same-package unique edges; AST path invent-free cross-package "
        "import-path selector edges when uniquely resolved under scan root. "
        "Not Python-parity."
    )

    def build_map(self, root: pathlib.Path) -> dict[str, Any]:
        return build_go_map(root)


def go_ast_status() -> dict[str, Any]:
    return {
        "mode": go_analyzer_mode(),
        "ast_available": ast_backend_available(),
    }
