"""Runtime call tracing and static error analysis.

Security note
-------------
``run_callable_with_trace`` intentionally executes user Python in an **isolated
subprocess** (never ``exec_module`` in the CLI process). Residual risk: the
child still runs arbitrary target code — that is required for runtime tracing.
Prefer ``analyze_errors_static`` (AST-only) when execution is not needed.

Hardening:
  * Target path must resolve under an allowlisted root (cwd by default, plus
    ``UF_TRACE_ALLOW_ROOTS`` pathsep-separated dirs). Symlinks that escape the
    allowlist are refused after ``resolve()``.
  * ``func_name`` must be a simple Python identifier; a denylist blocks
    high-risk builtins (``eval``, ``exec``, ``__import__``, …).
  * Worker applies soft CPU/address limits on POSIX when ``resource`` is
    available. On Windows, best-effort Job Object memory limit via ctypes
    (see residual risks in ``docs/SECURITY.md``).
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess  # nosec B404  # intentional: isolated trace worker, fixed argv, no shell
import sys
import tempfile
from pathlib import Path
from typing import Any

# Worker script executed in a subprocess. Kept as a string so the parent module
# never imports/executes the target file in-process.
_WORKER = r"""
import importlib.util
import json
import sys
import time

def _apply_limits():
    try:
        import resource
    except ImportError:
        return
    # Soft caps only — demo/trace workloads should stay small.
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    except (ValueError, OSError):
        pass
    try:
        # ~512 MiB address space
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    except (ValueError, OSError, AttributeError):
        pass

def _coerce(x):
    if x is None:
        return None
    try:
        return int(x)
    except (TypeError, ValueError):
        return x

def main():
    _apply_limits()
    pyfile, func_name = sys.argv[1], sys.argv[2]
    a = sys.argv[3] if len(sys.argv) > 3 else None
    b = sys.argv[4] if len(sys.argv) > 4 else None
    if a == "":
        a = None
    if b == "":
        b = None

    spec = importlib.util.spec_from_file_location("_uf_trace_mod", pyfile)
    if spec is None or spec.loader is None:
        print(json.dumps({"error": "could not load module", "events": []}))
        return 1
    mod = importlib.util.module_from_spec(spec)
    # INTENTIONAL: execute user module only inside this subprocess worker.
    spec.loader.exec_module(mod)
    target = getattr(mod, func_name, None)
    if target is None or not callable(target):
        print(json.dumps({"error": f"callable not found: {func_name}", "events": []}))
        return 1

    events = []
    start = time.time()

    def tracer(frame, event, arg):
        if event == "call":
            code = frame.f_code
            events.append({
                "type": "call",
                "func": code.co_name,
                "file": code.co_filename,
            })
        return tracer

    sys.setprofile(tracer)
    try:
        if a is None and b is None:
            target()
        elif b is None:
            target(_coerce(a))
        else:
            target(_coerce(a), _coerce(b))
    except Exception as exc:
        sys.setprofile(None)
        print(json.dumps({
            "error": f"{type(exc).__name__}: {exc}",
            "events": events,
            "duration_sec": time.time() - start,
        }))
        return 1
    finally:
        sys.setprofile(None)

    print(json.dumps({"events": events, "duration_sec": time.time() - start}))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
