# Contributing to Understand-First

Thank you for your interest in contributing to Understand-First! This document provides guidelines and information for contributors.

## Table of Contents

- [Contributing to Understand-First](#contributing-to-understand-first)
  - [Table of Contents](#table-of-contents)
  - [Code of Conduct](#code-of-conduct)
  - [Getting Started](#getting-started)
    - [Prerequisites](#prerequisites)
    - [Development Setup](#development-setup)
  - [Project Structure](#project-structure)
  - [Contributing Guidelines](#contributing-guidelines)
    - [Types of Contributions](#types-of-contributions)
    - [Development Workflow](#development-workflow)
    - [Code Style](#code-style)
    - [Commit Message Format](#commit-message-format)
  - [Pull Request Process](#pull-request-process)
    - [Before Submitting](#before-submitting)
    - [PR Requirements](#pr-requirements)
    - [Review Process](#review-process)
  - [Issue Reporting](#issue-reporting)
    - [Bug Reports](#bug-reports)
    - [Feature Requests](#feature-requests)
  - [Documentation](#documentation)
    - [Writing Guidelines](#writing-guidelines)
    - [Documentation Types](#documentation-types)
  - [Testing](#testing)
    - [Test Types](#test-types)
    - [Running Tests](#running-tests)
    - [Writing Tests](#writing-tests)
  - [Release Process](#release-process)
    - [Version Numbering](#version-numbering)
    - [Release Steps](#release-steps)
  - [Getting Help](#getting-help)
    - [Community](#community)
    - [Resources](#resources)
  - [Recognition](#recognition)

## Code of Conduct

This project follows a code of conduct that we expect all contributors to follow. Please be respectful, inclusive, and constructive in all interactions.

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 16+ (for React examples)
- Git
- Basic understanding of Python, web development, and software engineering practices

### Development Setup

1. **Fork and Clone**
   ```bash
   git clone https://github.com/your-username/understand-first.git
   cd understand-first
   ```

2. **Create Virtual Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```

4. **Verify Installation**
   ```bash
   python u.py --help
   python u.py doctor
   ```

## Project Structure

```
understand-first/
├── cli/                    # Core CLI application
│   └── ucli/
│       ├── analyzers/      # Code analysis modules
│       ├── contracts/      # Contract verification
│       ├── graph/          # Graph generation
│       ├── lens/           # Lens creation and management
│       ├── report/         # Report generation
│       ├── trace/          # Runtime tracing
│       └── main.py         # Main CLI entry point
├── web_demo/               # Web-based playground
│   └── index.html          # Interactive demo
├── examples/               # Real-world examples
│   ├── fastapi_ecommerce/  # FastAPI example
│   ├── react_dashboard/    # React example
│   ├── microservices/      # Microservices example
│   ├── flask_blog/         # Flask example
│   └── django_ecommerce/   # Django example
├── templates/              # Project templates
│   ├── django/             # Django template
│   ├── fastapi/            # FastAPI template
│   ├── react/              # React template
│   └── ...                 # Other templates
├── docs/                   # Documentation
├── tests/                  # Test suite
└── u.py                    # Main entry point
```

## Contributing Guidelines

### Types of Contributions

We welcome contributions in the following areas:

1. **Core Features**
   - Code analysis improvements
   - New analysis types
   - Performance optimizations
   - Bug fixes

2. **Web Playground**
   - UI/UX improvements
   - New analysis features
   - Export functionality
   - Accessibility improvements

3. **Project Templates**
   - New technology templates
   - Template improvements
   - Configuration options

4. **Real-World Examples**
   - New example applications
   - Example improvements
   - Documentation updates

5. **Documentation**
   - README improvements
   - API documentation
   - Tutorials and guides
   - Code comments

6. **Testing**
   - Unit tests
   - Integration tests
   - End-to-end tests
   - Test coverage improvements

### Development Workflow

1. **Create Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make Changes**
   - Write clean, well-documented code
   - Follow existing code style
   - Add tests for new functionality
   - Update documentation as needed

3. **Test Your Changes**
   ```bash
   python u.py doctor
   python -m pytest tests/
   ```

4. **Commit Changes**
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   ```

5. **Push and Create PR**
   ```bash
   git push origin feature/your-feature-name
   ```

### Code Style

- **Python**: Follow PEP 8 guidelines
- **JavaScript**: Use modern ES6+ syntax
- **HTML/CSS**: Use semantic HTML and modern CSS
- **Documentation**: Use clear, concise language
- **Comments**: Explain complex logic and business rules

### Commit Message Format

We use conventional commits:

```
type(scope): description

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes
- `refactor`: Code refactoring
- `test`: Test additions/changes
- `chore`: Maintenance tasks

Examples:
```
feat(web): add export functionality to playground
fix(cli): resolve import error in hot_path.py
docs(readme): update installation instructions
```

## Pull Request Process

### Before Submitting

1. **Test Thoroughly**
   - Run all existing tests
   - Test your changes manually
   - Check for regressions

2. **Update Documentation**
   - Update README if needed
   - Add/update docstrings
   - Update CHANGELOG.md

3. **Check Code Quality**
   - Follow code style guidelines
   - Remove debug code
   - Optimize performance if needed

### PR Requirements

1. **Clear Description**
   - What changes were made
   - Why the changes were necessary
   - How to test the changes

2. **Screenshots/Videos**
   - For UI changes
   - For new features
   - For bug fixes

3. **Test Coverage**
   - New code should have tests
   - Existing tests should pass
   - Coverage should not decrease

4. **Documentation**
   - Update relevant documentation
   - Add examples if applicable
   - Update CHANGELOG.md

### Review Process

1. **Automated Checks**
   - CI/CD pipeline runs
   - Code quality checks
   - Test suite execution

2. **Manual Review**
   - Code review by maintainers
   - Functionality testing
   - Documentation review

3. **Feedback Integration**
   - Address review comments
   - Make requested changes
   - Update PR as needed

## Issue Reporting

### Bug Reports

When reporting bugs, please include:

1. **Environment Information**
   - Python version
   - Operating system
   - Package versions

2. **Steps to Reproduce**
   - Clear, numbered steps
   - Expected vs actual behavior
   - Error messages and logs

3. **Additional Context**
   - Screenshots if applicable
   - Related issues
   - Workarounds if any

### Feature Requests

When requesting features, please include:

1. **Problem Description**
   - What problem does this solve?
   - Who would benefit from this?
   - Current workarounds

2. **Proposed Solution**
   - How should this work?
   - Any design considerations?
   - Alternative approaches

3. **Additional Context**
   - Use cases and examples
   - Related features
   - Implementation ideas

## Documentation

### Writing Guidelines

1. **Clear and Concise**
   - Use simple language
   - Avoid jargon when possible
   - Provide examples

2. **Structure**
   - Use headings and subheadings
   - Include table of contents
   - Use lists and code blocks

3. **Examples**
   - Provide working code examples
   - Include expected outputs
   - Show common use cases

### Documentation Types

1. **API Documentation**
   - Function signatures
   - Parameter descriptions
   - Return value explanations
   - Usage examples

2. **User Guides**
   - Step-by-step instructions
   - Screenshots and diagrams
   - Troubleshooting sections

3. **Developer Documentation**
   - Architecture overview
   - Development setup
   - Contributing guidelines

## Testing

### Test Types

1. **Unit Tests**
   - Test individual functions
   - Mock external dependencies
   - Cover edge cases

2. **Integration Tests**
   - Test component interactions
   - Use real dependencies
   - Test workflows

3. **End-to-End Tests**
   - Test complete user journeys
   - Use real data
   - Test error scenarios

### Running Tests

```bash
# Run all tests
python -m pytest

# Run specific test file
python -m pytest tests/test_analyzer.py

# Run with coverage
python -m pytest --cov=cli

# Run with verbose output
python -m pytest -v
```

### Writing Tests

1. **Test Structure**
   - Arrange: Set up test data
   - Act: Execute the code
   - Assert: Verify results

2. **Test Naming**
   - Use descriptive names
   - Include expected behavior
   - Group related tests

3. **Test Data**
   - Use realistic data
   - Test edge cases
   - Clean up after tests

## Release Process

### Version Numbering

We use [Semantic Versioning](https://semver.org/):
- **MAJOR**: Incompatible API changes
- **MINOR**: Backwards-compatible functionality additions
- **PATCH**: Backwards-compatible bug fixes

### Release Steps

1. **Update Version**
   - Update version in `__init__.py`
   - Update CHANGELOG.md
   - Update README.md if needed

2. **Create Release Branch**
   ```bash
   git checkout -b release/v2.0.0
   ```

3. **Final Testing**
   - Run full test suite
   - Test on multiple platforms
   - Verify documentation

4. **Create Release**
   - Create GitHub release
   - Tag the version
   - Publish to PyPI

## Getting Help

### Community

- **GitHub Issues**: For bug reports and feature requests
- **Discussions**: For questions and general discussion
- **Pull Requests**: For code contributions

### Resources

- **Documentation**: Check the README and docs/
- **Examples**: Look at examples/ for usage patterns
- **Templates**: Check templates/ for project setups

## Recognition

Contributors will be recognized in:
- CONTRIBUTORS.md file
- Release notes
- Project documentation

Thank you for contributing to Understand-First!
