# Understand-First (TTU Kit)

**Generate understanding, not just code.** This toolkit helps teams reduce **Time To Understanding (TTU)** and **Time To First Safe Change (TTFSC)** with maps, traces, tours, contracts, and PR guardrails.

<p align="center">
  <img src="assets/banner.svg" alt="Understand-First — Generate understanding, not just code" width="100%" />
</p>

## Why Understand-First?

**The Problem**: Modern codebases are complex, and new team members often spend weeks or months understanding the system before making their first safe change. Traditional documentation becomes outdated, and static analysis tools only show structure, not understanding.

**The Solution**: Understand-First generates **living documentation** that evolves with your code. It creates interactive maps, traces, and tours that show not just what the code does, but **why** and **how** it works together.

### Key Benefits

- **Reduce Onboarding Time**: New developers understand complex systems 3-5x faster
- **Prevent Breaking Changes**: Runtime tracing shows actual execution paths, not just static analysis
- **Living Documentation**: Maps and tours stay current as code evolves
- **PR Safety**: CI gates ensure understanding artifacts are updated with changes
- **Context Debt Visibility**: Metrics show where understanding gaps exist

### How It Differs from Other Tools

| Feature | Understand-First | Static Analysis Tools | Documentation Generators | Code Review Tools |
|---------|------------------|----------------------|-------------------------|-------------------|
| **Runtime Tracing** | ✅ Actual execution paths | ❌ Static only | ❌ No runtime info | ❌ No tracing |
| **Interactive Tours** | ✅ Step-by-step walkthroughs | ❌ Static reports | ❌ Static docs | ❌ No tours |
| **Living Documentation** | ✅ Auto-updates with code | ❌ Manual updates | ❌ Manual updates | ❌ No docs |
| **PR Integration** | ✅ CI gates & artifacts | ❌ No PR integration | ❌ No PR integration | ✅ Basic integration |
| **Context Debt Metrics** | ✅ TTU/TTFSC tracking | ❌ No metrics | ❌ No metrics | ❌ No metrics |
| **Multi-Language** | ✅ Python + planned TS/Go | ✅ Multiple languages | ✅ Multiple languages | ✅ Multiple languages |
| **IDE Integration** | ✅ VS Code extension | ✅ IDE plugins | ❌ No IDE integration | ✅ IDE plugins |
| **Contract Verification** | ✅ Formal verification | ❌ No contracts | ❌ No contracts | ❌ No contracts |

## What it does
- Builds maps: call graphs and dependency graphs (Python-first; TypeScript/Go adapters planned).
- Captures invariants: extracts pre/postcondition hints from code and tests and lists suspected side effects.
- Creates hot‑path fixtures: minimal, reproducible test scaffolds to read by running.
- Produces reading plans: auto-generates a module summary and questions to answer before editing.
- Enforces PR “Proof of Understanding”: CI can fail if map deltas, invariants, or module READMEs are missing.
- Measures context debt: simple metrics (missing READMEs, deep call chains, unmanaged side effects).

## Quick Start

### Option 1: Try Without Installation
1. **Web Playground**: Open [web_demo/index.html](web_demo/index.html) in your browser
2. **Paste Code**: Try the interactive code analysis
3. **Explore Features**: Test tours, exports, and visualizations

### Option 2: Full Installation
```bash
# requirements: Python 3.10+
cd cli
pip install -e .

# Interactive setup with wizard
u init --wizard

# Or manual setup
u scan ../examples/python_toy -o ../maps/repo.json
u lens from-seeds --map ../maps/repo.json --seed compute -o ../maps/lens.json
u tour ../maps/lens.json -o ../tours/local.md
```

### Option 3: Use Project Templates
```bash
# Initialize with project template
u init --wizard

# Choose from:
# - Django web application
# - FastAPI web application  
# - React frontend
# - Flask web application
# - Microservices architecture
# - Node.js application
# - Go application
# - Java application
# - Python project
```

### Complete Workflow
```bash
# 1. Scan your codebase
u scan examples/python_toy -o maps/repo.json

# 2. Create understanding lens
u lens from-seeds --map maps/repo.json --seed compute -o maps/lens.json

# 3. Trace runtime execution (optional)
u trace module examples/app/hot_path.py run_hot_path -o traces/tour.json

# 4. Merge trace into lens
u lens merge-trace maps/lens.json traces/tour.json -o maps/lens_merged.json

# 5. Generate understanding tour
u tour maps/lens_merged.json -o tours/local.md

# 6. Generate contracts (optional)
u contracts from-openapi examples/apis/petstore-mini.yaml -o contracts/contracts_from_openapi.yaml
u contracts compose -i contracts/contracts_from_openapi.yaml -o contracts/contracts.yaml
u contracts lean-stubs contracts/contracts.yaml -o contracts/lean/
u contracts verify-lean contracts/contracts.yaml -l contracts/lean
```

