# Usage Guide

This guide covers installation, configuration, and the end‑to‑end workflow using the `u` CLI and the VS Code extension.

## Install
```bash
# from repo root (recommended; matches CI)
uv sync --all-extras
# or
pip install -e ".[dev,examples]"
# or from PyPI (if published)
# pip install understand-first
```

Verify installation:
```bash
u --help | head -n 20
```

## Configure
Create `.understand-first.yml` in your repository root:
```yaml
hops: 2
seeds: []
seeds_for:
  bug: [examples/app/hot_path.py]
contracts_paths:
  - contracts/contracts_from_openapi.yaml
  - contracts/contracts_from_proto.yaml
glossary_path: docs/glossary.md
metrics:
  enabled: false
```
Generate a starter config:
```bash
u init
```
Validate your config:
```bash
u config_validate --path .understand-first.yml
```

## Health check
```bash
u doctor
```
Checks Python and Node availability, grpc_tools, open ports, VS Code, and repo write permissions.

## Core workflow
1) Scan the repository
```bash
u scan . -o maps/repo.json
# Optional: limit adapters (python, javascript, go, java, rust, csharp; aliases js/ts/typescript/golang/cs/c#)
u scan . --lang python -o maps/repo.json
u scan examples/js_toy --lang javascript -o maps/js.json
u scan examples/go_toy --lang go -o maps/go.json
u scan examples/java_toy --lang java -o maps/java.json
u scan examples/rust_toy --lang rust -o maps/rust.json
u scan examples/csharp_toy --lang csharp -o maps/csharp.json
```

`u scan` dispatches registered language adapters by file extension. Python uses
the AST analyzer. JavaScript/TypeScript (`.js`/`.mjs`/`.cjs`/`.ts`/`.tsx`/`.jsx`)
prefer a **Node + TypeScript compiler API** path (`javascript-ast` /
`typescript-ast`, complexity `ast-cyclomatic`) when Node 18+ and
`npm install` in `cli/ucli/analyzers/js_ast` are available; otherwise they
**degrade** to the regex adapter (`*-best-effort`, `keyword-heuristic`).
Force with `UF_JS_ANALYZER=regex|ast|auto`. Relative imports may also resolve via
re-export barrels and nearest `package.json` `"exports"` subpaths (AST path).
Go (`.go`) prefers **`go/parser`**
via `go run` in `cli/ucli/analyzers/go_ast` (`go-ast`, `ast-cyclomatic`) when
Go 1.21+ is on PATH; otherwise `go-best-effort` regex. Force with
`UF_GO_ANALYZER=regex|ast|auto`. Java (`.java`) is **`javalang` AST** when installed (`java-ast`,
`ast-cyclomatic`; `pip install javalang` or `understand-first[analyzers]`);
otherwise **best-effort regex** (`java-best-effort`). Force with
`UF_JAVA_ANALYZER=regex|ast|auto`. Rust (`.rs`) prefers **`syn`** via
`cargo run` in `cli/ucli/analyzers/rust_ast` (`rust-ast`, `ast-cyclomatic`) when
cargo is on PATH; otherwise **best-effort regex** (`rust-best-effort`). Force with
`UF_RUST_ANALYZER=regex|ast|auto`. C# (`.cs`) prefers **Roslyn** via
`dotnet run` in `cli/ucli/analyzers/csharp_ast` (`csharp-ast`, `ast-cyclomatic`) when
a .NET SDK is on PATH (`dotnet --list-sdks` non-empty); otherwise **best-effort
regex** (`csharp-best-effort`). Force with `UF_CSHARP_ANALYZER=regex|ast|auto`.
JS, Go, Java, Rust, and C# are not Python-parity. Unsupported source extensions
(e.g. `.rb`) are counted as not analyzed — they are never fed to the Python
analyzer or emitted as empty fake maps.
2) Create a task lens from seeds (files, functions, or labels)
```bash
u lens from-seeds --map maps/repo.json --seed examples/app/hot_path.py -o maps/lens.json
# Default seed match is substring (tok in qname). Use --exact for full qname /
# local name / simple_name equality only:
u lens from-seeds --map maps/repo.json --seed compute --exact -o maps/lens.json
# or use a preset label (from .understand-first.yml)
u lens preset bug --map maps/repo.json -o maps/lens.json
```
3) Trace the hot path at runtime (Python demo)
```bash
u trace module examples/app/hot_path.py run_hot_path -o traces/tour.json
```

Trace targets must resolve under the current working directory, or under extra
roots listed in ``UF_TRACE_ALLOW_ROOTS`` (``os.pathsep``-separated absolute or
relative directories). Example (PowerShell):

```powershell
$env:UF_TRACE_ALLOW_ROOTS = "D:\safe\traces;D:\other\allow"
u trace module D:\safe\traces\mod.py run -o traces/out.json
```

Callable names are restricted to simple identifiers; a denylist refuses
``eval`` / ``exec`` / ``__import__`` / ``open`` and similar. See
[SECURITY.md](SECURITY.md) for residual risk (subprocess still executes target
code; Windows Job Object memory limits are best-effort).

