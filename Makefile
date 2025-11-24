.PHONY: help lint format check clean install dev-install test

# Default target
help:
	@echo "Available commands:"
	@echo "  lint      - Run ruff linter to check code quality"
	@echo "  format    - Run ruff formatter to format code"
	@echo "  check     - Run both linting and formatting checks"
	@echo "  fix       - Run ruff to automatically fix issues"
	@echo "  clean     - Clean up build artifacts"
	@echo "  install   - Install the package in development mode"
	@echo "  test      - Run tests (if available)"

# Lint the code
lint:
	@echo "Running ruff linter..."
	ruff check noxus_sdk/

# Format the code
format:
	@echo "Running ruff formatter..."
	ruff format noxus_sdk/

# Check both linting and formatting
check: lint format
	@echo "All checks passed!"

# Fix linting and formatting issues automatically
fix:
	@echo "Fixing code issues..."
	ruff check --fix noxus_sdk/
	ruff format noxus_sdk/

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .ruff_cache/
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Install in development mode
install:
	@echo "Installing in development mode..."
	uv pip install -e .

# Install development dependencies
dev-install:
	@echo "Installing development dependencies..."
	uv pip install -e ".[dev]"

test:
	@echo "Running tests..."
	pytest --cov=noxus_sdk --cov-report=term-missing --cov-report=html -n auto