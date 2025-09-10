# Understand-First Project Templates

This directory contains pre-configured templates for common project types, optimized for Understand-First analysis.

## Table of Contents

- [Overview](#overview)
- [Available Templates](#available-templates)
- [Template Structure](#template-structure)
- [Using Templates](#using-templates)
- [Customizing Templates](#customizing-templates)
- [Creating New Templates](#creating-new-templates)
- [Best Practices](#best-practices)

## Overview

Project templates provide pre-configured Understand-First settings optimized for specific technologies and project types. Each template includes:

- **Smart Seed Presets**: Pre-configured analysis seeds for common patterns
- **File Pattern Optimization**: Include/exclude patterns tailored to each technology
- **Analysis Options**: Technology-specific analysis settings
- **CI/CD Integration**: Pre-configured for popular CI platforms
- **IDE Integration**: Settings for common development environments
- **Best Practices**: Follows state-of-the-art software engineering practices

## Available Templates

### Django
**Location**: `django/.understand-first.yml`

**Best For**: Django web applications with models, views, admin, and API development

**Key Features**:
- Django-specific seed presets (models, views, urls, admin, forms, serializers)
- ORM analysis and query optimization
- Template analysis and inheritance tracking
- API development patterns
- Django-specific metrics and monitoring

**Usage**:
```bash
u init --wizard
# Select "Django web application"
```

### FastAPI
**Location**: `fastapi/.understand-first.yml`

**Best For**: Modern async API applications with FastAPI

**Key Features**:
- FastAPI-specific seed presets (routes, models, schemas, services)
- Async pattern analysis
- Dependency injection tracking
- OpenAPI/Swagger integration
- API documentation analysis

**Usage**:
```bash
u init --wizard
# Select "FastAPI web application"
```

### React
**Location**: `react/.understand-first.yml`

**Best For**: React frontend applications with hooks and components

**Key Features**:
- React-specific seed presets (components, pages, hooks, services)
- Component architecture analysis
- Hook usage patterns
- State management analysis
- Bundle analysis and optimization

**Usage**:
```bash
u init --wizard
# Select "React frontend"
```

### Flask
**Location**: `flask/.understand-first.yml`

**Best For**: Flask web applications with blueprints and extensions

**Key Features**:
- Flask-specific seed presets (blueprints, routes, models, forms, templates)
- Blueprint organization analysis
- Template inheritance tracking
- Form handling patterns
- Flask extension analysis

**Usage**:
```bash
u init --wizard
# Select "Flask web application"
```

### Microservices
**Location**: `microservices/.understand-first.yml`

**Best For**: Distributed systems with multiple services

**Key Features**:
- Microservices-specific seed presets (services, clients, models, API)
- Service communication analysis
- Distributed pattern tracking
- Contract testing integration
- Infrastructure analysis

**Usage**:
```bash
u init --wizard
# Select "Microservices architecture"
```

### Node.js
**Location**: `nodejs/.understand-first.yml`

**Best For**: Node.js applications with Express or other frameworks

**Key Features**:
- Node.js-specific seed presets (routes, controllers, models, middleware)
- Express pattern analysis
- Middleware chain tracking
- Module dependency analysis
- Package management analysis

**Usage**:
```bash
u init --wizard
# Select "Node.js application"
```

### Go
**Location**: `go/.understand-first.yml`

**Best For**: Go applications and microservices

**Key Features**:
- Go-specific seed presets (handlers, models, services, repositories)
- Interface analysis
- Goroutine analysis
- Concurrency pattern tracking
- Go module analysis

**Usage**:
```bash
u init --wizard
# Select "Go application"
```

### Java
**Location**: `java/.understand-first.yml`

**Best For**: Java applications with Spring or other frameworks

**Key Features**:
- Java-specific seed presets (controllers, services, models, repositories)
- Spring pattern analysis
- Annotation analysis
- Inheritance analysis
- Maven/Gradle integration

**Usage**:
```bash
u init --wizard
# Select "Java application"
```

### Python
**Location**: `python/.understand-first.yml`

**Best For**: General Python applications and libraries

**Key Features**:
- General Python seed presets (main, tests, utils)
- Import analysis
- Class analysis
- Function analysis
- Package management analysis

**Usage**:
```bash
u init --wizard
# Select "Python project"
```

## Template Structure

Each template follows a consistent structure:

```yaml
# Basic Configuration
hops: 3
seeds: []

# Project-specific seed presets
seeds_for:
  # Core components
  models: ["*/models.py", "*/models/*.py"]
  views: ["*/views.py", "*/views/*.py"]
  # ... more presets

# File Patterns
include_patterns:
  - "*.py"
  - "*/templates/**/*.html"

exclude_patterns:
  - "**/__pycache__/**"
  - "**/node_modules/**"

# Analysis Options
analysis_options:
  complexity_analysis: true
  side_effects: true
  dependencies: true

# CI/CD Integration
ci_integration:
  enabled: true
  platform: "github"
  fail_on_issues: true

# IDE Integration
ide_integration:
  enabled: true
  type: "vscode"
  gutter_annotations: true
```

## Using Templates

### Interactive Setup

The easiest way to use templates is through the configuration wizard:

```bash
u init --wizard
```

This will:
1. Show available project types
2. Load the appropriate template
3. Allow customization of settings
4. Generate the configuration file

### Manual Setup

You can also copy and customize templates manually:

```bash
# Copy template to your project
cp templates/django/.understand-first.yml ./

# Customize the configuration
# Edit .understand-first.yml as needed
```

### Template Features

Each template includes:

#### Smart Seed Presets
- **Technology-Specific**: Tailored to each framework's patterns
- **Common Scenarios**: Bug fixing, feature development, performance
- **Comprehensive Coverage**: 16+ presets per template

#### File Pattern Optimization
- **Include Patterns**: Focus on relevant files
- **Exclude Patterns**: Skip build artifacts and dependencies
- **Performance**: Optimized for fast analysis

#### Analysis Options
- **Complexity Analysis**: Cyclomatic complexity calculation
- **Side Effects**: Detection of side effects
- **Dependencies**: Function and module dependencies
- **Technology-Specific**: Framework-specific analysis

#### CI/CD Integration
- **GitHub Actions**: Pre-configured workflows
- **GitLab CI**: GitLab pipeline integration
- **Jenkins**: Jenkins job configuration
- **Failure Handling**: Configurable failure conditions

#### IDE Integration
- **VS Code**: Extension integration
- **PyCharm**: Plugin support
- **Vim**: Vim plugin integration
- **Gutter Annotations**: Inline code annotations

## Customizing Templates

### Basic Customization

1. **Modify Seed Presets**:
   ```yaml
   seeds_for:
     custom_preset:
       - "custom/path/*.py"
       - "another/path/*.js"
   ```

2. **Adjust File Patterns**:
   ```yaml
   include_patterns:
     - "*.py"
     - "*.js"
     - "custom/**/*.ts"
   
   exclude_patterns:
     - "**/build/**"
     - "**/dist/**"
   ```

3. **Configure Analysis Options**:
   ```yaml
   analysis_options:
     complexity_analysis: true
     side_effects: true
     custom_analysis: true
   ```

### Advanced Customization

1. **Add Custom Metrics**:
   ```yaml
   metrics:
     enabled: true
     custom_metrics:
       - "performance"
       - "security"
       - "maintainability"
   ```

2. **Configure CI/CD**:
   ```yaml
   ci_integration:
     enabled: true
     platform: "custom"
     custom_config:
       pipeline: "custom-pipeline.yml"
   ```

3. **Add IDE Support**:
   ```yaml
   ide_integration:
     enabled: true
     type: "custom"
     custom_settings:
       theme: "dark"
       annotations: true
   ```

## Creating New Templates

### Template Requirements

1. **File Structure**:
   ```
   templates/
   └── your_template/
       └── .understand-first.yml
   ```

2. **Naming Convention**:
   - Use lowercase with underscores
   - Be descriptive and clear
   - Avoid special characters

3. **Configuration File**:
   - Must be named `.understand-first.yml`
   - Must be valid YAML
   - Must include required sections

### Template Development

1. **Create Directory**:
   ```bash
   mkdir templates/your_template
   ```

2. **Create Configuration**:
   ```yaml
   # templates/your_template/.understand-first.yml
   hops: 3
   seeds: []
   
   seeds_for:
     main:
       - "main.py"
       - "app.py"
   
   include_patterns:
     - "*.py"
   
   exclude_patterns:
     - "**/__pycache__/**"
   
   analysis_options:
     complexity_analysis: true
     side_effects: true
   
   ci_integration:
     enabled: true
     platform: "github"
   
   ide_integration:
     enabled: true
     type: "vscode"
   ```

3. **Test Template**:
   ```bash
   # Test template loading
   python -c "from cli.ucli.main import _load_project_template; print(_load_project_template('your_template'))"
   ```

4. **Update Documentation**:
   - Add to this README
   - Update main README
   - Add usage examples

### Template Best Practices

1. **Comprehensive Coverage**:
   - Include all common patterns
   - Cover different scenarios
   - Provide multiple presets

2. **Performance Optimization**:
   - Exclude unnecessary files
   - Use efficient patterns
   - Minimize analysis scope

3. **Documentation**:
   - Document all presets
   - Explain configuration options
   - Provide usage examples

4. **Testing**:
   - Test with real projects
   - Verify all features work
   - Check performance impact

## Best Practices

### Choosing the Right Template

1. **Match Your Technology**:
   - Use Django template for Django projects
   - Use React template for React projects
   - Use Python template for general Python projects

2. **Consider Project Size**:
   - Large projects: Use comprehensive templates
   - Small projects: Use minimal templates
   - Microservices: Use microservices template

3. **Think About Team**:
   - Team preferences
   - Existing workflows
   - CI/CD requirements

### Template Customization

1. **Start with Defaults**:
   - Use template as starting point
   - Customize gradually
   - Test changes incrementally

2. **Document Changes**:
   - Keep track of customizations
   - Document reasons for changes
   - Share with team

3. **Regular Updates**:
   - Update templates regularly
   - Incorporate new features
   - Remove deprecated options

### Performance Optimization

1. **File Patterns**:
   - Exclude build artifacts
   - Skip test files if not needed
   - Use specific patterns

2. **Analysis Scope**:
   - Limit hops for large projects
   - Use focused seed presets
   - Disable unnecessary analysis

3. **Caching**:
   - Enable caching when available
   - Use incremental analysis
   - Optimize CI/CD runs

## Troubleshooting

### Common Issues

1. **Template Not Loading**:
   - Check file path
   - Verify YAML syntax
   - Check file permissions

2. **Configuration Errors**:
   - Validate YAML syntax
   - Check required fields
   - Use configuration wizard

3. **Performance Issues**:
   - Adjust file patterns
   - Reduce analysis scope
   - Check system resources

### Getting Help

1. **Check Documentation**:
   - Read this README
   - Check main documentation
   - Look at examples

2. **Test with Examples**:
   - Use provided examples
   - Compare configurations
   - Test different settings

3. **Community Support**:
   - GitHub issues
   - Discussions
   - Pull requests

## Contributing

### Adding New Templates

1. **Choose Technology**:
   - Pick a technology not yet covered
   - Ensure it's widely used
   - Consider community needs

2. **Research Patterns**:
   - Study common patterns
   - Look at best practices
   - Analyze existing projects

3. **Create Template**:
   - Follow template structure
   - Include comprehensive presets
   - Test thoroughly

4. **Submit PR**:
   - Follow contributing guidelines
   - Include documentation
   - Provide examples

### Improving Existing Templates

1. **Identify Issues**:
   - Look for missing patterns
   - Check for outdated options
   - Consider performance improvements

2. **Make Changes**:
   - Update configuration
   - Test thoroughly
   - Document changes

3. **Submit PR**:
   - Explain changes
   - Include tests
   - Update documentation

## Next Steps

After setting up your template:

1. **Run Analysis**:
   - Scan your codebase
   - Create understanding lens
   - Generate tours

2. **Customize Further**:
   - Adjust settings as needed
   - Add custom presets
   - Optimize performance

3. **Share with Team**:
   - Document your setup
   - Train team members
   - Establish workflows

4. **Contribute Back**:
   - Share improvements
   - Create new templates
   - Help others

Happy templating! 🚀
