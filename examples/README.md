# Understand-First Examples

This directory contains comprehensive real-world examples demonstrating Understand-First with modern software patterns and technologies.

## Table of Contents

- [Overview](#overview)
- [FastAPI E-commerce](#fastapi-e-commerce)
- [React Dashboard](#react-dashboard)
- [Microservices Architecture](#microservices-architecture)
- [Flask Blog](#flask-blog)
- [Django E-commerce](#django-e-commerce)
- [Getting Started](#getting-started)
- [Understanding the Examples](#understanding-the-examples)

## Overview

These examples showcase how Understand-First helps developers understand complex, real-world codebases across different technologies and architectural patterns.

### What Makes These Examples Special

- **Real-World Complexity**: Not toy examples, but production-ready patterns
- **Modern Technologies**: Latest frameworks and best practices
- **Comprehensive Coverage**: Multiple languages, frameworks, and architectures
- **Well-Documented**: Clear explanations and usage instructions
- **Interactive Analysis**: Each example can be analyzed with Understand-First

## FastAPI E-commerce

**Location**: `fastapi_ecommerce/`

A modern async e-commerce API built with FastAPI, demonstrating:

### Features
- **Async Patterns**: Modern Python async/await usage
- **Dependency Injection**: FastAPI's dependency system
- **Authentication**: JWT-based authentication
- **Data Validation**: Pydantic models with validation
- **API Design**: RESTful API with proper HTTP status codes
- **Error Handling**: Comprehensive error handling and logging

### Key Components
- `main.py`: FastAPI application with routes and middleware
- **Models**: Pydantic models for request/response validation
- **Services**: Business logic separated into service classes
- **Authentication**: JWT token generation and validation
- **Database**: In-memory storage (easily replaceable with real DB)

### Running the Example
```bash
# Install dependencies
pip install fastapi uvicorn pydantic

# Run the server
python examples/fastapi_ecommerce/main.py

# Server will start on http://localhost:8000
# API documentation available at http://localhost:8000/docs
```

### Understanding with Understand-First
```bash
# Scan the FastAPI example
u scan examples/fastapi_ecommerce -o maps/fastapi_repo.json

# Create lens focusing on API routes
u lens from-seeds --seed main --map maps/fastapi_repo.json -o maps/fastapi_lens.json

# Generate understanding tour
u tour maps/fastapi_lens.json -o tours/fastapi_tour.md
```

## React Dashboard

**Location**: `react_dashboard/`

A modern React dashboard application demonstrating:

### Features
- **React Hooks**: useState, useEffect, useCallback, useMemo
- **Custom Hooks**: Reusable logic extraction
- **State Management**: Local state and context
- **Component Architecture**: Functional components with props
- **API Integration**: Fetching data from external APIs
- **Responsive Design**: Mobile-friendly interface

### Key Components
- `src/App.js`: Main application component
- `src/App.css`: Styling and responsive design
- `package.json`: Dependencies and scripts
- **Custom Hooks**: Data fetching and state management
- **Components**: Reusable UI components

### Running the Example
```bash
# Install dependencies
cd examples/react_dashboard
npm install

# Start development server
npm start

# Application will open in browser at http://localhost:3000
```

### Understanding with Understand-First
```bash
# Scan the React example
u scan examples/react_dashboard -o maps/react_repo.json

# Create lens focusing on components
u lens from-seeds --seed App --map maps/react_repo.json -o maps/react_lens.json

# Generate understanding tour
u tour maps/react_lens.json -o tours/react_tour.md
```

## Microservices Architecture

**Location**: `microservices/`

A distributed system demonstrating microservices patterns:

### Features
- **Service Communication**: HTTP and gRPC communication
- **Database Integration**: Async database operations
- **Caching**: Redis for performance
- **Event-Driven**: Asynchronous event handling
- **Error Handling**: Circuit breaker patterns
- **Monitoring**: Logging and metrics

### Key Components
- `user_service.py`: User management service
- `order_service.py`: Order processing service
- **Database**: Async PostgreSQL integration
- **Caching**: Redis for session and data caching
- **Communication**: HTTP clients and gRPC

### Running the Example
```bash
# Install dependencies
pip install aiohttp asyncpg redis pydantic

# Run user service
python examples/microservices/user_service.py

# Run order service (in another terminal)
python examples/microservices/order_service.py
```

### Understanding with Understand-First
```bash
# Scan the microservices
u scan examples/microservices -o maps/microservices_repo.json

# Create lens focusing on service communication
u lens from-seeds --seed user_service --map maps/microservices_repo.json -o maps/microservices_lens.json

# Generate understanding tour
u tour maps/microservices_lens.json -o tours/microservices_tour.md
```

## Flask Blog

**Location**: `flask_blog/`

A complete blog application built with Flask:

### Features
- **User Authentication**: Login, registration, and session management
- **Content Management**: Post creation, editing, and deletion
- **Comments System**: Nested comments with approval workflow
- **Admin Interface**: Content management and user administration
- **Background Tasks**: Celery for async operations
- **Caching**: Redis for performance optimization

### Key Components
- `app.py`: Main Flask application
- **Models**: SQLAlchemy models for database
- **Forms**: WTForms for form handling
- **Templates**: Jinja2 templates for rendering
- **Services**: Business logic separation
- **Tasks**: Celery background tasks

### Running the Example
```bash
# Install dependencies
pip install flask flask-sqlalchemy flask-login flask-wtf celery redis

# Run the application
python examples/flask_blog/app.py

# Application will start on http://localhost:5000
```

### Understanding with Understand-First
```bash
# Scan the Flask example
u scan examples/flask_blog -o maps/flask_repo.json

# Create lens focusing on routes and models
u lens from-seeds --seed app --map maps/flask_repo.json -o maps/flask_lens.json

# Generate understanding tour
u tour maps/flask_lens.json -o tours/flask_tour.md
```

## Django E-commerce

**Location**: `django_ecommerce/`

A complete Django e-commerce application:

### Features
- **Django ORM**: Model relationships and queries
- **Admin Interface**: Built-in admin for content management
- **View Patterns**: Class-based and function-based views
- **Template System**: Template inheritance and rendering
- **Form Handling**: Django forms with validation
- **Authentication**: User authentication and permissions

### Key Components
- `models.py`: Django models for database
- `views.py`: View functions and classes
- `urls.py`: URL routing configuration
- `admin.py`: Admin interface configuration
- **Templates**: HTML templates with Django syntax
- **Forms**: Django forms for user input

### Running the Example
```bash
# Install dependencies
pip install django djangorestframework

# Run migrations
cd examples/django_ecommerce
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run development server
python manage.py runserver

# Application will start on http://localhost:8000
# Admin interface available at http://localhost:8000/admin
```

### Understanding with Understand-First
```bash
# Scan the Django example
u scan examples/django_ecommerce -o maps/django_repo.json

# Create lens focusing on models and views
u lens from-seeds --seed models --map maps/django_repo.json -o maps/django_lens.json

# Generate understanding tour
u tour maps/django_lens.json -o tours/django_tour.md
```

## Getting Started

### Prerequisites

1. **Python 3.10+**
2. **Node.js 16+** (for React example)
3. **Required Python packages**:
   ```bash
   pip install -r requirements.txt
   ```

### Quick Start

1. **Choose an Example**
   - Pick the technology you're most familiar with
   - Or choose one you want to learn

2. **Run the Example**
   - Follow the specific instructions for each example
   - Make sure all dependencies are installed

3. **Analyze with Understand-First**
   - Use the provided commands to analyze the code
   - Explore the generated tours and maps

4. **Experiment**
   - Modify the code and re-analyze
   - Try different seed functions
   - Explore the generated understanding artifacts

## Understanding the Examples

### What to Look For

When analyzing these examples with Understand-First, pay attention to:

1. **Architecture Patterns**
   - How components are organized
   - Dependencies between modules
   - Data flow through the system

2. **Code Quality**
   - Complexity metrics
   - Side effects and dependencies
   - Error handling patterns

3. **Best Practices**
   - Modern language features
   - Framework-specific patterns
   - Security considerations

### Analysis Strategies

1. **Start with Main Entry Points**
   - `main.py`, `app.py`, `App.js`
   - These show the overall structure

2. **Follow Data Flow**
   - Trace how data moves through the system
   - Identify key transformation points

3. **Look for Patterns**
   - Authentication flows
   - Error handling
   - Database interactions

4. **Compare Technologies**
   - How do different frameworks solve similar problems?
   - What are the trade-offs?

### Common Analysis Commands

```bash
# Basic analysis
u scan examples/[example_name] -o maps/[example]_repo.json
u lens from-seeds --seed [main_function] --map maps/[example]_repo.json -o maps/[example]_lens.json
u tour maps/[example]_lens.json -o tours/[example]_tour.md

# Focus on specific patterns
u lens from-seeds --seed [pattern_function] --map maps/[example]_repo.json -o maps/[pattern]_lens.json

# Compare different examples
u lens from-seeds --seed [common_pattern] --map maps/[example1]_repo.json -o maps/compare_lens.json
```

## Learning Path

### Beginner
1. Start with **Flask Blog** (simpler, more traditional)
2. Move to **Django E-commerce** (more structured)
3. Try **React Dashboard** (frontend patterns)

### Intermediate
1. Explore **FastAPI E-commerce** (modern async patterns)
2. Study **Microservices** (distributed systems)
3. Compare different approaches

### Advanced
1. Analyze all examples together
2. Look for cross-cutting concerns
3. Identify common patterns and anti-patterns
4. Consider how to apply these patterns in your own projects

## Contributing

### Adding New Examples

1. **Choose a Technology**: Pick a framework or language not yet covered
2. **Create Realistic Example**: Build something that demonstrates real-world patterns
3. **Document Thoroughly**: Include setup instructions and analysis commands
4. **Test with Understand-First**: Make sure it can be analyzed effectively
5. **Submit Pull Request**: Follow the contributing guidelines

### Improving Existing Examples

1. **Add Features**: Enhance existing examples with more patterns
2. **Fix Issues**: Report and fix bugs
3. **Improve Documentation**: Make instructions clearer
4. **Add Tests**: Ensure examples work reliably

## Troubleshooting

### Common Issues

1. **Dependencies Not Found**
   - Make sure you're in a virtual environment
   - Install all required packages
   - Check Python/Node.js versions

2. **Examples Won't Start**
   - Check for port conflicts
   - Verify database connections
   - Look at error messages

3. **Analysis Fails**
   - Check file paths
   - Verify seed function names
   - Look at generated error logs

### Getting Help

- Check the main README for general issues
- Look at GitHub issues for known problems
- Create an issue if you find a new problem
- Ask questions in discussions

## Next Steps

After exploring these examples:

1. **Apply to Your Projects**: Use Understand-First on your own codebases
2. **Create Templates**: Build project templates for your preferred technologies
3. **Contribute**: Help improve Understand-First and these examples
4. **Share**: Tell others about your experience with Understand-First

Happy exploring! 🚀
