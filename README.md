# MTBO Scraper

## Overview

The MTBO Scraper is a Python-based tool designed to collect Mountain Bike Orienteering (MTBO) event data from Eventor instances in Sweden, Norway, and the IOF. It extracts event details, document links, entry statistics, and precise map locations (including embargoed area polygons) into a structured JSON format.

## Installation

Requires **Python 3.12+**. Install using [uv](https://github.com/astral-sh/uv):

```bash
# Install dependencies
uv sync

# (Optional) Install pre-commit hooks
uv run pre-commit install
```

Alternatively, if using pip:

```bash
pip install -e .
```

## Output

The scraper produces a JSON file (default: `mtbo_events.json`) containing a list of events. Each event includes:

- Stable ID (`{Country}-{EventId}`)
- Name, Date, Organizers, Country, Status
- Document links
- Map positions (coordinates and polygons)

## JSON Schema

The output structure is strictly defined by the included `schema.json` file. This schema is based on the **IOF XML 3.0** standard but adapted for JSON with snake_case naming conventions.

### Validation
You can validate the generated `mtbo_events.json` against the schema using any JSON Schema 2020-12 compliant validator.

Example using Python `jsonschema`:

```bash
pip install jsonschema
jsonschema -i mtbo_events.json schema.json
```

### Key Concepts
- **Wrapper**: Top-level object containing `meta` (source systems) and `events` list.
- **Event**: Represents the competition event. ID format: `{Country}_{SourceId}`.
- **Race**: Each event has one or more races (stages).
- **Encryption**: Emails in spam-protected tags are stored as `enc:{base64}`.

## Directory Structure
- `src/sources/`: Scraper logic and parsers (`eventor_source.py`, `eventor_parser.py`, `manual_source.py`).
- `src/utils/`: Shared utilities (`date_and_time.py`, `crypto.py`, `diff.py`).

## Usage

Run the scraper using the provided bash script:

```bash
./scrape_now.sh [OPTIONS]
```

### Options

- `--start-date YYYY-MM-DD` - Start date for scraping (default: 4 weeks ago)
- `--end-date YYYY-MM-DD` - End date for scraping (default: Dec 31st of next year)
- `--output FILE` - Output JSON file path (default: `mtbo_events.json`)
- `--verbose, -v` - Increase logging verbosity (use multiple times: `-v`, `-vv`)
- `--json-logs` - Output logs in JSON format for machine parsing

### Examples

```bash
# Default scraping (last 4 weeks onwards)
./scrape_now.sh

# Scrape specific date range with verbose output
./scrape_now.sh --start-date 2025-06-01 --end-date 2025-08-31 -vv

# JSON logs for automated processing
./scrape_now.sh --json-logs --output events.json
```

See [Docs/operation.md](docs/operation.md) for detailed usage and scheduling instructions.
See [Docs/design.md](docs/design.md) for architectural details.

## Automation

To automate scraping and version control updates, use `scrape_and_push.sh`. This script:

1.  Runs the scraper.
2.  Verifies the output file integrity (size check).
3.  Commits changes to git.
4.  Pushes to the repository.

```bash
./scrape_and_push.sh
```

## Testing

Run the test suite and linters:

```bash
# Run all tests and linters
./run_tests.sh

# Or run individually:
uv run ruff check .          # Linting
uv run ruff format --check . # Format checking
uv run mypy src/             # Type checking
uv run pytest tests/ -v      # Unit tests
```

### Pre-commit Hooks

Install pre-commit hooks to automatically check code quality before commits:

```bash
uv run pre-commit install
```
