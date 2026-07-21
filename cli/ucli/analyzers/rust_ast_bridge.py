"""Cargo subprocess bridge for the Rust syn AST worker (Wave 23).

Requires ``cargo`` on PATH and ``cli/ucli/analyzers/rust_ast``.
When unavailable, callers fall back to the regex adapter.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess  # nosec B404  # intentional: fixed argv [cargo, run, ...], no shell
from typing import Any

_RUST_AST_DIR = pathlib.Path(__file__).resolve().parent / "rust_ast"
_MANIFEST = _RUST_AST_DIR / "Cargo.toml"

_ENV_MODE = "UF_RUST_ANALYZER"
_ENV_TIMEOUT = "UF_RUST_AST_TIMEOUT"


def rust_analyzer_mode() -> str:
    raw = (os.environ.get(_ENV_MODE) or "auto").strip().lower()
    if raw in {"auto", "ast", "regex", "best-effort"}:
        return "regex" if raw == "best-effort" else raw
    return "auto"


def cargo_binary() -> str | None:
    return shutil.which("cargo")


def ast_backend_available() -> bool:
    return _MANIFEST.is_file() and cargo_binary() is not None


def ast_unavailable_reason() -> str:
    if not _MANIFEST.is_file():
        return f"Rust AST worker missing at {_MANIFEST}"
    if cargo_binary() is None:
        return "cargo not found on PATH (need Rust 1.70+)"
    return ""


def _timeout_seconds() -> float:
    raw = os.environ.get(_ENV_TIMEOUT) or "180"
    try:
        return max(30.0, float(raw))
    except ValueError:
        return 180.0


def run_rust_ast_worker(
    root: pathlib.Path,
    files: list[pathlib.Path],
) -> dict[str, Any] | None:
    """Run ``cargo run`` for the syn worker; return payload or None on soft failure."""
    if rust_analyzer_mode() == "regex":
        return None
    if not ast_backend_available():
        if rust_analyzer_mode() == "ast":
            raise RuntimeError(ast_unavailable_reason())
        return None

    cargo = cargo_binary()
    if cargo is None:
        return None

    root = root.resolve()
    rel_files: list[str] = []
    for f in files:
        fp = pathlib.Path(f)
        if not fp.is_absolute():
            cwd_cand = fp.resolve()
            root_cand = (root / fp).resolve()
            if cwd_cand.exists():
                fp = cwd_cand
            elif root_cand.exists():
                fp = root_cand
            else:
                fp = cwd_cand
        else:
            fp = fp.resolve()
        try:
            rel_files.append(fp.relative_to(root).as_posix())
        except ValueError:
            continue

    if not rel_files and files:
        if rust_analyzer_mode() == "ast":
            raise RuntimeError("Rust AST worker: no input files resolved under scan root")
        return None

    payload = json.dumps({"root": str(root), "files": rel_files})
    try:
        proc = subprocess.run(  # nosec B603  # fixed argv, no shell, trusted worker path
            [
                cargo,
                "run",
                "--quiet",
                "--manifest-path",
                str(_MANIFEST),
            ],
            input=payload,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_timeout_seconds(),
            check=False,
            cwd=str(_RUST_AST_DIR),
        )
    except (OSError, subprocess.TimeoutExpired):
        if rust_analyzer_mode() == "ast":
            raise
        return None

    if proc.returncode != 0:
        if rust_analyzer_mode() == "ast":
            err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
            raise RuntimeError(f"Rust AST worker failed: {err}")
        return None

    try:
        data = json.loads(proc.stdout or "")
    except json.JSONDecodeError as err:
        if rust_analyzer_mode() == "ast":
            raise RuntimeError("Rust AST worker returned invalid JSON") from err
        return None

    if not isinstance(data, dict) or not data.get("ok"):
        if rust_analyzer_mode() == "ast":
            detail = data.get("error") if isinstance(data, dict) else None
            raise RuntimeError(f"Rust AST worker reported failure: {detail or data}")
        return None

    return data
