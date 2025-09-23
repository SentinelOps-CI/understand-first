.PHONY: help bootstrap dev run release test clean docker-build docker-run docker-push install uninstall

# Default target
help:
	@echo "Understand-First - Available targets:"
	@echo "  dev       - Set up local development environment"
	@echo "  run       - Run the application locally"
	@echo "  release   - Build and publish artifacts (dry-run supported)"
	@echo "  test      - Run tests"
	@echo "  clean     - Clean build artifacts"
	@echo "  install   - Install the package locally"
	@echo "  uninstall - Uninstall the package"
	@echo "  docker-build - Build Docker image"
	@echo "  docker-run   - Run Docker container"
	@echo "  docker-push   - Push Docker image to registry"

# Development setup
bootstrap: dev

dev:
	@echo "Setting up local development environment..."
	python3 -m pip install --upgrade pip
	pip install -e .
	pip install -r requirements.txt
	@echo "Development environment ready!"
	@echo "Run 'make run' to start the application"

# Run the application
run:
	@echo "Starting Understand-First..."
	@echo "Starting HTTP server on port 8000..."
	uvicorn examples.servers.http_server:app --host 127.0.0.1 --port 8000 &
	@echo "Starting gRPC server on port 50051..."
	python examples/servers/grpc_server.py &
	@echo "Servers started!"
	@echo "HTTP API: http://localhost:8000"
	@echo "gRPC: localhost:50051"
	@echo "Run 'u demo' to see a complete example"

# Build and publish (with dry-run support)
release:
	@echo "Building package..."
	python -m build
	@echo "Package built successfully!"
	@echo "To publish to PyPI:"
	@echo "  twine upload dist/*"
	@echo "To publish to GitHub Container Registry:"
	@echo "  docker build -t ghcr.io/sentinelops-ci/understand-first:latest ."
	@echo "  docker push ghcr.io/sentinelops-ci/understand-first:latest"

# Testing
test: ci-local

ci-local:
	pytest -q

# Clean build artifacts
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf cli/*.egg-info/
	rm -rf __pycache__/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Package management
install:
	pip install -e .

uninstall:
	pip uninstall understand-first -y

# Docker targets
docker-build:
	@echo "Building Docker image..."
	docker build -t understand-first:latest .
	@echo "Docker image built successfully!"

docker-run:
	@echo "Running Docker container..."
	docker run --rm -p 8000:8000 -p 50051:50051 understand-first:latest

docker-push:
	@echo "Pushing Docker image to registry..."
	docker tag understand-first:latest ghcr.io/sentinelops-ci/understand-first:latest
	docker push ghcr.io/sentinelops-ci/understand-first:latest

# Legacy targets for compatibility
tour:
	u scan . -o maps/repo.json || true
	u lens from-seeds --map maps/repo.json -o maps/lens.json || true
	u trace module examples/app/hot_path.py run_hot_path -o traces/tour.json
	u lens merge-trace maps/lens.json traces/tour.json -o maps/lens_merged.json
	u tour maps/lens_merged.json -o tours/local.md

vsix:
	cd ide/vscode/understand-first && npx --yes @vscode/vsce package --no-yarn

wheel:
	python -m build

smoke:
	pytest -q
