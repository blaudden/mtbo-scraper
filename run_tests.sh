#!/bin/bash
# Run all tests with verbose output
echo "Running pre-commit hooks..."
uv run pre-commit run --all-files

echo "Running tests..."
uv run python -m pytest tests/ -v
