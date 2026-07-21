"""Rust analyzer (Wave 22–23).

Preferred path (Wave 23): ``cargo run`` + ``syn`` worker → ``rust-ast``,
``ast-cyclomatic``. Requires cargo on PATH.

Fallback (Wave 22): conservative regex → ``rust-best-effort``,
``keyword-heuristic``. Override with ``UF_RUST_ANALYZER=regex|ast|auto``.

Call edges: same-file unique short names only — never invents cross-module /
``use`` / crate edges. Not Python/Go/Java-AST parity.
"""

from __future__ import annotations

import os
import pathlib
import re
from typing import Any

from ucli.analyzers.rust_ast_bridge import (
    ast_backend_available,
    run_rust_ast_worker,
    rust_analyzer_mode,
)

RUST_EXTENSIONS = frozenset({".rs"})

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
        "loop",
        "match",
        "return",
        "break",
        "continue",
        "fn",
        "let",
        "mut",
        "const",
        "static",
        "struct",
        "enum",
        "trait",
        "impl",
        "mod",
        "use",
        "pub",
        "crate",
        "super",
        "self",
        "Self",
        "where",
        "as",
        "in",
        "ref",
        "move",
        "async",
        "await",
        "dyn",
        "type",
        "unsafe",
        "extern",
        "true",
        "false",
        "Some",
        "None",
        "Ok",
        "Err",
        "vec",
        "println",
        "print",
        "format",
        "panic",
        "assert",
        "assert_eq",
        "assert_ne",
        "dbg",
        "todo",
        "unimplemented",
        "unreachable",
    }
)

# fn name<...>(  or  pub async fn name(
_RE_FN = re.compile(
    r"(?m)^[ \t]*(?:pub(?:\s*\([^)]*\))?\s+)?(?:async\s+)?(?:unsafe\s+)?(?:const\s+)?"
    r"fn\s+([A-Za-z_][\w]*)\s*(?:<[^>]*>)?\s*\(",
)
# impl [Trait for] Type {
_RE_IMPL = re.compile(
    r"(?m)^[ \t]*(?:pub\s+)?(?:unsafe\s+)?impl(?:\s*<[^>]*>)?\s+"
    r"(?:([A-Za-z_][\w:]*)\s+for\s+)?"
    r"([A-Za-z_][\w:]*)\s*(?:where\b[^{]*)?\{",
)
_RE_CALL = re.compile(r"(?<![.\w])([A-Za-z_][\w]*)\s*(?:::\s*[A-Za-z_][\w]*)*\s*\(")
_RE_COMPLEXITY = re.compile(r"\b(?:if|for|while|loop|match)\b|=>|\&\&|\|\||\?(?![?.])")


def _is_rust_file(path: pathlib.Path) -> bool:
    if path.suffix.lower() not in RUST_EXTENSIONS:
        return False
    return not any(part.startswith(".") for part in path.parts if part not in (".", ".."))


def _should_skip_dir(name: str) -> bool:
    return name in _SKIP_DIR_NAMES or name.startswith(".")


def _strip_comments_and_strings(src: str) -> str:
    """Strip // and /* */ comments and \"...\" strings (keep lifetimes like 'static)."""
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
        # Double-quoted strings only — do not treat 'lifetime / 'c' as strings here.
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
        # Take last path segment for Foo::bar( → bar; bare foo( → foo
        raw = m.group(0)
        name = m.group(1)
        if "::" in raw:
            # Prefer method/fn after ::
            parts = re.findall(r"[A-Za-z_][\w]*", raw)
            if parts:
                name = parts[-1]
        if name in _KEYWORD_CALLEES:
            continue
        calls.append(name)
    return list(dict.fromkeys(calls))


def _parse_rust_source(src: str, file_path: pathlib.Path) -> dict[str, Any]:
    cleaned = _strip_comments_and_strings(src)
    out: dict[str, Any] = {}

    def add(local: str, simple: str, body: str, line: int) -> None:
        out[local] = {
            "simple_name": simple,
            "file": file_path.as_posix(),
            "calls": _calls_in_body(body),
            "callers": [],
            "complexity": _complexity_heuristic(body),
            "line": line,
            "language": "rust",
            "analyzer": "rust-best-effort",
            "complexity_kind": "keyword-heuristic",
        }

    # Collect impl block ranges first so free-fn pass can skip them.
    impl_ranges: list[tuple[int, int, str]] = []
    for im in _RE_IMPL.finditer(cleaned):
        type_name = (im.group(2) or "").split("::")[-1]
        if not type_name:
            continue
        open_brace = cleaned.find("{", im.end() - 1)
        if open_brace < 0:
            continue
        end = _brace_block_end(cleaned, open_brace)
        impl_ranges.append((open_brace, end, type_name))

    def in_impl(idx: int) -> tuple[int, int, str] | None:
        for start, end, tname in impl_ranges:
            if start <= idx < end:
                return start, end, tname
        return None

    for m in _RE_FN.finditer(cleaned):
        name = m.group(1)
        open_brace = cleaned.find("{", m.end() - 1)
        if open_brace < 0:
            body, line = "", _line_of(src, m.start())
        else:
            end = _brace_block_end(cleaned, open_brace)
            body, line = cleaned[open_brace:end], _line_of(src, m.start())

        enclosing = in_impl(m.start())
        if enclosing is not None:
            _start, _end, type_name = enclosing
            local = f"{type_name}.{name}"
        else:
            local = name
        add(local, name, body, line)

    return out