Open `maps/`, `contracts/`, and `examples/` to see artifacts and experiment.

## Real-World Examples

Understand-First includes comprehensive examples demonstrating modern software patterns:

### FastAPI E-commerce API
```bash
# Modern async API with authentication, cart, and order management
python examples/fastapi_ecommerce/main.py
```
- **Features**: Async patterns, dependency injection, Pydantic models, JWT authentication
- **Patterns**: REST API design, error handling, data validation, background tasks

### React Dashboard
```bash
# Modern React application with hooks and state management
cd examples/react_dashboard
npm install && npm start
```
- **Features**: React hooks, custom hooks, state management, component architecture
- **Patterns**: Functional components, useEffect, useState, custom hooks, API integration

### Microservices Architecture
```bash
# Distributed system with multiple services
python examples/microservices/order_service.py
python examples/microservices/user_service.py
```
- **Features**: Service communication, database integration, Redis caching, async operations
- **Patterns**: Distributed systems, event-driven architecture, service discovery

### Flask Blog Application
```bash
# Full blog with authentication, comments, and admin
python examples/flask_blog/app.py
```
- **Features**: User authentication, post management, comments, admin interface
- **Patterns**: Blueprint organization, form handling, database relationships, background tasks

### Django E-commerce
```bash
# Complete Django application
cd examples/django_ecommerce
python manage.py runserver
```
- **Features**: Django ORM, admin interface, model relationships, view patterns
- **Patterns**: MVC architecture, template inheritance, form handling, authentication

## Try It Live

**Experience Understand-First without installation**: [Interactive Web Demo](web_demo/index.html)

The web demo lets you:
- **Paste your Python code** and see instant analysis
- **Explore interactive tours** and visualizations
- **Compare before/after** understanding improvements
- **Experience key features** in your browser
- **Export analysis results** (JSON, Markdown, Tour formats)
- **Test advanced code analysis** features
- **Real-time complexity calculation** with side effect detection
- **Interactive call graphs** and function relationships
- **Modern responsive UI** with tabbed interface
- **Progress indicators** and visual feedback

## Project Templates

Understand-First provides pre-configured templates for common project types:

### Available Templates
- **Django**: Web applications with models, views, admin, and API development
- **FastAPI**: Modern async APIs with dependency injection and OpenAPI
- **React**: Frontend applications with hooks, state management, and components
- **Flask**: Traditional web apps with blueprints, forms, and templates
- **Microservices**: Distributed systems with service communication
- **Node.js**: Express applications with middleware and API patterns
- **Go**: Applications and microservices with concurrency patterns
- **Java**: Spring applications with enterprise patterns
- **Python**: General Python applications and libraries

### Using Templates
```bash
# Interactive template selection
u init --wizard

# Templates include:
# - Optimized seed presets for each technology
# - Technology-specific file patterns
# - Advanced analysis options
# - CI/CD integration settings
# - IDE integration configurations
```

### Template Features
Each template includes:
- **Smart Seed Presets**: Pre-configured analysis seeds for common patterns
- **File Pattern Optimization**: Include/exclude patterns tailored to each technology
- **Analysis Options**: Technology-specific analysis settings
- **CI/CD Integration**: Pre-configured for GitHub, GitLab, Jenkins
- **IDE Integration**: VS Code, PyCharm, Vim support
- **Best Practices**: Follows state-of-the-art software engineering

## Example Outputs

### Repository Map
Understand-First generates a comprehensive map of your codebase showing function relationships:

```json
{
  "language": "python",
  "functions": {
    "examples/python_toy/pkg/service:compute": {
      "file": "examples/python_toy/pkg/service.py",
      "calls": ["add", "maybe_log"],
      "callers": [],
      "complexity": 3,
      "side_effects": ["logging"]
    },
    "examples/python_toy/pkg/service:add": {
      "file": "examples/python_toy/pkg/service.py", 
      "calls": [],
      "callers": ["compute"],
      "complexity": 1,
      "side_effects": []
    }
  }
}
```

### Interactive Tour
Generated tours provide step-by-step walkthroughs with actionable insights:

```markdown
# Understanding Tour: Hot Path Analysis

## Overview
This tour traces the execution path through `examples/app/hot_path.py:run_hot_path()`.

## Step 1: HTTP Service Check
**File**: `examples/app/hot_utils.py:wait_http()`
**Purpose**: Ensures the HTTP service is available before making requests
**Key Logic**: Polls the service endpoint with exponential backoff

## Step 2: Pet Operations
**File**: `examples/clients/pet_client.py`
**Purpose**: Demonstrates REST API client usage
**Key Functions**:
- `list_pets()`: Retrieves all pets
- `create_pet()`: Adds a new pet
- `get_pet()`: Fetches specific pet by ID

## Step 3: Order Operations (Optional)
**File**: `examples/clients/orders_client.py`
**Purpose**: Shows gRPC client integration
**Note**: Only runs if gRPC service is available
```

