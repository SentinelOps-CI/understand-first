# Understand-First API Documentation

This document provides comprehensive API documentation for Understand-First.

## Table of Contents

- [CLI Commands](#cli-commands)
- [Core Modules](#core-modules)
- [Web Playground API](#web-playground-api)
- [Configuration API](#configuration-api)
- [Template API](#template-api)
- [Examples API](#examples-api)

## CLI Commands

### Main Entry Point

```bash
python u.py [command] [options]
```

### Available Commands

#### `scan`
Scans a codebase and generates a repository map.

```bash
u scan <path> -o <output_file>
```

**Parameters:**
- `path`: Path to the codebase to scan
- `-o, --output`: Output file for the repository map (default: `maps/out.json`)

**Example:**
```bash
u scan examples/python_toy -o maps/repo.json
```

#### `lens`
Creates understanding lenses from seeds or merges traces.

```bash
# Create lens from seeds
u lens from-seeds --seed <seed> --map <map_file> -o <output_file>

# Merge trace into lens
u lens merge-trace <lens_file> <trace_file> -o <output_file>
```

**Parameters:**
- `--seed`: Seed function(s) to start analysis from
- `--map`: Repository map file
- `-o, --output`: Output file for the lens

**Example:**
```bash
u lens from-seeds --seed compute --map maps/repo.json -o maps/lens.json
```

#### `trace`
Captures runtime traces of function execution.

```bash
u trace module <python_file> <function_name> [args...] -o <output_file>
```

**Parameters:**
- `python_file`: Python file containing the function
- `function_name`: Function to trace
- `args`: Arguments to pass to the function
- `-o, --output`: Output file for the trace

**Example:**
```bash
u trace module examples/app/hot_path.py run_hot_path -o traces/tour.json
```

#### `tour`
Generates understanding tours from lenses.

```bash
u tour <lens_file> -o <output_file>
```

**Parameters:**
- `lens_file`: Lens file to generate tour from
- `-o, --output`: Output file for the tour

**Example:**
```bash
u tour maps/lens.json -o tours/tour.md
```

#### `init`
Initializes Understand-First configuration.

```bash
u init [--wizard]
```

**Options:**
- `--wizard`: Run interactive configuration wizard

**Example:**
```bash
u init --wizard
```

#### `doctor`
Checks system health and dependencies.

```bash
u doctor
```

#### `demo`
Runs the interactive demo.

```bash
u demo
```

#### `contracts`
Manages contract verification.

```bash
# Generate contracts from OpenAPI
u contracts from-openapi <openapi_file> -o <output_file>

# Generate contracts from Protocol Buffers
u contracts from-proto <proto_file> -o <output_file>

# Compose multiple contracts
u contracts compose -i <input_files> -o <output_file>

# Generate Lean stubs
u contracts lean-stubs <contracts_file> -o <output_dir>

# Verify Lean contracts
u contracts verify-lean <contracts_file> -l <lean_dir>
```

## Core Modules

### Analyzers

#### `python_analyzer`
Analyzes Python code and generates repository maps.

```python
from cli.ucli.analyzers.python_analyzer import build_python_map

# Build repository map
repo_map = build_python_map(pathlib.Path("path/to/code"))
```

**Returns:**
- Dictionary containing function relationships, complexity, and side effects

### Graph

#### `graph`
Generates DOT format graphs from repository maps.

```python
from cli.ucli.graph.graph import write_dot

# Write graph to file
write_dot(repo_map, "output.dot")
```

### Lens

#### `lens`
Creates and manages understanding lenses.

```python
from cli.ucli.lens.lens import lens_from_seeds, merge_trace_into_lens

# Create lens from seeds
lens = lens_from_seeds(seeds, repo_map)

# Merge trace into lens
merged_lens = merge_trace_into_lens(lens, trace)
```

### Trace

#### `pytrace`
Captures runtime traces of Python functions.

```python
from cli.ucli.trace.pytrace import run_callable_with_trace

# Trace function execution
trace = run_callable_with_trace("module.py", "function_name", arg1, arg2)
```

### Report

#### `report`
Generates markdown reports from lenses.

```python
from cli.ucli.report.report import make_report_md

# Generate report
report = make_report_md(lens)
```

## Web Playground API

### JavaScript Functions

#### `performAdvancedAnalysis(code)`
Performs comprehensive code analysis.

**Parameters:**
- `code`: Python code string to analyze

**Returns:**
- Object containing analysis results

**Example:**
```javascript
const analysis = performAdvancedAnalysis(`
def compute(a, b):
    return a + b
`);
```

#### `calculateComplexity(code)`
Calculates cyclomatic complexity.

**Parameters:**
- `code`: Python code string

**Returns:**
- Complexity score

#### `findFunctionCalls(code)`
Finds function call relationships.

**Parameters:**
- `code`: Python code string

**Returns:**
- Array of function call objects

#### `findSideEffects(code)`
Identifies side effects in code.

**Parameters:**
- `code`: Python code string

**Returns:**
- Array of side effect objects

#### `displayAdvancedResults(analysis)`
Displays analysis results in the UI.

**Parameters:**
- `analysis`: Analysis results object

#### `exportAnalysis(format)`
Exports analysis results.

**Parameters:**
- `format`: Export format ('json', 'markdown', 'tour')

**Returns:**
- Exported data string

## Configuration API

### Configuration Wizard

#### `_run_config_wizard()`
Runs the interactive configuration wizard.

**Features:**
- Project type selection
- Template loading
- Configuration options
- Error handling and validation

#### `_load_project_template(project_type)`
Loads project-specific template.

**Parameters:**
- `project_type`: Type of project (django, fastapi, react, etc.)

**Returns:**
- Template configuration dictionary

#### `_get_suggested_presets(project_type)`
Gets suggested seed presets for project type.

**Parameters:**
- `project_type`: Type of project

**Returns:**
- Dictionary of preset configurations

### Configuration Validation

#### `validate_config_dict(config)`
Validates configuration dictionary.

**Parameters:**
- `config`: Configuration dictionary

**Returns:**
- List of validation errors

#### `_fix_config_errors(config, errors)`
Automatically fixes common configuration errors.

**Parameters:**
- `config`: Configuration dictionary
- `errors`: List of validation errors

**Returns:**
- Fixed configuration dictionary

## Template API

### Template Structure

Each template includes:

```yaml
# Template configuration
hops: 3
seeds: []
seeds_for:
  models:
    - "*/models.py"
    - "*/models/*.py"
  views:
    - "*/views.py"
    - "*/views/*.py"
# ... more presets

include_patterns:
  - "*.py"
  - "*/templates/**/*.html"

exclude_patterns:
  - "**/__pycache__/**"
  - "**/migrations/**"

analysis_options:
  complexity_analysis: true
  side_effects: true
  dependencies: true

ci_integration:
  enabled: true
  platform: "github"
  fail_on_issues: true

ide_integration:
  enabled: true
  type: "vscode"
  gutter_annotations: true
```

### Available Templates

- **django**: Django web applications
- **fastapi**: FastAPI web applications
- **react**: React frontend applications
- **flask**: Flask web applications
- **microservices**: Microservices architecture
- **nodejs**: Node.js applications
- **go**: Go applications
- **java**: Java applications
- **python**: General Python projects

## Examples API

### FastAPI E-commerce

#### `main.py`
FastAPI application with authentication, cart, and order management.

**Features:**
- Async patterns
- Dependency injection
- Pydantic models
- JWT authentication
- REST API design

**Usage:**
```bash
python examples/fastapi_ecommerce/main.py
```

### React Dashboard

#### `src/App.js`
React application with hooks and state management.

**Features:**
- React hooks
- Custom hooks
- State management
- Component architecture
- API integration

**Usage:**
```bash
cd examples/react_dashboard
npm install && npm start
```

### Microservices

#### `order_service.py`
Order service with database and Redis integration.

**Features:**
- Async operations
- Database integration
- Redis caching
- Service communication
- Error handling

**Usage:**
```bash
python examples/microservices/order_service.py
```

### Flask Blog

#### `app.py`
Flask blog application with authentication and admin.

**Features:**
- User authentication
- Post management
- Comments system
- Admin interface
- Background tasks

**Usage:**
```bash
python examples/flask_blog/app.py
```

### Django E-commerce

#### `models.py`, `views.py`
Django application with ORM and admin interface.

**Features:**
- Django ORM
- Model relationships
- View patterns
- Admin interface
- Template inheritance

**Usage:**
```bash
cd examples/django_ecommerce
python manage.py runserver
```

## Error Handling

### Common Errors

#### `ModuleNotFoundError`
- **Cause**: Missing dependencies
- **Solution**: Install required packages with `pip install -r requirements.txt`

#### `ImportError: attempted relative import`
- **Cause**: Running module directly with relative imports
- **Solution**: Use absolute imports or run as module

#### `FileNotFoundError`
- **Cause**: Missing files or incorrect paths
- **Solution**: Check file paths and ensure files exist

### Error Recovery

The system includes automatic error recovery:
- Configuration validation and fixing
- Dependency checking
- Path resolution
- Import error handling

## Performance Considerations

### Optimization Tips

1. **Use Templates**: Leverage project templates for faster setup
2. **Configure Analysis**: Adjust analysis options for your needs
3. **Exclude Patterns**: Use exclude patterns to skip unnecessary files
4. **Seed Selection**: Choose appropriate seeds for your analysis

### Memory Usage

- Repository maps can be large for big codebases
- Use appropriate seed selection to limit analysis scope
- Consider excluding test files and dependencies

## Troubleshooting

### Common Issues

1. **CLI Not Working**
   - Check Python version (3.10+ required)
   - Verify virtual environment activation
   - Install dependencies

2. **Web Demo Not Loading**
   - Check file paths
   - Verify web server is running
   - Check browser console for errors

3. **Templates Not Loading**
   - Verify template files exist
   - Check file permissions
   - Validate YAML syntax

### Getting Help

- Check the README for quick start guide
- Look at examples for usage patterns
- Check GitHub issues for known problems
- Create an issue for new problems

## Version Compatibility

### Python Version
- Minimum: Python 3.10
- Recommended: Python 3.11+

### Dependencies
- See `requirements.txt` for exact versions
- Use virtual environment for isolation
- Update dependencies regularly

### Browser Support
- Web playground: Modern browsers (Chrome, Firefox, Safari, Edge)
- JavaScript: ES6+ features required
- CSS: Modern CSS features used