def _parse_file(file_path: pathlib.Path) -> dict[str, Any]:
    try:
        src = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return {}
    try:
        return _parse_rust_source(src, file_path)
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


def _collect_rust_files(root: pathlib.Path) -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    if root.is_file():
        return [root] if _is_rust_file(root) else []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not _should_skip_dir(d)]
        for name in filenames:
            path = pathlib.Path(dirpath) / name
            if _is_rust_file(path):
                files.append(path)
    return files


def _build_regex_map(files: list[pathlib.Path]) -> dict[str, Any]:
    functions: dict[str, Any] = {}
    for file_path in files:
        parsed = _parse_file(file_path)
        for func, meta in parsed.items():
            key = f"{file_path.with_suffix('').as_posix()}:{func}"
            m = dict(meta)
            m["analyzer"] = "rust-best-effort"
            m["complexity_kind"] = "keyword-heuristic"
            functions[key] = m

    _attach_and_qualify_same_file(functions)
    return {
        "language": "rust",
        "functions": functions,
        "analyzer": "rust-best-effort",
        "analyzer_fidelity": "best-effort",
        "complexity_kind": "keyword-heuristic",
        "analyzer_note": (
            "Rust map via regex heuristics — not syn/rustc AST; complexity is "
            "keyword-based; call edges are same-file unique names only. No use/"
            "crate-path invent; not Python/Go/Java-AST parity. "
            "Set UF_RUST_ANALYZER=auto with cargo on PATH for rust-ast."
        ),
    }


def _build_ast_map(
    root: pathlib.Path,
    files: list[pathlib.Path],
    worker_payload: dict[str, Any],
) -> dict[str, Any]:
    functions: dict[str, Any] = {}
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

        locals_map = entry.get("functions") or {}
        for local, meta in locals_map.items():
            if not isinstance(meta, dict):
                continue
            qn = f"{stem}:{local}"
            m = dict(meta)
            m["file"] = display_file
            m["analyzer"] = "rust-ast"
            m["complexity_kind"] = "ast-cyclomatic"
            m["language"] = "rust"
            if m.get("calls") is None:
                m["calls"] = []
            m.setdefault("callers", [])
            m.setdefault("simple_name", local.rsplit(".", 1)[-1])
            functions[qn] = m

    _attach_and_qualify_same_file(functions)
    formula = worker_payload.get("complexity_formula") or (
        "1 + If/While/For/Loop/MatchArm/Question/&&/||; nested fn/closure excluded"
    )
    return {
        "language": "rust",
        "functions": functions,
        "analyzer": "rust-ast",
        "analyzer_fidelity": "ast",
        "complexity_kind": "ast-cyclomatic",
        "analyzer_note": (
            "Rust map via syn (parse only, not rustc typecheck). "
            f"Complexity is ast-cyclomatic: {formula}. "
            "Call edges: same-file unique names only (method calls use bare method "
            "name). No use/crate-path invent; not Python-parity. "
            "Falls back to rust-best-effort when cargo is unavailable."
        ),
    }


def build_rust_map(root: pathlib.Path) -> dict[str, Any]:
    """Build a Rust map for ``root`` (syn AST preferred, regex fallback)."""
    root = pathlib.Path(root)
    mode = rust_analyzer_mode()
    files = _collect_rust_files(root)
    scan_root = root if root.is_dir() else root.parent

    if mode != "regex":
        payload = run_rust_ast_worker(scan_root, files)
        if payload is not None:
            worker_files = payload.get("files") or []
            if worker_files or not files:
                return _build_ast_map(root, files, payload)
            if mode == "ast":
                raise RuntimeError("UF_RUST_ANALYZER=ast but worker returned no file results")
        elif mode == "ast":
            raise RuntimeError("UF_RUST_ANALYZER=ast but AST worker did not succeed")

    return _build_regex_map(files)


class RustAdapter:
    """Registry-facing adapter for Rust (syn AST preferred, regex fallback)."""

    language = "rust"
    extensions = RUST_EXTENSIONS
    fidelity = "ast"
    note = (
        "Prefers syn AST via cargo run worker (rust-ast, ast-cyclomatic); "
        "degrades to regex (rust-best-effort, keyword-heuristic) if cargo missing. "
        "Same-file call edges only. Not rustc typechecked / not Python-parity."
    )

    def build_map(self, root: pathlib.Path) -> dict[str, Any]:
        return build_rust_map(root)


def rust_ast_status() -> dict[str, Any]:
    return {
        "mode": rust_analyzer_mode(),
        "ast_available": ast_backend_available(),
    }
