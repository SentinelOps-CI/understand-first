# Understand-First GitHub PR Commenter

A comprehensive GitHub PR analysis service that automatically comments on pull requests with detailed code analysis, policy compliance checks, and visualizations.

## Features

- **Automated PR Analysis**: Analyzes code changes between base and head commits
- **Policy Compliance**: Checks against configurable code quality policies
- **Visual Mini-Maps**: Generates SVG visualizations of code changes
- **Rich Comments**: Posts detailed comments with metrics, checklists, and action items
- **GitHub Integration**: Creates Check Runs and commit statuses
- **Webhook Support**: Responds to GitHub webhook events
- **Artifact Upload**: Uploads analysis artifacts for download

## Quick Start

### Using GitHub Actions

1. Copy the workflow files to your repository:
   ```bash
   cp .github/workflows/understand-first-pr-analysis.yml .github/workflows/
   cp .github/workflows/understand-first-commenter.yml .github/workflows/
   ```

2. The workflows will automatically run on PR events.

### Using Docker

1. Build the Docker image:
   ```bash
   docker build -t understand-first/commenter .
   ```

2. Run the container:
   ```bash
   docker run -e GITHUB_TOKEN=your_token \
              -e REPOSITORY=your-org/your-repo \
              understand-first/commenter \
              --pr-number 123
   ```

### Using Kubernetes

1. Update the repository in `k8s-deployment.yaml`
2. Create the secret with your GitHub token:
   ```bash
   kubectl create secret generic github-secrets \
     --from-literal=token=your_github_token
   ```
3. Deploy:
   ```bash
   kubectl apply -f k8s-deployment.yaml
   ```

## Configuration

### Environment Variables

- `GITHUB_TOKEN`: GitHub personal access token (required)
- `REPOSITORY`: Default repository (owner/repo format)
- `GITHUB_WEBHOOK_SECRET`: Webhook secret for signature verification
- `PORT`: Port for webhook server (default: 8080)

### Policy Rules

The commenter checks against these policies by default:

- **High Complexity**: Functions with complexity > 10
- **Unmanaged Side Effects**: Functions with side effects not properly documented
- **Significant Complexity Increase**: Functions with >50% complexity increase
- **New Hot Paths**: New functions in critical execution paths
- **Breaking Changes**: Functions with signature changes

## API Endpoints

### Webhook Endpoint
- `POST /webhook`: Handles GitHub webhook events
- `GET /health`: Health check
- `GET /ready`: Readiness check

### Manual Analysis
- `POST /analyze`: Trigger manual analysis
  ```json
  {
    "pr_number": 123,
    "repository": "owner/repo",
    "base_commit": "abc123",
    "head_commit": "def456"
  }
  ```

## Comment Format

The commenter posts comprehensive comments including:

- **Analysis Summary**: Overview of changes
- **Mini-Map Visualization**: SVG diagram of code changes
- **Policy Compliance**: Pass/fail status with violations
- **Key Metrics**: Functions added/removed/modified, complexity changes
- **Action Items**: Checklist of required fixes
- **Analysis Summary**: Detailed metrics and risk assessment

## Example Comment

```markdown
## 🔍 Understand-First PR Analysis

### Summary
This PR adds 3 new functions and modifies 2 existing ones...

### 📊 Mini-Map Visualization
[SVG diagram showing code changes]

### ✅ Policy Compliance Checklist
❌ **High Complexity**: Function `processData` has complexity 15 (limit: 10)
✅ **Side Effects**: All side effects properly documented

### 📈 Key Metrics
- **Functions Added**: 3
- **Functions Removed**: 0
- **Functions Modified**: 2
- **Complexity Change**: +5
- **Side Effects**: 1 added, 0 removed

### 🎯 Action Items
- [ ] Fix: Reduce complexity of `processData` function
- [ ] Fix: Add documentation for `updateCache` side effects

### 📊 Analysis Summary
- **Total Functions**: 25
- **Hot Paths**: 2
- **Critical Functions**: 1
- **Risk Score**: 3.2/10
```

## Development

### Local Development

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the commenter:
   ```bash
   python understand_first_commenter.py \
     --github-token your_token \
     --repository owner/repo \
     --pr-number 123
   ```

3. Run the webhook server:
   ```bash
   python webhook_handler.py
   ```

### Testing

Run tests with:
```bash
python -m pytest tests/
```

## Troubleshooting

### Common Issues

1. **Analysis fails**: Check that the `u` CLI tool is installed and accessible
2. **Comment not posted**: Verify GitHub token has `pull_requests: write` permission
3. **Webhook not triggered**: Check webhook URL and secret configuration
4. **Mini-map not generated**: Ensure SVG output is enabled in CLI

### Logs

Enable debug logging:
```bash
export LOG_LEVEL=DEBUG
python webhook_handler.py
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details.