### Before/After: Code Understanding

**Before Understand-First**:
- New developer spends 2-3 days reading through scattered files
- No clear understanding of execution flow
- Uncertainty about which functions are critical
- Risk of breaking changes due to incomplete understanding

**After Understand-First**:
- Interactive tour shows complete execution path in 30 minutes
- Clear identification of hot paths and critical functions
- Runtime tracing reveals actual behavior, not just static analysis
- Confidence in making changes with full context

### Contract Verification
Formal contracts ensure API compliance:

```yaml
ROUTE::pets:
  GET /pets:
    request_schema: {}
    response_schema: 
      type: array
      items: {type: object, properties: {id: string, name: string}}
    preconditions: []
    postconditions: ["response.status_code == 200"]
    side_effects: ["database_read"]
```

### Visual Delta
See exactly what changed between versions:

```svg
<!-- Generated delta visualization showing -->
<!-- - New functions (green) -->
<!-- - Modified functions (yellow) -->  
<!-- - Removed functions (red) -->
<!-- - Call relationship changes -->
```

### Health check
```bash
u doctor
```
Verifies Python/Node, grpc_tools, VS Code, ports, and repo write permissions; exits non‑zero with fixes and a link to docs if problems are found.

### Guided demo
```bash
u demo
```
Generates contracts, starts services, traces the hot path, builds a tour and dashboard, and prints a shareable file:// URL.

## Concepts
- **TTU**: time from “new task” to “first accurate mental model.”
- **TTFSC**: time from “new task” to “first safe change merged.”
- **Context Debt**: the gap between the context a system requires and what it affords to readers.

## CLI overview
Key commands provided by the `u` CLI (see `u --help` for all):

- Scanning and mapping
  - `u scan <path> -o maps/repo.json`: Build a repository map (Python-first)
  - `u map maps/repo.json -o maps/`: Emit Graphviz DOT
  - `u report maps/repo.json -o maps/`: Emit a Markdown report

- Lenses and tours
  - `u lens from-issue --map maps/repo.json <issue.md> -o maps/lens.json`
  - `u lens from-seeds --map maps/repo.json --seed <file_or_symbol> -o maps/lens.json`
  - `u lens merge-trace maps/lens.json traces/tour.json -o maps/lens_merged.json`
  - `u lens preset --map maps/repo.json <label> -o maps/lens.json`
  - `u lens ingest-github <gh_actions_log.txt>` or `u lens ingest-jira <jira.json>`
  - `u lens explain <qualified.name> --lens maps/lens_merged.json --repo maps/repo.json`
  - `u tour maps/lens_merged.json -o tours/local.md`
  - `u tour_run --fixtures fixtures maps/lens_merged.json` (verify minimal fixture)

- Runtime tracing (Python demo)
  - `u trace module <pyfile> <function> -o traces/trace.json`
  - `u trace errors <pyfile> --json`

- Boundaries
  - `u boundaries scan <path> -o maps/boundaries.json`

- Contracts
  - `u contracts from-openapi examples/apis/petstore-mini.yaml -o contracts/contracts_from_openapi.yaml`
  - `u contracts from-proto examples/apis/orders.proto -o contracts/contracts_from_proto.yaml`
  - `u contracts compose -i contracts/contracts_from_openapi.yaml -i contracts/contracts_from_proto.yaml -o contracts/contracts.yaml`
  - `u contracts lean-stubs contracts/contracts.yaml -o contracts/lean/`
  - `u contracts verify-lean contracts/contracts.yaml -l contracts/lean`
  - `u contracts stub-tests contracts/contracts.yaml -o tests/test_contracts.py`

- Visualization
  - `u visual delta maps/old_lens.json maps/new_lens.json -o maps/delta.svg`

- Packs and publishing
  - `u pack create --lens maps/lens_merged.json --tour tours/local.md --contracts contracts/contracts_from_openapi.yaml -o packs/pack.zip`
  - `u pack --publish` (local pack in `dist/`)

- Glossary and dashboard
  - `u glossary -o docs/glossary.md`
  - `u dashboard --repo maps/repo.json --lens maps/lens_merged.json --bounds maps/boundaries.json -o docs/understanding-dashboard.md`

- Health, TTU, and init
  - `u doctor`
  - `u ttu <event>` or `u ttu report -o docs/ttu.md`
  - `u init` (creates `.understand-first.yml` and appends a brief tour section to `README.md`)
  - `u tour_gate --progress .uf-progress.json`
  - `u config_validate --path .understand-first.yml`

## Real-World Examples

### Django E-commerce Application
Complete Django e-commerce system with models, views, and business logic:
- **Location**: `examples/django_ecommerce/`
- **Features**: User management, product catalog, shopping cart, order processing
- **Understanding Focus**: Model relationships, view logic, form handling, payment processing

