"""Go toolchain subprocess bridge for the Go AST worker (Wave 19).

Requires ``go`` on PATH (1.21+) and ``cli/ucli/analyzers/go_ast/parse_worker.go``.
When unavailable, callers fall back to the regex adapter.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess  # nosec B404  # intentional: fixed argv [go, run, worker.go], no shell
from typing import Any

_GO_AST_DIR = pathlib.Path(__file__).resolve().parent / "go_ast"
_WORKER = _GO_AST_DIR / "parse_worker.go"

# UF_GO_ANALYZER: auto (default) | ast | regex
_ENV_MODE = "UF_GO_ANALYZER"
_ENV_TIMEOUT = "UF_GO_AST_TIMEOUT"


def go_analyzer_mode() -> str:
    raw = (os.environ.get(_ENV_MODE) or "auto").strip().lower()
    if raw in {"auto", "ast", "regex"}:
        return raw
    return "auto"


def go_binary() -> str | None:
    return shutil.which("go")


def ast_backend_available() -> bool:
    """True when ``go`` is on PATH and the worker source is present."""
    if not _WORKER.is_file():
        return False
    return go_binary() is not None


def ast_unavailable_reason() -> str:
    if not _WORKER.is_file():
        return f"AST worker missing at {_WORKER}"
    if go_binary() is None:
        return "Go toolchain not found on PATH (need go 1.21+)"
    return ""


def _timeout_seconds() -> float:
    raw = os.environ.get(_ENV_TIMEOUT) or "90"
    try:
        return max(10.0, float(raw))
    except ValueError:
        return 90.0


def run_go_ast_worker(
    root: pathlib.Path,
    files: list[pathlib.Path],
) -> dict[str, Any] | None:
    """Run the Go AST worker; return parsed payload or None on failure.

    Never raises for expected environment gaps — returns None so callers can
    degrade to the regex analyzer (unless ``UF_GO_ANALYZER=ast``).
    """
    if go_analyzer_mode() == "regex":
        return None
    if not ast_backend_available():
        if go_analyzer_mode() == "ast":
            raise RuntimeError(ast_unavailable_reason())
        return None

    go = go_binary()
    if go is None:
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
        if go_analyzer_mode() == "ast":
            raise RuntimeError("Go AST worker: no input files resolved under scan root")
        return None

    payload = json.dumps({"root": str(root), "files": rel_files})
    try:
        proc = subprocess.run(  # nosec B603  # fixed argv, no shell, trusted worker path
            [go, "run", str(_WORKER)],
            input=payload,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_timeout_seconds(),
            check=False,
            cwd=str(_GO_AST_DIR),
        )
    except (OSError, subprocess.TimeoutExpired):
        if go_analyzer_mode() == "ast":
            raise
        return None

    if proc.returncode != 0:
        if go_analyzer_mode() == "ast":
            err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
            raise RuntimeError(f"Go AST worker failed: {err}")
        return None

    try:
        data = json.loads(proc.stdout or "")
    except json.JSONDecodeError as err:
        if go_analyzer_mode() == "ast":
            raise RuntimeError("Go AST worker returned invalid JSON") from err
        return None

    if not isinstance(data, dict) or not data.get("ok"):
        if go_analyzer_mode() == "ast":
            raise RuntimeError(
                f"Go AST worker error: {data.get('error') if isinstance(data, dict) else data}"
            )
        return None
    return data
