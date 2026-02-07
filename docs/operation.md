# MTBO Scraper Operation Guide

## Installation

1.  Ensure `uv` is installed.
2.  Clone the repository.
3.  Install Python dependencies:

    ```bash
    uv sync
    ```

4.  **System Requirements** (for Cloudflare bypass):

    - **Google Chrome** - Required by undetected-chromedriver

      ```bash
      # Ubuntu/Debian
      wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
      sudo dpkg -i google-chrome-stable_current_amd64.deb
      ```

    - **Xvfb** - Required for headless/cron environments
      ```bash
      sudo apt-get install xvfb
      ```

## Usage

Run the scraper using the provided bash script:

```bash
./scrape_now.sh [OPTIONS]
```

### Options

- `--start-date YYYY-MM-DD`: Start date for scraping (default: 4 weeks ago).
- `--end-date YYYY-MM-DD`: End date for scraping (default: Dec 31st of current year).
- `--output FILE`: Output Index file path (default: `data/events/mtbo_events.json`). The actual event data is stored in `data/events/{year}/events.json`.
- `--verbose, -v`: Increase logging verbosity. Use multiple times for more detail:
  - No flag: WARNING level (errors and warnings only)
  - `-v`: INFO level (general progress information)
  - `-vv` or more: DEBUG level (detailed execution trace)
- `--json-logs`: Output logs in JSON format for machine parsing and AI agents.

### Examples

Scrape current year (default):

```bash
./scrape_now.sh
```

Scrape a specific range:

```bash
./scrape_now.sh --start-date 2025-06-01 --end-date 2025-08-31
```

Scrape historical data (last 10 years):

```bash
# Automatically triggers history mode (slower delays, year-by-year save)
./scrape_now.sh --start-date 2015-01-01 --end-date 2025-12-31
```

Verbose output for debugging:

```bash
./scrape_now.sh -vv --start-date 2025-01-01
```

JSON logs for automated monitoring:

```bash
./scrape_now.sh --json-logs --output events.json
```

## Scheduling

To run the scraper regularly, add cron jobs using the provided scripts.

### Recommended Schedule

For optimal freshness with minimal load:

```cron
# Full weekly sync - Wednesday at 4:17 AM
17 4 * * 3 /path/to/mtbo-scraper/scrape_and_push.sh >> /path/to/mtbo-scraper/scraper.log 2>&1

# Daily incremental - Every day at 4:33 AM (1 week back, 2 weeks forward)
33 4 * * * /path/to/mtbo-scraper/scrape_and_push_current.sh >> /path/to/mtbo-scraper/scraper.log 2>&1
```

### Scraping Modes

The scraper automatically determines the **fixed** delay range at startup based on the `start_date` (Threshold-Based Logic):

- **Standard Mode** (Recent Events):
  - **Trigger**: `start_date` is within the last 4 weeks (default) or in the future.
  - **Delay**: **1-3 seconds** (Fast).
  - **Behavior**: Suitable for daily/weekly updates.

- **History Mode** (Deep Scrape):
  - **Trigger**: `start_date` is older than 4 weeks ago.
  - **Delay**: **5-15 seconds** (Slow/Stealth).
  - **Behavior**: Designed for scraping long history (e.g., 10+ years) without triggering blocks.

**Universal Behavior**:
Regardless of the mode, the scraper **always** processes data year-by-year and saves incrementally after each year is completed to ensure data safety.

- **Full mode** (`scrape_and_push.sh`): Scrapes entire date range (4 weeks back to Dec 31st of next year)
- **Current mode** (`scrape_and_push_current.sh`): Scrapes only current time window (1 week back, 2 weeks forward)

### Git Automation

Both scripts automatically:
1. Pull the latest source and data from the remote repository (`git pull --rebase`)
2. Run the scraper
3. Commit changes to git if any events were modified
4. Push to remote repository

You can also pass arguments to the scripts, which will be forwarded to the scraper:

```bash
./scrape_and_push.sh --start-date 2025-01-01
./scrape_and_push_current.sh -vv  # Verbose logging
```

