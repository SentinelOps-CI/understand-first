"""Analyzer registry and multi-language ``build_repo_map`` dispatch."""

from __future__ import annotations

import os
import pathlib
from collections.abc import Iterable, Sequence
from typing import Any

from ucli.analyzers.base import LanguageAdapter
from ucli.analyzers.python_analyzer import build_python_map

# Extensions that look like source but have no adapter yet.
_UNSUPPORTED_SOURCE_EXTS = frozenset(
    {
        ".rb",
        ".php",
        ".kt",
        ".swift",
        ".c",
        ".cc",
        ".cpp",
        ".cxx",
        ".h",
        ".hpp",
        ".hh",
        ".scala",
        ".m",
        ".mm",
        ".lua",
        ".r",
        ".R",
        ".jl",
        ".zig",
        ".dart",
        ".vue",
        ".svelte",
    }
)

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


class PythonAdapter:
    """High-confidence Python AST adapter wrapping ``build_python_map``."""

    language = "python"
    extensions = frozenset({".py"})
    fidelity = "ast"
    note = (
        "Python AST maps with McCabe complexity and high-confidence call edges "
        "(ambiguous names omit rather than invent)."
    )

    def build_map(self, root: pathlib.Path) -> dict[str, Any]:
        return build_python_map(root)


_ADAPTERS: list[LanguageAdapter] = [
    PythonAdapter(),
]


def registered_adapters() -> list[LanguageAdapter]:
    return list(_ADAPTERS)


def adapter_for_extension(ext: str) -> LanguageAdapter | None:
    needle = ext.lower() if ext.startswith(".") else f".{ext.lower()}"
    for adapter in _ADAPTERS:
        if needle in adapter.extensions:
            return adapter
    return None


def supported_extensions() -> frozenset[str]:
    exts: set[str] = set()
    for adapter in _ADAPTERS:
        exts |= set(adapter.extensions)
    return frozenset(exts)


def supported_languages() -> list[str]:
    return [a.language for a in _ADAPTERS]


def _should_skip_dir(name: str) -> bool:
    return name in _SKIP_DIR_NAMES or (name.startswith(".") and name not in {".", ".."})


def _path_has_hidden_segment(path: pathlib.Path) -> bool:
    """Match Python analyzer: skip paths with any ``.``-prefixed segment."""
    return any(part.startswith(".") for part in path.parts)


def discover_source_inventory(
    root: pathlib.Path,
) -> tuple[dict[str, list[pathlib.Path]], dict[str, int]]:
    """Walk ``root``; bucket supported files by language; count unsupported by ext.

    Unsupported files are **not** passed to any analyzer (no empty fake maps).
    """
    by_lang: dict[str, list[pathlib.Path]] = {a.language: [] for a in _ADAPTERS}
    unsupported: dict[str, int] = {}

    if root.is_file():
        paths = [root]
    else:
        paths = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not _should_skip_dir(d)]
            for name in filenames:
                paths.append(pathlib.Path(dirpath) / name)

    for path in paths:
        if _path_has_hidden_segment(path):
            continue
        ext = path.suffix.lower()
        adapter = adapter_for_extension(ext)
        if adapter is not None:
            by_lang.setdefault(adapter.language, []).append(path)
        elif ext in _UNSUPPORTED_SOURCE_EXTS:
            key = ext.lstrip(".")
            unsupported[key] = unsupported.get(key, 0) + 1
    return by_lang, unsupported


def normalize_lang_filter(languages: Sequence[str] | None) -> set[str] | None:
    """Map user ``--lang`` tokens to registry language ids (``typescript`` ΓåÆ ``javascript``)."""
    if not languages:
        return None
    wanted: set[str] = set()
    aliases = {
        "js": "javascript",
        "ts": "javascript",  # TS handled by JS adapter
        "typescript": "javascript",
        "py": "python",
        "golang": "go",
        "c#": "csharp",
        "cs": "csharp",
        "csharp": "csharp",
    }
    for raw in languages:
        for part in str(raw).split(","):
            tok = part.strip().lower()
            if not tok:
                continue
            wanted.add(aliases.get(tok, tok))
    return wanted


