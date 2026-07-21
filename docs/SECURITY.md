# Security Policy

We value responsible disclosure and the safety of our users.

## Reporting a Vulnerability
- Email the maintainers using the contact in this repository’s metadata or open a private, security‑labeled issue if available.
- Provide a detailed description, steps to reproduce, and affected versions.
- Do not create public issues or pull requests that include exploit details.

We will acknowledge reports within 72 hours and provide a timeline for remediation when possible.

## Disclosure
- Please do not disclose the issue publicly until a fix is available and users have had a reasonable time to update.
- Coordinated disclosure is appreciated.

## Supported Versions
This is an active repository; we support the latest `main` branch and the most recent tagged release. Security fixes may be backported at the maintainers’ discretion.

The Python package targets the interpreter range in `requires-python` (see the root `pyproject.toml`). Prefer installing with pinned dependencies (`uv.lock` / `uv sync --frozen`) or the exported `requirements.txt` when deploying.

## Bandit baseline (CLI)

CI runs Bandit fail-closed: any **HIGH** finding fails the job, and any finding not present in the committed `.bandit-baseline.json` also fails (new LOW/MEDIUM drift).

### Intentional `subprocess` (B404 / B603)

The CLI uses `subprocess` in fixed-argv, no-shell helpers:

| Location | Why |
| --- | --- |
| `cli/ucli/commands/tour_ops.py` | `tour_run` fixture execution |
| `cli/ucli/commands/doctor_ops.py` | Doctor environment probes (`node -v`) |
| `cli/ucli/commands/demo_ops.py` | Local demo HTTP server lifecycle |
| `cli/ucli/trace/pytrace.py` | Isolated trace worker (never `exec` in-process) |

Each of those imports is marked `# nosec B404` with an inline rationale. Call sites that spawn processes use `# nosec B603` where Bandit flags the invoke. **Do not** silence B404/B603 for shell=`True`, user-controlled argv, or new call sites without review.

The committed `.bandit-baseline.json` is refreshed to **zero residual findings** when intentional `subprocess` imports are `# nosec B404`'d and call sites use `# nosec B603` where needed. Re-run `bandit -r cli/ -f json -o .bandit-baseline.json` after accepting any *new* residual finding — never to hide HIGH severity or unreviewed drift. Fail-closed gates (`-lll` HIGH + `-b` baseline) stay mandatory.

## Runtime trace sandbox (`u trace module`)

Tracing **must** execute target Python to collect call events. Mitigations:

| Control | Behavior |
| --- | --- |
| Process isolation | Worker runs in a subprocess; the CLI process never `exec_module`s the target |
| Path allowlist | Target must resolve under cwd or `UF_TRACE_ALLOW_ROOTS`; non-`.py` refused |
| Argv denylist | `func` must be a simple identifier; dunders and `eval`/`exec`/`__import__`/`compile`/`open`/… are refused |
| POSIX limits | Soft `RLIMIT_CPU` / `RLIMIT_AS` in the worker when `resource` exists |
| Windows Job Object | Best-effort process memory cap via Job Object (ctypes); failure is non-fatal |
| Timeout | 60s hard kill |

### Residual risk

- Target code still runs with the privileges of the user invoking `u trace`. A malicious `.py` under an allowlisted root can perform any action the OS user can (network, filesystem outside the job memory limit, etc.).
- Windows Job Object assignment is best-effort; if ctypes/API calls fail, only the timeout remains as a hard stop (no POSIX `RLIMIT_*`).
- Denylist blocks *names* passed to `getattr(module, name)` — it does not inspect what the callable body does.
- Prefer `u trace errors` (AST-only) when execution is not required.

Do not treat trace as a general-purpose sandbox for untrusted code.
