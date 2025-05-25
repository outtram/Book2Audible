# Makefile for Book2Audible

.PHONY: install test clean format lint setup

# Install dependencies and setup environment
install:
	python3 -m venv book2audible-env
	./book2audible-env/bin/pip install --upgrade pip
	./book2audible-env/bin/pip install -r requirements.txt
	./book2audible-env/bin/pip install -e .

# Setup development environment
setup: install
	./book2audible-env/bin/pip install -e ".[dev]"
	python3 -c "import nltk; nltk.download('punkt')"
	mkdir -p data/input data/output data/logs

# Run tests
test:
	./book2audible-env/bin/pytest

# Run tests with coverage
test-cov:
	./book2audible-env/bin/pytest --cov=src --cov-report=html

# Format code
format:
	./book2audible-env/bin/black src/
	./book2audible-env/bin/black book2audible.py

# Lint code
lint:
	./book2audible-env/bin/flake8 src/
	./book2audible-env/bin/mypy src/

# Clean up generated files
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/
	find . -type d -name __pycache__ -delete
	find . -type f -name "*.pyc" -delete

# Test connection to Baseten API
test-connection:
	./book2audible-env/bin/python book2audible.py --test-connection

# Process sample book
demo:
	./book2audible-env/bin/python book2audible.py -i data/input/sample_adhd_book.txt

# Validate configuration
check-config:
	./book2audible-env/bin/python book2audible.py --validate-config

# Show help
help:
	@echo "Book2Audible Makefile Commands:"
	@echo "  install       - Install dependencies"
	@echo "  setup         - Setup development environment"
	@echo "  test          - Run tests"
	@echo "  test-cov      - Run tests with coverage"
	@echo "  format        - Format code with black"
	@echo "  lint          - Lint code with flake8 and mypy"
	@echo "  clean         - Clean generated files"
	@echo "  test-connection - Test Baseten API connection"
	@echo "  demo          - Process sample book"
	@echo "  check-config  - Validate configuration"