4) Merge runtime trace into the lens and rank by error proximity
```bash
u lens merge-trace maps/lens.json traces/tour.json -o maps/lens_merged.json
```
5) Generate a tour for code review or walkthrough
```bash
u tour maps/lens_merged.json -o tours/local.md
```
6) Optional gates
```bash
# CI fixture smoke (preferred PR gate — see tour-must-pass.yml):
u tour_run maps/lens_merged.json -f fixtures

# IDE walkthrough milestones (requires .uf-progress.json from the VS Code panel,
# or produce one via fixture):
u tour_gate --fixture-lens maps/lens_merged.json
u tour_gate --progress .uf-progress.json
```

## Lensing from issue or CI logs
```bash
u lens from-issue --map maps/repo.json path/to/issue.md -o maps/lens.json
u lens ingest-github path/to/gh_actions_log.txt > seeds.json
u lens ingest-jira path/to/jira.json > seeds.json
```

## Contracts
Generate and manage contracts from interface definitions. Lean output is scaffold-only (presence checks), not compiled formal verification.

### Basic workflow
```bash
# 1. Generate contracts from OpenAPI specs
u contracts from-openapi examples/apis/petstore-mini.yaml -o contracts/contracts_from_openapi.yaml

# 2. Generate contracts from protobuf/gRPC specs  
u contracts from-proto examples/apis/orders.proto -o contracts/contracts_from_proto.yaml

# 3. Compose multiple contract sources into a single file
u contracts compose -i contracts/contracts_from_openapi.yaml -i contracts/contracts_from_proto.yaml -o contracts/contracts.yaml

# 4. Generate Lean scaffold stubs (Prop := True / by trivial — not compiled)
u contracts lean-stubs contracts/contracts.yaml -o contracts/lean/

# 5. Presence-only check that scaffold theorem stubs exist (does not compile Lean)
u contracts verify-lean contracts/contracts.yaml -l contracts/lean

# 6. Generate property test stubs
u contracts stub-tests contracts/contracts.yaml -o tests/test_contracts.py
```

### Contract composition
The `compose` command merges multiple contract YAML files, deduplicating modules and functions while preserving order. This is useful when you have contracts from different sources (OpenAPI, protobuf, manual definitions) that need to be unified.

### Lean scaffold (presence-only)
The `lean-stubs` command generates one Lean file per module containing scaffold-only:
- `invariant_{module}__{function} : Prop := True`
- `theorem ... := by trivial`

These are **not** real proofs and are not compiled by Understand-First. The `verify-lean` command checks file presence of those theorem names (`mode: presence-only`); it does not run `lake build` or the Lean compiler.

### Contract structure
Contracts are organized by modules (e.g., `ROUTE::pets`, `PROTO::orders`) with functions containing:
- Request/response schemas as compact JSON metadata
- Pre/post condition fields (documentation; Lean scaffold does not prove them)
- Side effect annotations

## Visualization
Render a delta between two lenses as an SVG.
```bash
u visual delta maps/old_lens.json maps/new_lens.json -o maps/delta.svg
```

## Dashboard and glossary
```bash
u glossary -o docs/glossary.md
u dashboard --repo maps/repo.json --lens maps/lens_merged.json --bounds maps/boundaries.json -o docs/understanding-dashboard.md
```

## Time to Understanding (TTU) metrics
Enable metrics in `.understand-first.yml`:
```yaml
metrics:
  enabled: true
```
The CLI records events in `metrics/events.jsonl`. Generate a weekly summary:
```bash
u ttu report -o docs/ttu.md
```
Record custom events:
```bash
u ttu map_open
u ttu tour_run
u ttu fixture_pass
```

## VS Code extension
After generating `maps/repo.json` and a lens, open the repository in VS Code:
- Decorations show call counts, runtime hotness, and contract presence.
- Command palette:
  - Understand-First: Show Tour
  - Understand-First: Explain Error Propagation
  - Understand-First: Generate Property Test
  - Understand-First: Open Glossary

## CI integration
The project includes a GitHub Actions workflow (`.github/workflows/ci.yml`) that runs:
- **Tests** on Python 3.9–3.13 (`uv run pytest` with coverage)
- **Lint**: Ruff (check + format check) and Pyright on `cli/` and `tests/`
- **VS Code extension**: `npm ci`, `npm run lint`, and `vsce package` under `ide/vscode/understand-first/`
- **React example**: Vite production build under `examples/react_dashboard/`
- **SBOM**: CycloneDX from locked `requirements.txt` (after a successful lint job)
- **Wheel build** and optional Docker publish (see workflow for conditions)

Contract generation and Lean steps are available as CLI commands but are not all run as separate CI stages; see the workflow file for the exact jobs.

### Manual CI-aligned checks
```bash
# After `uv sync --all-extras`
uv run ruff check cli tests
uv run ruff format --check cli tests
uv run pyright
uv run pytest -q
```

### PR gates
- Fail-closed: `u scan`, `u lens from-seeds`, `u trace` / merge, `u tour`, then `u tour_run` (see `.github/workflows/tour-must-pass.yml`)
- Map delta: `u scan` base/head + `u diff --old/--new` (see `understand-first-pr-analysis.yml`)
- `u tour_gate` is for IDE milestone progress (`.uf-progress.json`); do not treat it as a substitute for `tour_run` in CI
- The contracts `verify-lean` step fails if scaffold theorem stubs are missing for any contract function (presence-only; does not compile Lean)