"""

# Top-level getattr targets that must never be invoked via `u trace module`.
_FUNC_DENYLIST = frozenset(
    {
        "eval",
        "exec",
        "compile",
        "__import__",
        "breakpoint",
        "input",
        "exit",
        "quit",
        "help",
        "memoryview",
        "open",
    }
)
_FUNC_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _allow_roots() -> list[Path]:
    roots = [Path.cwd()]
    extra = os.environ.get("UF_TRACE_ALLOW_ROOTS", "")
    if extra:
        for part in extra.split(os.pathsep):
            part = part.strip()
            if part:
                roots.append(Path(part))
    return roots


def _path_is_allowed(target: Path, roots: list[Path] | None = None) -> bool:
    """True when ``target`` resolves under at least one allowlisted root."""
    try:
        resolved = target.resolve()
    except OSError:
        return False
    # Refuse non-.py targets after resolve (covers symlink renames).
    if resolved.suffix.lower() != ".py":
        return False
    for root in roots or _allow_roots():
        try:
            root_res = root.resolve()
        except OSError:
            continue
        try:
            resolved.relative_to(root_res)
            return True
        except ValueError:
            continue
    return False


def _validate_func_name(func_name: str) -> str | None:
    """Return an error message if ``func_name`` is unsafe; else None."""
    if not func_name or not _FUNC_NAME_RE.match(func_name):
        return (
            "trace refused: func must be a simple Python identifier (top-level callable name only)"
        )
    if func_name in _FUNC_DENYLIST or func_name.startswith("__"):
        return f"trace refused: callable '{func_name}' is denylisted"
    return None


def _windows_assign_job_memory_limit(
    proc: subprocess.Popen, limit_bytes: int = 512 * 1024 * 1024
) -> None:
    """Best-effort Windows Job Object memory cap for the trace child process.

    Failures are silent — tracing still proceeds with timeout-only containment.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes
        from ctypes import wintypes
    except ImportError:
        return

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    JobObjectExtendedLimitInformation = 9
    JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100

    class IO_COUNTERS(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount", ctypes.c_uint64),
            ("WriteTransferCount", ctypes.c_uint64),
            ("OtherTransferCount", ctypes.c_uint64),
        ]

    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.c_size_t),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
            ("IoInfo", IO_COUNTERS),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    handle = None
    try:
        handle = kernel32.CreateJobObjectW(None, None)
        if not handle:
            return
        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_PROCESS_MEMORY
        info.ProcessMemoryLimit = limit_bytes
        ok = kernel32.SetInformationJobObject(
            handle,
            JobObjectExtendedLimitInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        if not ok:
            return
        # PROCESS_SET_QUOTA | PROCESS_TERMINATE
        PROCESS_SET_QUOTA = 0x0100
        PROCESS_TERMINATE = 0x0001
        proc_handle = kernel32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, proc.pid)
        if not proc_handle:
            return
        try:
            kernel32.AssignProcessToJobObject(handle, proc_handle)
        finally:
            kernel32.CloseHandle(proc_handle)
        # Keep job handle alive until process exits by attaching to Popen.
        proc._uf_job_handle = handle  # type: ignore[attr-defined]
        handle = None
    except (OSError, AttributeError, ValueError, TypeError):
        return
    finally:
        if handle:
            try:
                kernel32.CloseHandle(handle)
            except OSError:
                pass


def run_callable_with_trace(pyfile: str, func_name: str, a=None, b=None) -> dict[str, Any]:
    """Run ``func_name`` from ``pyfile`` under a profile tracer in a subprocess."""
    deny = _validate_func_name(func_name)
    if deny:
        return {"error": deny, "events": []}

    target = Path(pyfile)
    if not target.is_file():
        return {"error": f"file not found: {pyfile}", "events": []}
    if "\x00" in pyfile:
        return {"error": "trace refused: path contains NUL", "events": []}
    if not _path_is_allowed(target):
        return {
            "error": (
                f"trace refused: {pyfile} is outside allowlisted roots "
                "(cwd and UF_TRACE_ALLOW_ROOTS) or is not a .py file"
            ),
            "events": [],
        }

    with tempfile.TemporaryDirectory(prefix="uf-trace-") as tmp:
        worker = Path(tmp) / "_uf_trace_worker.py"
        worker.write_text(_WORKER, encoding="utf-8")
        cmd = [
            sys.executable,
            str(worker),
            str(target.resolve()),
            func_name,
            "" if a is None else str(a),
            "" if b is None else str(b),
        ]
        try:
            proc = subprocess.Popen(  # nosec B603
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            _windows_assign_job_memory_limit(proc)
            try:
                stdout, stderr = proc.communicate(timeout=60)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
                return {"error": "trace subprocess timed out (60s)", "events": []}
        except OSError as exc:
            return {"error": f"trace subprocess failed to start: {exc}", "events": []}

    stdout = (stdout or "").strip()
    if not stdout:
        err = (stderr or "").strip() or f"exit {proc.returncode}"
        return {"error": f"trace subprocess produced no output: {err}", "events": []}

    # Worker prints one JSON object on the last non-empty line.
    last = stdout.splitlines()[-1]
    try:
        data = json.loads(last)
    except json.JSONDecodeError:
        return {
            "error": "trace subprocess returned invalid JSON",
            "events": [],
            "stderr": (stderr or "")[:500],
        }
    if not isinstance(data, dict):
        return {"error": "trace subprocess returned non-object JSON", "events": []}
    return data


def analyze_errors_static(pyfile: str) -> dict[str, Any]:
    src = open(pyfile, encoding="utf-8", errors="ignore").read()
    tree = ast.parse(src)
    raises: list[dict[str, Any]] = []
    try_catches: list[dict[str, Any]] = []

    class V(ast.NodeVisitor):
        def visit_Raise(self, node: ast.Raise):
            name = (
                getattr(getattr(node.exc, "func", None), "id", None)
                or getattr(getattr(node.exc, "func", None), "attr", None)
                or getattr(getattr(node.exc, "id", None), "id", None)
            )
            raises.append({"line": getattr(node, "lineno", 0), "exc": name or "Exception"})
            self.generic_visit(node)

        def visit_Try(self, node: ast.Try):
            for h in node.handlers:
                et = getattr(h.type, "id", None) if h.type is not None else "Exception"
                try_catches.append({"line": getattr(h, "lineno", 0), "catch": et or "Exception"})
            self.generic_visit(node)

    V().visit(tree)
    return {"raises": raises, "catches": try_catches}
