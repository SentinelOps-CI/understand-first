"""Node subprocess bridge for the JS/TS AST worker (Wave 17).

Requires Node 18+ and ``npm install`` in ``cli/ucli/analyzers/js_ast``
(typescript package). When unavailable, callers fall back to the regex adapter.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess  # nosec B404  # intentional: fixed argv [node, worker.mjs], no shell
from typing import Any

_WORKER = pathlib.Path(__file__).resolve().parent / "js_ast" / "parse_worker.mjs"
_JS_AST_DIR = _WORKER.parent

# UF_JS_ANALYZER: auto (default) | ast | regex
_ENV_MODE = "UF_JS_ANALYZER"
_ENV_TIMEOUT = "UF_JS_AST_TIMEOUT"


def js_analyzer_mode() -> str:
    raw = (os.environ.get(_ENV_MODE) or "auto").strip().lower()
    if raw in {"auto", "ast", "regex"}:
        return raw
    return "auto"


def node_binary() -> str | None:
    return shutil.which("node")


def typescript_install_present() -> bool:
    return (_JS_AST_DIR / "node_modules" / "typescript").is_dir()


def ast_backend_available() -> bool:
    """True when Node is on PATH and the worker's typescript dep is installed."""
    if not _WORKER.is_file():
        return False
    if node_binary() is None:
        return False
    return typescript_install_present()


def ast_unavailable_reason() -> str:
    if not _WORKER.is_file():
        return f"AST worker missing at {_WORKER}"
    if node_binary() is None:
        return "Node.js not found on PATH (need Node 18+)"
    if not typescript_install_present():
        return (
            "typescript not installed for AST worker; run "
            "`npm install` in cli/ucli/analyzers/js_ast"
        )
    return ""


def _timeout_seconds() -> float:
    raw = os.environ.get(_ENV_TIMEOUT) or "60"
    try:
        return max(5.0, float(raw))
    except ValueError:
        return 60.0


def run_js_ast_worker(
    root: pathlib.Path,
    files: list[pathlib.Path],
) -> dict[str, Any] | None:
    """Run the Node AST worker; return parsed payload or None on failure.

    Never raises for expected environment gaps — returns None so callers can
    degrade to the regex analyzer.
    """
    if js_analyzer_mode() == "regex":
        return None
    if not ast_backend_available():
        if js_analyzer_mode() == "ast":
            raise RuntimeError(ast_unavailable_reason())
        return None

    node = node_binary()
    if node is None:
        return None

    root = root.resolve()
    rel_files: list[str] = []
    for f in files:
        # Walk paths are typically cwd-relative (e.g. examples/js_toy/math.js).
        # Resolve from cwd first — do NOT join onto root (that double-prefixes).
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
            # Outside scan root — skip rather than invent absolute keys.
            continue

    if not rel_files and files:
        # Nothing resolvable under root → treat as worker miss for fallback.
        if js_analyzer_mode() == "ast":
            raise RuntimeError("JS AST worker: no input files resolved under scan root")
        return None

    payload = json.dumps({"root": str(root), "files": rel_files})
    try:
        proc = subprocess.run(  # nosec B603  # fixed argv, no shell, trusted worker path
            [node, str(_WORKER)],
            input=payload,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_timeout_seconds(),
            check=False,
            cwd=str(_JS_AST_DIR),
        )
    except (OSError, subprocess.TimeoutExpired):
        if js_analyzer_mode() == "ast":
            raise
        return None

    if proc.returncode != 0:
        if js_analyzer_mode() == "ast":
            err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
            raise RuntimeError(f"JS AST worker failed: {err}")
        return None

    try:
        data = json.loads(proc.stdout or "")
    except json.JSONDecodeError as err:
        if js_analyzer_mode() == "ast":
            raise RuntimeError("JS AST worker returned invalid JSON") from err
        return None

    if not isinstance(data, dict) or not data.get("ok"):
        if js_analyzer_mode() == "ast":
            raise RuntimeError(
                f"JS AST worker error: {data.get('error') if isinstance(data, dict) else data}"
            )
        return None
    return data
