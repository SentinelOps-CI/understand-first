# Usage Guide

This guide covers installation, configuration, and the end‑to‑end workflow using the `u` CLI and the VS Code extension.

## Install
```bash
# from repo root
pip install -e cli
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
```
2) Create a task lens from seeds (files, functions, or labels)
```bash
u lens from-seeds --map maps/repo.json --seed examples/app/hot_path.py -o maps/lens.json
# or use a preset label (from .understand-first.yml)
u lens preset bug --map maps/repo.json -o maps/lens.json
```
3) Trace the hot path at runtime (Python demo)
```bash
u trace module examples/app/hot_path.py run_hot_path -o traces/tour.json
```
4) Merge runtime trace into the lens and rank by error proximity
```bash
u lens merge-trace maps/lens.json traces/tour.json -o maps/lens_merged.json
```
5) Generate a tour for code review or walkthrough
```bash
u tour maps/lens_merged.json -o tours/local.md
```
6) Optional gate: verify walkthrough milestones
```bash
u tour_gate --progress .uf-progress.json
```

## Lensing from issue or CI logs
```bash
u lens from-issue --map maps/repo.json path/to/issue.md -o maps/lens.json
u lens ingest-github path/to/gh_actions_log.txt > seeds.json
u lens ingest-jira path/to/jira.json > seeds.json
```

## Contracts
Generate and manage contracts from interface definitions with formal verification support.

### Basic workflow
```bash
# 1. Generate contracts from OpenAPI specs
u contracts from-openapi examples/apis/petstore-mini.yaml -o contracts/contracts_from_openapi.yaml

# 2. Generate contracts from protobuf/gRPC specs  
u contracts from-proto examples/apis/orders.proto -o contracts/contracts_from_proto.yaml

# 3. Compose multiple contract sources into a single file
u contracts compose -i contracts/contracts_from_openapi.yaml -i contracts/contracts_from_proto.yaml -o contracts/contracts.yaml

# 4. Generate Lean formal verification stubs
u contracts lean-stubs contracts/contracts.yaml -o contracts/lean/

# 5. Verify Lean coverage for all contract functions
u contracts verify-lean contracts/contracts.yaml -l contracts/lean

# 6. Generate property test stubs
u contracts stub-tests contracts/contracts.yaml -o tests/test_contracts.py
```

### Contract composition
The `compose` command merges multiple contract YAML files, deduplicating modules and functions while preserving order. This is useful when you have contracts from different sources (OpenAPI, protobuf, manual definitions) that need to be unified.

### Lean verification
The `lean-stubs` command generates one Lean file per module containing:
- `invariant_{module}__{function}` definitions for each contract function
- `theorem` stubs for formal verification of contract properties

The `verify-lean` command checks that every function in your contracts has a corresponding Lean theorem stub, helping ensure complete formal verification coverage.

### Contract structure
Contracts are organized by modules (e.g., `ROUTE::pets`, `PROTO::orders`) with functions containing:
- Request/response schemas as compact JSON metadata
- Pre/post conditions for formal verification
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
The project includes a GitHub Actions workflow (`.github/workflows/ci.yml`) that automatically:
- Lints code with `ruff`
- Generates contracts from OpenAPI and protobuf specs
- Composes contracts into a unified file
- Generates Lean verification stubs
- Verifies Lean coverage for all contract functions
- Runs the test suite

### Manual CI steps
```bash
# Run the same checks locally
ruff check .
u contracts compose -i contracts/contracts_from_openapi.yaml -i contracts/contracts_from_proto.yaml -o contracts/contracts.yaml
u contracts lean-stubs contracts/contracts.yaml -o contracts/lean/
u contracts verify-lean contracts/contracts.yaml -l contracts/lean
pytest -q
```

### PR gates
- Run `u scan`, `u lens from-seeds`, and `u tour` in CI to attach artifacts to PRs
- Use a PR gate that runs `u tour_gate` and fails the build if walkthrough milestones are not met
- The contracts verification step will fail if Lean stubs are missing for any contract function
