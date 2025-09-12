# Context Debt Dashboard

A comprehensive dashboard for tracking and visualizing context debt across codebases, including missing documentation, complex call chains, and hotspots.

## Features

- **Context Debt Metrics**: Track documentation coverage, complexity, side effects, and type hints
- **Hotspot Analysis**: Identify the most complex and frequently called functions
- **Documentation Gaps**: Find missing READMEs, docstrings, type hints, and side effect documentation
- **Call Chain Analysis**: Visualize deep function call chains and their complexity
- **Trends Over Time**: Track how context debt changes over time
- **Web Interface**: Modern, responsive web dashboard
- **API Endpoints**: RESTful API for integration with other tools

## Quick Start

### Using Docker

1. Build the Docker image:
   ```bash
   docker build -t understand-first/dashboard .
   ```

2. Run the container:
   ```bash
   docker run -p 5000:5000 understand-first/dashboard
   ```

3. Open your browser to `http://localhost:5000`

### Using Python

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the dashboard server:
   ```bash
   python dashboard_server.py
   ```

3. Open your browser to `http://localhost:5000`

## Usage

### Command Line Interface

Analyze a codebase and generate dashboard data:

```bash
python context_debt_dashboard.py --analysis-file analysis.json --repository my-repo --output dashboard.html
```

### Web Interface

1. **Upload Analysis Data**: Use the `/api/upload` endpoint to upload analysis results
2. **View Dashboard**: Navigate to the main page to see the dashboard
3. **Filter Data**: Use the repository and time period filters to focus on specific data
4. **Refresh**: Click the refresh button to reload the latest data

### API Endpoints

- `GET /api/dashboard` - Get complete dashboard data
- `GET /api/metrics` - Get context debt metrics
- `GET /api/hotspots` - Get code hotspots
- `GET /api/documentation-gaps` - Get documentation gaps
- `GET /api/call-chains` - Get call chains
- `GET /api/trends` - Get trends over time
- `POST /api/upload` - Upload analysis data
- `GET /health` - Health check

## Configuration

### Environment Variables

- `DB_PATH`: Path to SQLite database file (default: `context_debt.db`)
- `PORT`: Port for web server (default: 5000)
- `DEBUG`: Enable debug mode (default: False)

### Database Schema

The dashboard uses SQLite with the following tables:

- `analysis_runs`: Stores analysis run metadata
- `context_debt_metrics`: Stores context debt metrics
- `call_chains`: Stores function call chains
- `hotspots`: Stores code hotspots
- `documentation_gaps`: Stores documentation gaps

## Metrics Tracked

### Context Debt Metrics

1. **Documentation Coverage**: Percentage of functions with docstrings
2. **High Complexity Functions**: Percentage of functions with complexity > 10
3. **Unmanaged Side Effects**: Percentage of functions with undocumented side effects
4. **Type Hint Coverage**: Percentage of functions with type hints

### Hotspot Analysis

- **Risk Score**: Calculated from complexity, call frequency, and side effects
- **Complexity**: Cyclomatic complexity of functions
- **Call Frequency**: How often functions are called
- **Side Effects**: Number of side effects in functions

### Documentation Gaps

- **Missing READMEs**: Files without README documentation
- **Missing Docstrings**: Functions without docstrings
- **Missing Type Hints**: Functions without type hints
- **Missing Side Effect Docs**: Functions with undocumented side effects

## Customization

### Adding New Metrics

1. Extend the `ContextDebtMetric` dataclass
2. Add analysis logic in `_analyze_context_debt_metrics`
3. Update the database schema if needed
4. Add rendering logic in the web interface

### Customizing Severity Levels

Modify the threshold values in `_analyze_context_debt_metrics`:

```python
metrics.append(ContextDebtMetric(
    name="Documentation Coverage",
    value=doc_coverage,
    threshold=80.0,  # Adjust this threshold
    severity="high" if doc_coverage < 50 else "medium" if doc_coverage < 80 else "low",
    # ...
))
```

## Integration

### With Understand-First CLI

```bash
# Analyze codebase
u analyze --output analysis.json

# Upload to dashboard
curl -X POST http://localhost:5000/api/upload \
  -H "Content-Type: application/json" \
  -d @analysis.json
```

### With GitHub Actions

```yaml
- name: Upload to Context Debt Dashboard
  run: |
    curl -X POST ${{ secrets.DASHBOARD_URL }}/api/upload \
      -H "Content-Type: application/json" \
      -d @analysis.json
```

## Troubleshooting

### Common Issues

1. **Database errors**: Ensure SQLite is installed and the database file is writable
2. **No data showing**: Check that analysis data has been uploaded
3. **Web interface not loading**: Verify Flask is installed and the server is running
4. **API errors**: Check the server logs for detailed error messages

### Debug Mode

Enable debug mode for detailed logging:

```bash
DEBUG=true python dashboard_server.py
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details.
