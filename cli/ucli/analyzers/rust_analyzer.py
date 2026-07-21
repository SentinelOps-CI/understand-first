"""Rust analyzer (Wave 22–26).

Preferred path (Wave 23): ``cargo run`` + ``syn`` worker → ``rust-ast``,
``ast-cyclomatic``. Requires cargo on PATH.

Fallback (Wave 22): conservative regex → ``rust-best-effort``,
``keyword-heuristic``. Override with ``UF_RUST_ANALYZER=regex|ast|auto``.

Call edges (Wave 26): same-file unique short names, plus invent-free
cross-module edges when ``mod`` / ``use`` evidence uniquely resolves a
target inside the scanned tree. Ambiguous names are omitted (left bare).
Not rustc typechecked / not Python-parity.
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
# Top-level mod name;  / mod name {
_RE_MOD = re.compile(
    r"(?m)^[ \t]*(?:pub(?:\s*\([^)]*\))?\s+)?mod\s+([A-Za-z_][\w]*)\s*[;{]",
)
_RE_USE = re.compile(
    r"(?m)^[ \t]*(?:pub(?:\s*\([^)]*\))?\s+)?use\s+([^;]+);",
)


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
        raw = m.group(0)
        name = m.group(1)
        if "::" in raw:
            parts = re.findall(r"[A-Za-z_][\w]*", raw)
            if parts:
                # Preserve mod::fn paths for Wave 26; same-file uses last segment.
                name = "::".join(parts) if len(parts) > 1 else parts[-1]
        if name in _KEYWORD_CALLEES or name.rsplit("::", 1)[-1] in _KEYWORD_CALLEES:
            continue
        calls.append(name)
    return list(dict.fromkeys(calls))


def _parse_use_bindings(use_body: str) -> list[dict[str, Any]]:
    """Flatten a ``use`` path body into invent-free bindings (globs omitted)."""
    body = use_body.strip()
    if not body or "*" in body:
        return []
    # Drop leading crate/super/self path roots for module matching.
    body = re.sub(r"^(?:crate|super|self)\s*::\s*", "", body)

    bindings: list[dict[str, Any]] = []

    def walk(prefix: list[str], fragment: str) -> None:
        fragment = fragment.strip()
        if not fragment or "*" in fragment:
            return
        if fragment.startswith("{"):
            close = fragment.rfind("}")
            if close < 0:
                return
            inner = fragment[1:close]
            depth = 0
            start = 0
            for i, ch in enumerate(inner):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                elif ch == "," and depth == 0:
                    walk(prefix, inner[start:i])
                    start = i + 1
            walk(prefix, inner[start:])
            return
        if "::" in fragment:
            head, rest = fragment.split("::", 1)
            head = head.strip()
            if not head:
                return
            walk([*prefix, head], rest)
            return
        # Terminal: name or name as alias
        as_match = re.match(
            r"^([A-Za-z_][\w]*)\s+as\s+([A-Za-z_][\w]*)$",
            fragment.strip(),
        )
        if as_match:
            bindings.append(
                {
                    "name": as_match.group(2),
                    "imported": as_match.group(1),
                    "module": list(prefix),
                }
            )
            return
        name = fragment.strip()
        if not re.match(r"^[A-Za-z_][\w]*$", name):
            return
        if name == "self" and prefix:
            bindings.append(
                {"name": prefix[-1], "imported": prefix[-1], "module": prefix[:-1]}
            )
            return
        bindings.append({"name": name, "imported": name, "module": list(prefix)})

    walk([], body)
    return bindings


def _extract_file_mod_use(cleaned: str) -> tuple[list[str], list[dict[str, Any]]]:
    mods = list(dict.fromkeys(m.group(1) for m in _RE_MOD.finditer(cleaned)))
    uses: list[dict[str, Any]] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for m in _RE_USE.finditer(cleaned):
        for binding in _parse_use_bindings(m.group(1)):
            key = (binding["name"], tuple(binding["module"]))
            if key in seen:
                continue
            seen.add(key)
            uses.append(binding)
    return mods, uses


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


def _parse_file(
    file_path: pathlib.Path,
) -> tuple[dict[str, Any], list[str], list[dict[str, Any]]]:
    try:
        src = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return {}, [], []
    try:
        cleaned = _strip_comments_and_strings(src)
        mods, uses = _extract_file_mod_use(cleaned)
        return _parse_rust_source(src, file_path), mods, uses
    except Exception:
        return {}, [], []


def _module_name_for_file(file_posix: str) -> str:
    p = pathlib.PurePosixPath(file_posix)
    if p.name == "mod.rs":
        return p.parent.name
    return p.stem


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


def _pick_unique(candidates: list[str], token: str, caller_qn: str) -> str | None:
    uniq = list(dict.fromkeys(candidates))
    exact = [c for c in uniq if c.rsplit(":", 1)[-1] == token]
    pick = exact if len(exact) == 1 else (uniq if len(uniq) == 1 else [])
    if len(pick) == 1 and pick[0] != caller_qn:
        return pick[0]
    return None


def _attach_and_qualify_same_file(functions: dict[str, Any]) -> None:
    by_file_short = _build_file_indexes(functions)
    for caller_qn, meta in functions.items():
        caller_file = meta.get("file", "")
        local_map = by_file_short.get(caller_file, {})
        qualified: list[str] = []
        for token in meta.get("calls") or []:
            if ":" in token and "::" not in token:
                # Already a qname (file:local)
                qualified.append(token)
                continue
            if "." in token and ":" not in token and "::" not in token:
                qualified.append(token)
                continue
            # Path tokens (mod::fn) do not invent same-file Type::method edges.
            if "::" in token:
                qualified.append(token)
                continue
            candidates = list(dict.fromkeys(local_map.get(token, [])))
            picked = _pick_unique(candidates, token, caller_qn)
            if picked is not None:
                qualified.append(picked)
                functions[picked].setdefault("callers", []).append(caller_qn)
            else:
                qualified.append(token)
        meta["calls"] = list(dict.fromkeys(qualified))
    for meta in functions.values():
        meta["callers"] = sorted(set(meta.get("callers") or []))


def _index_files_by_module_stem(
    file_paths: list[str],
) -> dict[str, list[str]]:
    by_stem: dict[str, list[str]] = {}
    for fp in file_paths:
        stem = _module_name_for_file(fp)
        if stem in {"lib", "main"}:
            continue
        by_stem.setdefault(stem, []).append(fp)
    return by_stem


def _resolve_mod_target_file(
    caller_file: str,
    mod_name: str,
    by_stem: dict[str, list[str]],
) -> str | None:
    """Map ``mod name`` to a unique scanned ``name.rs`` / ``name/mod.rs``."""
    candidates = list(dict.fromkeys(by_stem.get(mod_name, [])))
    if not candidates:
        return None
    parent = str(pathlib.PurePosixPath(caller_file).parent)
    preferred = [
        c
        for c in candidates
        if pathlib.PurePosixPath(c).parent.as_posix() == parent
        or (
            pathlib.PurePosixPath(c).name == "mod.rs"
            and pathlib.PurePosixPath(c).parent.name == mod_name
            and pathlib.PurePosixPath(c).parent.parent.as_posix() == parent
        )
    ]
    pool = preferred if preferred else candidates
    if len(pool) == 1:
        return pool[0]
    return None


def _attach_cross_module_edges(
    functions: dict[str, Any],
    file_mods: dict[str, list[str]],
    file_uses: dict[str, list[dict[str, Any]]],
) -> None:
    """Qualify remaining bare / path calls via unique mod/use targets (fail closed)."""
    by_file_short = _build_file_indexes(functions)
    all_files = sorted({meta.get("file", "") for meta in functions.values() if meta.get("file")})
    by_stem = _index_files_by_module_stem(all_files)

    # Precompute child-module file → functions available via caller's `mod` decls.
    child_files_by_caller: dict[str, set[str]] = {}
    for caller_file, mods in file_mods.items():
        kids: set[str] = set()
        for mod_name in mods:
            target = _resolve_mod_target_file(caller_file, mod_name, by_stem)
            if target:
                kids.add(target)
        child_files_by_caller[caller_file] = kids

    for caller_qn, meta in functions.items():
        caller_file = meta.get("file", "")
        uses = file_uses.get(caller_file) or []
        use_by_name: dict[str, list[dict[str, Any]]] = {}
        for u in uses:
            use_by_name.setdefault(u["name"], []).append(u)

        new_calls: list[str] = []
        for token in meta.get("calls") or []:
            # Already qualified qname
            if ":" in token and "::" not in token:
                new_calls.append(token)
                continue

            resolved: str | None = None

            if "::" in token:
                parts = [p for p in token.split("::") if p]
                if len(parts) >= 2:
                    mod_segs, simple = parts[:-1], parts[-1]
                    while mod_segs and mod_segs[0] in {"crate", "super", "self"}:
                        mod_segs = mod_segs[1:]
                    if mod_segs:
                        mod_name = mod_segs[-1]
                        declared = mod_name in (file_mods.get(caller_file) or [])
                        use_mentions = any(
                            mod_name in (u.get("module") or []) or u.get("name") == mod_name
                            for u in uses
                        )
                        if declared or use_mentions:
                            target_file = _resolve_mod_target_file(
                                caller_file, mod_name, by_stem
                            )
                            if target_file:
                                local_map = by_file_short.get(target_file, {})
                                candidates = list(
                                    dict.fromkeys(local_map.get(simple, []))
                                )
                                resolved = _pick_unique(candidates, simple, caller_qn)

            if resolved is None and "::" not in token:
                # use-gated bare name
                bindings = use_by_name.get(token) or []
                if len(bindings) == 1:
                    binding = bindings[0]
                    imported = str(binding.get("imported") or token)
                    module = list(binding.get("module") or [])
                    while module and module[0] in {"crate", "super", "self"}:
                        module = module[1:]
                    if module:
                        mod_name = module[-1]
                        target_file = _resolve_mod_target_file(
                            caller_file, mod_name, by_stem
                        )
                        if target_file:
                            local_map = by_file_short.get(target_file, {})
                            candidates = list(
                                dict.fromkeys(local_map.get(imported, []))
                            )
                            resolved = _pick_unique(
                                candidates, imported, caller_qn
                            )
                elif not bindings:
                    # Unique among child modules declared via `mod` only.
                    kids = child_files_by_caller.get(caller_file) or set()
                    if kids:
                        candidates = []
                        for kid in kids:
                            candidates.extend(by_file_short.get(kid, {}).get(token, []))
                        resolved = _pick_unique(candidates, token, caller_qn)

            if resolved is not None:
                new_calls.append(resolved)
                functions[resolved].setdefault("callers", []).append(caller_qn)
            else:
                new_calls.append(token)
        meta["calls"] = list(dict.fromkeys(new_calls))
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
    file_mods: dict[str, list[str]] = {}
    file_uses: dict[str, list[dict[str, Any]]] = {}

    for file_path in files:
        parsed, mods, uses = _parse_file(file_path)
        display = file_path.as_posix()
        file_mods[display] = mods
        file_uses[display] = uses
        for func, meta in parsed.items():
            key = f"{file_path.with_suffix('').as_posix()}:{func}"
            m = dict(meta)
            m["analyzer"] = "rust-best-effort"
            m["complexity_kind"] = "keyword-heuristic"
            functions[key] = m

    _attach_and_qualify_same_file(functions)
    _attach_cross_module_edges(functions, file_mods, file_uses)
    return {
        "language": "rust",
        "functions": functions,
        "analyzer": "rust-best-effort",
        "analyzer_fidelity": "best-effort",
        "complexity_kind": "keyword-heuristic",
        "analyzer_note": (
            "Rust map via regex heuristics — not syn/rustc AST; complexity is "
            "keyword-based; call edges are same-file unique names, plus invent-free "
            "cross-module edges when mod/use uniquely resolves a scanned target. "
            "Ambiguous or unproven edges stay bare. Not Python-parity. "
            "Set UF_RUST_ANALYZER=auto with cargo on PATH for rust-ast."
        ),
    }


def _normalize_worker_uses(raw_uses: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(raw_uses, list):
        return out
    for item in raw_uses:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        imported = str(item.get("imported") or name).strip() or name
        module_raw = item.get("module") or []
        module = [str(x) for x in module_raw] if isinstance(module_raw, list) else []
        out.append({"name": name, "imported": imported, "module": module})
    return out


def _build_ast_map(
    root: pathlib.Path,
    files: list[pathlib.Path],
    worker_payload: dict[str, Any],
) -> dict[str, Any]:
    functions: dict[str, Any] = {}
    file_mods: dict[str, list[str]] = {}
    file_uses: dict[str, list[dict[str, Any]]] = {}
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

        mods_raw = entry.get("mods") or []
        file_mods[display_file] = (
            [str(m) for m in mods_raw] if isinstance(mods_raw, list) else []
        )
        file_uses[display_file] = _normalize_worker_uses(entry.get("uses"))

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
    _attach_cross_module_edges(functions, file_mods, file_uses)
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
            "Call edges: same-file unique names, plus invent-free cross-module "
            "edges when mod/use uniquely resolves a scanned target. "
            "Ambiguous edges omitted; not Python-parity. "
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
        "Same-file + invent-free mod/use cross-module unique call edges. "
        "Not rustc typechecked / not Python-parity."
    )

    def build_map(self, root: pathlib.Path) -> dict[str, Any]:
        return build_rust_map(root)


def rust_ast_status() -> dict[str, Any]:
    return {
        "mode": rust_analyzer_mode(),
        "ast_available": ast_backend_available(),
    }
