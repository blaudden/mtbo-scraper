<!-- Copilot / AI agent instructions for the mtbo-scraper repository -->
# Quick orientation (for AI coding agents)

This repo scrapes Mountain Bike Orienteering event data from various sources (Eventor SWE/NOR/IOF, Manual) and manages a year-partitioned event database.

- Entry point: `src/main.py` — orchestrates sources, handles date ranges, and manages cross-source storage.
- Sources: `src/sources/`
  - `eventor_source.py`: Primary source for Swedish, Norwegian, and IOF Eventor instances.
  - `manual_source.py`: Loads manual events and document references from `manual_events/` directory.
  - `base_source.py`: Abstract base class for all scraper sources.
- Parsing: `src/sources/eventor_parser.py` (class: `EventorParser`) contains HTML heuristics, project-specific mapping rules, and participant list parsing.
- Networking: `src/scraper.py` wraps `cloudscraper` and `undetected-chromedriver` for Cloudflare bypass, uses `pyvirtualdisplay` for headless environments.
- Data model: `src/models.py` (`Event`, `Race`, `Position`, `Area`, `Document`) — use `Event.to_dict()` for JSON serialization.
- Persistence: `src/storage.py` implements an Umbrella Index architecture. `mtbo_events.json` is the root index pointing to year-based partitions in `data/events/{year}/events.json`.

# Important project conventions and patterns

- Standard IDs: `{SourceIndicator}_{CountryCode}_{ShortName}{Year}`
  - Example: `MAN_DNK_MTBOCAMP26` (Manual), `SWE_54361` (Eventor)
- **Targeted Scraping**: Use `--source MAN` to update only manual events quickly and safely.
- Date handling: `src/utils/date_and_time.py` contains shared ISO parsing and timezone-aware formatting.
- Terminology: Follow IOF 3.0 terminology (Snake Case). Use `Position` (lat/lng) and `Area` (lat/lng/polygon).
- Language: Preserve `culture=en-GB` in all Eventor requests to ensure consistent parsing of English content.
- Rate limiting: Respect `delay_range` in `Scraper` to avoid blocks.
- Fingerprinting: `src/utils/fingerprint.py` uses participant names/clubs to detect event updates for SWE/NOR sources.

# Developer workflows (commands and scripts)

- Unified environment: Uses `uv`. Prefer `uv run <command>` for all operations.
- Run scraper:
  - `./scrape_now.sh --start-date=YYYY-MM-DD --end-date=YYYY-MM-DD`
  - Scrapes a specific range and updates the umbrella index.
- Automated pipeline:
  - `./scrape_and_push.sh` / `./scrape_and_push_current.sh`
  - Orchestrates full or partial scrapes, verifies data integrity, and commits changes.
- Tests: `uv run pytest` runs the full suite. Tests use `tests/data` for HTML fixtures.

# What to look at for common tasks (code pointers)

- Add parsing rule: Modify `EventorParser` in `src/sources/eventor_parser.py`. Add tests in `tests/test_parser.py`.
- New Source: Extend `BaseSource` and register in `SOURCE_CONFIGS` in `src/main.py`.
- Model Change: Update `src/models.py` and ensure `to_dict()` matches the JSON schema in `schema.json`.
- Storage logic: `Storage.save()` handles the logic for year-splitting and index updates.

# Guidance for AI edits

- TDD: Always look at existing tests before modifying parsers. Use `pytest` to verify fixes.
- Defensive Parsing: Eventor HTML changes frequently. Use `BeautifulSoup` carefully and handle missing elements gracefully.
- Consistency: Maintain stable git diffs by preserving field order and using ISO 8601 for all timestamps.
- Driver Management: Use the `Scraper` abstraction for all networking; it handles browser fallback automatically.

---
This file is maintained to help AI assistants understand the project's evolving architecture. Update it when making significant structural changes.