### Microservices Architecture
Distributed user service with async operations and service communication:
- **Location**: `examples/microservices/`
- **Features**: User service, database operations, external API calls, event handling
- **Understanding Focus**: Service boundaries, async patterns, error handling, data flow

### Try the Examples
```bash
# Analyze Django e-commerce app
u scan examples/django_ecommerce -o maps/django_repo.json
u lens from-seeds --map maps/django_ecommerce_repo.json --seed "models.py" -o maps/django_lens.json

# Analyze microservices
u scan examples/microservices -o maps/microservices_repo.json
u lens from-seeds --map maps/microservices_repo.json --seed "user_service.py" -o maps/microservices_lens.json
```

## Repository contents
- `cli/` – Typer-based CLI (`u`) for scanning, mapping, reporting, tracing, lenses, contracts, and visualization.
- `docs/` – onboarding, usage, privacy, and version notes.
- `ide/` – VS Code extension that overlays maps, shows tours, and explains error propagation.
- `examples/` – toy project, Django e-commerce, and microservices for demos and CI.
- `templates/` – pre-configured templates for Django, FastAPI, React, and microservices.
- `web_demo/` – interactive web demo for trying the tool without installation.
- `maps/` – generated maps (JSON, DOT, markdown, SVG).
- `tests/` – unit tests for CLI components.

## VS Code extension
The VS Code extension contributes commands:
- `Understand-First: Show Tour` opens an interactive walkthrough with progress indicators and one-click commands.
- `Understand-First: Explain Error Propagation` shows seed nodes and guidance.
- `Understand-First: Generate Property Test` scaffolds language-aware property test templates.
- `Understand-First: Open Glossary` opens `docs/glossary.md` or a configured glossary path.
The editor displays lightweight decorations for call counts, runtime hotness, and contract presence when maps are available.

## Configuration

### Quick Setup with Wizard
Get started quickly with the interactive configuration wizard:

```bash
u init --wizard
```

The wizard will guide you through:
- Project type selection (Python, Django, FastAPI, React, Microservices)
- Seed configuration for different scenarios
- Contract and metrics setup
- Project-specific optimizations

### Project Templates
Pre-configured templates for common project types:

```bash
# Copy template for your project type
cp templates/django/.understand-first.yml .understand-first.yml
cp templates/fastapi/.understand-first.yml .understand-first.yml
cp templates/microservices/.understand-first.yml .understand-first.yml
cp templates/react/.understand-first.yml .understand-first.yml
```

### Manual Configuration
The file `.understand-first.yml` controls seeds, presets, hops, and metrics. Example:
```yaml
hops: 2
seeds: []
seeds_for:
  bug: [examples/app/hot_path.py]
  feature: [*/models.py, */views.py]
contracts_paths:
  - contracts/api_contracts.yaml
glossary_path: docs/glossary.md
metrics:
  enabled: false
```

## Roadmap
- Language adapters: TypeScript (tsserver/ts-morph), Go (go/ast), Java (Spoon).
- Map‑delta visualizer comment bot.
- Invariant DSL with optional Lean proof stubs.
- IDE integrations (VS Code) to overlay maps on code.

## Understand-First Integration

This project uses [Understand-First](https://github.com/your-org/understand-first) for automated code understanding and documentation generation.

### Quick Start

1. **Generate Repository Map**
   ```bash
   u scan . -o maps/repo.json
   ```

2. **Create Understanding Lens**
   ```bash
   u lens from-seeds --map maps/repo.json --seed main -o maps/lens.json
   ```

3. **Generate Understanding Tour**
   ```bash
   u tour maps/lens.json -o tours/understanding.md
   ```

4. **Run Guided Demo**
   ```bash
   u demo
   ```

### Configuration

The project configuration is stored in `.understand-first.yml`. Key settings include:

- **Hops**: Analysis depth (currently set to 2)
- **Seeds**: Starting points for analysis
- **Presets**: Common scenarios like bug fixes and feature development
- **Patterns**: File inclusion/exclusion rules

### CI/CD Integration

The project is configured for CI/CD integration. Add this to your pipeline:

```yaml
- name: Understand-First Analysis
  run: |
    u scan . -o maps/repo.json
    u lens preset feature --map maps/repo.json -o maps/lens.json
    u tour maps/lens.json -o tours/ci-tour.md
```

### IDE Integration

Install the Understand-First VS Code extension for:
- Gutter annotations showing complexity and call counts
- Quick peek tours and explanations
- Real-time understanding insights

### Learn More

- [Documentation](https://github.com/your-org/understand-first#readme)
- [Examples](https://github.com/your-org/understand-first/tree/main/examples)
- [Web Playground](https://your-org.github.io/understand-first/demo)
