"""Dotnet subprocess bridge for the C# Roslyn AST worker (Wave 24).

Requires ``dotnet`` (SDK) on PATH and ``cli/ucli/analyzers/csharp_ast``.
When unavailable, callers fall back to the regex adapter.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess  # nosec B404  # intentional: fixed argv [dotnet, run, ...], no shell
from typing import Any

_CSHARP_AST_DIR = pathlib.Path(__file__).resolve().parent / "csharp_ast"
_PROJECT = _CSHARP_AST_DIR / "UfCsharpAst.csproj"

_ENV_MODE = "UF_CSHARP_ANALYZER"
_ENV_TIMEOUT = "UF_CSHARP_AST_TIMEOUT"


def csharp_analyzer_mode() -> str:
    raw = (os.environ.get(_ENV_MODE) or "auto").strip().lower()
    if raw in {"auto", "ast", "regex", "best-effort"}:
        return "regex" if raw == "best-effort" else raw
    return "auto"


def dotnet_binary() -> str | None:
    return shutil.which("dotnet")


def _dotnet_sdk_available(dotnet: str) -> bool:
    """Return True when ``dotnet --list-sdks`` reports at least one SDK."""
    try:
        proc = subprocess.run(  # nosec B603  # fixed argv, no shell
            [dotnet, "--list-sdks"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15.0,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    if proc.returncode != 0:
        return False
    return bool((proc.stdout or "").strip())


def ast_backend_available() -> bool:
    if not _PROJECT.is_file():
        return False
    dotnet = dotnet_binary()
    if dotnet is None:
        return False
    return _dotnet_sdk_available(dotnet)


def ast_unavailable_reason() -> str:
    if not _PROJECT.is_file():
        return f"C# AST worker missing at {_PROJECT}"
    if dotnet_binary() is None:
        return "dotnet not found on PATH (need .NET SDK 8+)"
    if not _dotnet_sdk_available(dotnet_binary() or "dotnet"):
        return "dotnet found but no SDK installed (runtime-only is not enough for csharp-ast)"
    return ""


def _timeout_seconds() -> float:
    raw = os.environ.get(_ENV_TIMEOUT) or "180"
    try:
        return max(30.0, float(raw))
    except ValueError:
        return 180.0


def run_csharp_ast_worker(
    root: pathlib.Path,
    files: list[pathlib.Path],
) -> dict[str, Any] | None:
    """Run ``dotnet run`` for the Roslyn worker; return payload or None on soft failure."""
    if csharp_analyzer_mode() == "regex":
        return None
    if not ast_backend_available():
        if csharp_analyzer_mode() == "ast":
            raise RuntimeError(ast_unavailable_reason())
        return None

    dotnet = dotnet_binary()
    if dotnet is None:
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
        if csharp_analyzer_mode() == "ast":
            raise RuntimeError("C# AST worker: no input files resolved under scan root")
        return None

    payload = json.dumps({"root": str(root), "files": rel_files})
    env = os.environ.copy()
    env.setdefault("DOTNET_NOLOGO", "1")
    env.setdefault("DOTNET_CLI_TELEMETRY_OPTOUT", "1")
    env.setdefault("MSBUILDTERMINALLOGGER", "off")
    try:
        proc = subprocess.run(  # nosec B603  # fixed argv, no shell, trusted worker path
            [
                dotnet,
                "run",
                "--project",
                str(_PROJECT),
                "--verbosity",
                "minimal",
            ],
            input=payload,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_timeout_seconds(),
            check=False,
            cwd=str(_CSHARP_AST_DIR),
            env=env,
        )
    except (OSError, subprocess.TimeoutExpired):
        if csharp_analyzer_mode() == "ast":
            raise
        return None

    if proc.returncode != 0:
        if csharp_analyzer_mode() == "ast":
            err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
            # Prefer the last lines — MSBuild banners are noisy; real errors trail.
            if len(err) > 2000:
                err = err[-2000:]
            raise RuntimeError(f"C# AST worker failed: {err}")
        return None

    stdout = (proc.stdout or "").strip()
    # MSBuild may prepend banners; extract the JSON object.
    if stdout and not stdout.startswith("{"):
        start = stdout.find("{")
        end = stdout.rfind("}")
        if start >= 0 and end > start:
            stdout = stdout[start : end + 1]

    try:
        data = json.loads(stdout or "")
    except json.JSONDecodeError as err:
        if csharp_analyzer_mode() == "ast":
            raise RuntimeError("C# AST worker returned invalid JSON") from err
        return None

    if not isinstance(data, dict) or not data.get("ok"):
        if csharp_analyzer_mode() == "ast":
            detail = data.get("error") if isinstance(data, dict) else None
            raise RuntimeError(f"C# AST worker reported failure: {detail or data}")
        return None

    return data