def build_repo_map(
    root: pathlib.Path,
    *,
    languages: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Dispatch registered analyzers and merge into one repository map.

    Unsupported source files are counted under ``unsupported`` and never fed to
    the Python (or other) analyzer as empty stand-ins.
    """
    root = pathlib.Path(root)
    by_lang, unsupported = discover_source_inventory(root)
    lang_filter = normalize_lang_filter(languages)

    functions: dict[str, Any] = {}
    analyzed: list[str] = []
    fidelity: dict[str, str] = {}
    notes: dict[str, str] = {}
    files_analyzed = 0
    # Last single-adapter partial metadata (propagated when exactly one language ran).
    last_partial: dict[str, Any] | None = None

    for adapter in _ADAPTERS:
        if lang_filter is not None and adapter.language not in lang_filter:
            continue
        files = by_lang.get(adapter.language) or []
        if not files and lang_filter is None:
            # Still allow adapter walk (e.g. single-file roots); skip if inventory empty.
            continue
        if lang_filter is not None and not files:
            continue
        partial = adapter.build_map(root)
        funcs = partial.get("functions") or {}
        if not funcs and not files:
            continue
        functions.update(funcs)
        analyzed.append(adapter.language)
        # Prefer per-map fidelity when the adapter reports what actually ran
        # (JS AST vs regex fallback).
        partial_fid = partial.get("analyzer_fidelity")
        if isinstance(partial_fid, str) and partial_fid:
            fidelity[adapter.language] = partial_fid
        else:
            fidelity[adapter.language] = adapter.fidelity
        notes[adapter.language] = partial.get("analyzer_note") or adapter.note
        files_analyzed += len(files)
        last_partial = partial

    # Language label
    if len(analyzed) == 0:
        language = "none"
    elif len(analyzed) == 1:
        # Prefer typescript label when JS adapter says so and only that adapter ran.
        if analyzed[0] == "javascript":
            language = "javascript"
            # Re-check suffixes for typescript-only trees.
            js_files = by_lang.get("javascript") or []
            suffixes = {p.suffix.lower() for p in js_files}
            if suffixes and suffixes <= {".ts", ".tsx"}:
                language = "typescript"
            # Honor adapter language when it already distinguished typescript.
            if last_partial and last_partial.get("language") in {"javascript", "typescript"}:
                language = str(last_partial["language"])
        else:
            language = analyzed[0]
    else:
        language = "mixed"

    if analyzed == ["python"]:
        complexity_kind = "mccabe"
    elif analyzed == ["javascript"] and last_partial is not None:
        complexity_kind = str(last_partial.get("complexity_kind") or "keyword-heuristic")
    elif analyzed == ["go"] and last_partial is not None:
        complexity_kind = str(last_partial.get("complexity_kind") or "keyword-heuristic")
    elif analyzed == ["java"] and last_partial is not None:
        complexity_kind = str(last_partial.get("complexity_kind") or "keyword-heuristic")
    elif analyzed == ["rust"] and last_partial is not None:
        complexity_kind = str(last_partial.get("complexity_kind") or "keyword-heuristic")
    elif analyzed == ["csharp"] and last_partial is not None:
        complexity_kind = str(last_partial.get("complexity_kind") or "keyword-heuristic")
    elif analyzed:
        complexity_kind = "mixed"
    else:
        complexity_kind = "none"

    out: dict[str, Any] = {
        "language": language,
        "languages_analyzed": analyzed,
        "analyzer_fidelity": fidelity,
        "analyzer_notes": notes,
        "unsupported": unsupported,
        "files_analyzed": files_analyzed,
        "functions": functions,
        "complexity_kind": complexity_kind,
    }
    # Single-adapter maps: surface honest analyzer id (e.g. javascript-best-effort).
    if len(analyzed) == 1 and last_partial is not None:
        if "analyzer" in last_partial:
            out["analyzer"] = last_partial["analyzer"]
        elif analyzed[0] == "python":
            out["analyzer"] = "python-ast"
        if "analyzer_note" in last_partial:
            out["analyzer_note"] = last_partial["analyzer_note"]
    return out


def format_unsupported_summary(unsupported: dict[str, int]) -> str:
    if not unsupported:
        return ""
    parts = [f".{ext}├ù{count}" for ext, count in sorted(unsupported.items())]
    return (
        "Not analyzed (no adapter): "
        + ", ".join(parts)
        + ". These files were skipped ΓÇö not scanned as Python or empty maps."
    )


def iter_adapter_notes() -> Iterable[tuple[str, str, str]]:
    for a in _ADAPTERS:
        yield a.language, a.fidelity, a.note
