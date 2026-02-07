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
The scraper produces a partitioned dataset using an **Umbrella Index** architecture to handle large datasets efficiently.

### File Structure
- `data/events/mtbo_events.json` (Index): The root entry point. Contains metadata and pointers to year-based partition files.
- `data/events/{YYYY}/events.json`: Partitioned event data file for a specific year.

### History Mode
When scraping past years (e.g., last 10 years), the scraper automatically enters **History Mode**:
- **Slower Delays**: 5-15s between requests (vs 1-3s) for stealth.
- **Incremental Saves**: Data is saved to disk after each year completes.
- **Year-by-Year**: Processing happens in 1-year chunks.

### Index Format (`data/events/mtbo_events.json`)
```json
{
  "schema_version": "2.0",
  "last_scraped_at": "2025-01-01T12:00:00+00:00",
  "data_root": "data/events",
  "partitions": {
    "2025": {
      "path": "data/events/2025/events.json",
      "count": 150,
      "last_updated_at": "2025-01-01T12:00:00+00:00"
    }
  },
  "sources": {
    "IOF": {
      "count": 42,
      "last_updated_at": "2025-01-01T12:00:00+00:00"
    }
  }
}
```

## JSON Schema
The output structure is strictly defined by the included `schema.json` file (Version 2.0).

### Key Concepts
- **Umbrella Index**: The top-level `data/events/mtbo_events.json` does not contain events directly. It indexes partitions and provides global source statistics.
- **Partitions**: Events are grouped by year. Each partition file follows the "Event List" schema.
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
- `--output FILE` - Output JSON file path (default: `data/events/mtbo_events.json`)
- `--source SOURCE` - Specific source to scrape (e.g., `SWE`, `NOR`, `IOF`, `MAN`)
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

# Scrape only IOF source
./scrape_now.sh --source IOF
```

See [docs/operation.md](docs/operation.md) for detailed usage and scheduling instructions.
See [docs/design.md](docs/design.md) for architectural details.

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
