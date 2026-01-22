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
- `--output FILE`: Output JSON file path (default: `mtbo_events.json`).
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

Verbose output for debugging:

```bash
./scrape_now.sh -vv --start-date 2025-01-01
```

JSON logs for automated monitoring:

```bash
./scrape_now.sh --json-logs --output events.json
```

## Scheduling

To run the scraper regularly (e.g., nightly), add a cron job using the script:

```bash
0 3 * * * /path/to/mtbo-scraper/scrape_now.sh >> /path/to/mtbo-scraper/scraper.log 2>&1
```

### Git Automation

To automatically scrape, verify, and push changes to git, use `scrape_and_push.sh`:

```bash
0 3 * * * /path/to/mtbo-scraper/scrape_and_push.sh >> /path/to/mtbo-scraper/scraper.log 2>&1
```

You can also pass arguments to `scrape_and_push.sh`, which will be forwarded to the scraper:

```bash
./scrape_and_push.sh --start-date 2025-01-01
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
2026-01-23 22:44:51 [info] scraper_starting output_file=mtbo_events.json
2026-01-23 22:44:51 [info] date_range_determined start_date=2025-12-26 end_date=2026-12-31
```

#### JSON Format (for AI Agents & Monitoring)

Machine-parseable structured logs:

```bash
./scrape_now.sh --json-logs
```

Output:
```json
{"event": "scraper_starting", "level": "info", "timestamp": "2026-01-23T22:44:51.123Z", "output_file": "mtbo_events.json"}
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

1. **cloudscraper** - Handles most JavaScript challenges automatically
2. **undetected-chromedriver** - For "managed challenge" (opens real browser)

Common issues:

- **Browser window pops up**: This is expected behavior when managed challenge is encountered. The browser opens briefly to solve the Cloudflare challenge, then closes. Cookies are cached for subsequent requests.

- **"Could not start virtual display"**: Install Xvfb: `sudo apt-get install xvfb`

- **Chrome not found**: Install Google Chrome (see Installation section)

- **Infinite loop / hanging**: This was a bug in cloudscraper 3.0.0's `auto_refresh_on_403` feature. It's disabled in our configuration.

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

- Reads event URLs from `tests/data/eventor_test_urls.txt`
- Automatically detects single vs multi-race events
- Downloads main event pages
- Downloads race-specific detail pages (for IOF multi-race events)
- Downloads start/result lists for each race
- Saves files with standardized naming: `{COUNTRY}_{ID}_{type}.html`

**Add new test events:**

1. Add the event URL to `tests/data/eventor_test_urls.txt`
2. Run the fetch script: `uv run python tests/fetch_all_test_data.py`
3. Create corresponding test cases in `tests/test_parser.py` or `tests/test_new_events.py`