```

## Logging

The scraper supports two logging modes: **human-readable** (default) and **JSON** for machine parsing.

### Logging Modes

#### Human-Readable (Default)

Standard console output with timestamps and log levels:

```bash
./scrape_now.sh -v
```

Output:
```
2026-01-23 22:44:51 [info] scraper_starting output_file=data/events/mtbo_events.json
2026-01-23 22:44:51 [info] date_range_determined start_date=2025-12-26 end_date=2026-12-31
```

#### JSON Format (for AI Agents & Monitoring)

Machine-parseable structured logs:

```bash
./scrape_now.sh --json-logs
```

Output:
```json
{"event": "scraper_starting", "level": "info", "timestamp": "2026-01-23T22:44:51.123Z", "output_file": "data/events/mtbo_events.json"}
{"event": "date_range_determined", "level": "info", "timestamp": "2026-01-23T22:44:51.456Z", "start_date": "2025-12-26", "end_date": "2026-12-31"}
```

### Verbosity Levels

- **Default** (no `-v` flag): WARNING level - only errors and warnings
- **`-v`**: INFO level - general progress and completion messages
- **`-vv`** or more: DEBUG level - detailed trace including HTTP requests

Logs are written to:

- Console (Standard Output)
- `scraper.log` file

## Troubleshooting

### Cloudflare Errors

The scraper uses a two-tier Cloudflare bypass:

1. **curl-cffi** - Handles TLS/JA3 impersonation automatically
2. **undetected-chromedriver** - For "managed challenge" (opens real browser)

Common issues:

- **Browser window pops up**: This is expected behavior when managed challenge is encountered. The browser opens briefly to solve the Cloudflare challenge, then closes. Cookies are cached for subsequent requests.

- **"Could not start virtual display"**: Install Xvfb: `sudo apt-get install xvfb`

- **Chrome not found**: Install Google Chrome (see Installation section)

### Missing Map Data

If map positions are missing, verify that the event actually has a map published on Eventor.

## Running Tests

The project includes comprehensive unit tests to verify parsing functionality.

### Run All Tests

```bash
./run_tests.sh
```

This will run the `ruff` linter followed by all `pytest` tests with verbose output.

Or:

```bash
uv run python -m pytest tests/ -v
```

This will automatically run all test files including:

- `tests/test_parser.py` - Core parsing tests (11 tests)
- `tests/test_new_events.py` - Multi-race event tests (5 tests)

### Run Specific Test Files

```bash
# Run only core parser tests
uv run python -m pytest tests/test_parser.py -v

# Run only new event tests
uv run python -m pytest tests/test_new_events.py -v
```

### Run Individual Tests

```bash
# Run a specific test by name
uv run python -m pytest tests/test_parser.py::test_parse_swe_multi -v

## Code Formatting

To automatically format the code to satisfy Ruff's style guidelines (and pass the linter), run:

```bash
uv run ruff format .
```
```

### Test Coverage

Current test coverage includes:

- **Swedish Events**: Single and multi-race events
- **Norwegian Events**: Single-race events
- **IOF Events**: Single and multi-race events with separate detail pages
- **List Parsing**: Entry, start, and result lists with class breakdowns
- **Field Parsing**: Multi-value fields, contact info, email decoding
- **Edge Cases**: Over-splitting prevention, non-ASCII characters

## Test Data Utilities

To update the test data used for unit tests, use the provided utility script. This is useful when you want to refresh the HTML files with the latest content from Eventor or add new test cases.

**Update all test data:**

```bash
uv run python tests/fetch_all_test_data.py
```

This script:

- Reads event URLs from `tests/data/eventor_test_urls.json`
- Automatically detects single vs multi-race events
- Downloads main event pages
- Downloads race-specific detail pages (for IOF multi-race events)
- Downloads start/result lists for each race
- Saves files with standardized naming: `{COUNTRY}_{ID}_{type}.html`

**Add new test events:**

1. Add the event URL (and metadata) to `tests/data/eventor_test_urls.json`
2. Run the fetch script: `uv run python tests/fetch_all_test_data.py`
3. Create corresponding test cases in `tests/test_parser.py` or `tests/test_new_events.py`
