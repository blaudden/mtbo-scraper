#!/bin/bash
# Run all tests with verbose output
echo "Running linter..."
uv run ruff check .

echo "Running tests..."
uv run python -m pytest tests/ -v
