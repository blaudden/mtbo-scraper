<!-- Copilot / AI agent instructions for the mtbo-scraper repository -->
# Quick orientation (for AI coding agents)

This repo scrapes Mountain Bike Orienteering event data from Eventor (SWE/NOR) and IOF pages and writes a single JSON file `mtbo_events.json`.

- Entry point: `src/main.py` — orchestrates sources, parsing and storage.
- Sources: `src/sources/eventor.py` implements fetching of lists and details (per-country configuration found in `src/main.py`).
- Parsing: `src/parsers.py` (class: `EventorParser`) contains the HTML heuristics and many project-specific rules (date parsing, "HERE" map recipe, splitting concatenated organizer names, Livelox extraction).
- Networking: `src/scraper.py` wraps `cloudscraper` with rate-limiting, English-content `culture=en-GB` parameter and retry/backoff behavior.
- Data model: `src/models.py` (Event, Race, MapPosition, Document) — use `Event.to_dict()` for serialization.
- Persistence: `src/storage.py` loads existing JSON (basic loader) and `save()` merges new events then writes sorted JSON.

# Important project conventions and patterns

- Event IDs: canonical id format is `{Country}-{EventId}` (e.g. `SWE-50597`). Do not change this format.
- Date range limits: `src/main.py` enforces a maximum date range of ~15 months (used by CLI defaults and validation).
- Map extraction: parser expects map position inputs under `.mapPosition input.options` and decodes JSON / polygons to GeoJSON-like [lon, lat] arrays.
- Language: All requests intentionally request English pages (`culture=en-GB`) — preserve that behavior when adding HTTP calls.
- Rate limiting: `Scraper._wait_for_rate_limit()` adds randomized delays; keep this polite behavior when adding fetchers.

# Developer workflows (commands and scripts)

- Run scraper interactively (recommended wrapper):
  - `./scrape_now.sh --start-date=YYYY-MM-DD --end-date=YYYY-MM-DD --output mtbo_events.json`
  - `scrape_now.sh` uses `uv run python -m src.main` to execute with the project's Python environment.

- Automated scrape + push (includes sanity checks on file size):
  - `./scrape_and_push.sh` — runs the scraper, verifies output size (against git HEAD or a minimum), then commits & pushes changes.

- Tests: `./run_tests.sh` uses the `uv` wrapper to run pytest: `uv run python -m pytest tests/ -v`.
  - Tests and static sample pages are in `tests/data` and test modules in `tests/`.

- Dependencies: `pyproject.toml` and `requirements.txt` list runtime libs (beautifulsoup4, cloudscraper, lxml, click, requests). Use the same set when adding features.

# What to look at for common tasks (code pointers)

- Add a new source adapter: copy pattern from `src/sources/eventor.py` and register it in `EVENTOR_CONFIGS` in `src/main.py` (the main script instantiates sources using `EventorSource(country, url)`).
- Change parsing rules: update `EventorParser` in `src/parsers.py`. Many functions are intentionally defensive (split_multi_value_field, parse_date_to_iso, _extract_map_positions) — follow the same defensive style and add unit tests in `tests/`.
- Network changes: alter `src/scraper.py` to preserve `culture` parameter and the randomized rate limiting/backoff.
- Storage/format changes: update `Event.to_dict()` in `src/models.py` and `Storage.save()`; `save()` currently merges based on `id` keys and sorts by `start_date`.

# Examples to cite in modifications

- Date parsing example: `EventorParser.parse_date_to_iso()` — supports multiple human-readable formats and falls back to the original string.
- Map polygon extraction example: `EventorParser._extract_map_positions()` — loads JSON from `input.value`, converts polygon vertices into [[lon, lat],...] and closes rings.
- Rate-limited GET: `Scraper.get(url, params=None, retries=3)` uses `cloudscraper.create_scraper()` and exponential backoff.

# Non-obvious behaviors and gotchas

- `scrape_and_push.sh` refuses to commit if the new `mtbo_events.json` is significantly smaller (>10% shrink) than the git HEAD copy — this is an integrity safeguard.
- `Storage.load()` currently returns dicts (loaded items) and the loader is simplified; when changing storage behavior, run tests to ensure merge semantics remain intact.
- Tests rely on fixtures in `tests/data/` (sample Eventor HTML). When changing parsers, update or add test fixtures there.

# Guidance for AI edits

- Be conservative: prefer small, well-tested changes. Add unit tests for parser changes and run `./run_tests.sh`.
- Keep external request behavior identical (headers, culture param, rate limiting). Breaking request patterns can change parsing results.
- Preserve event id and output JSON schema (see `Event.to_dict()`); downstream consumers depend on these keys.

# Quick checklist (before opening a PR)

- Run `./run_tests.sh` and ensure all tests pass.
- If touching network code, smoke-run `./scrape_now.sh` for a small date range and inspect `mtbo_events.json` and `scraper.log`.
- Update or add tests in `tests/` and sample HTML in `tests/data/` for parsing changes.

---

If anything above is unclear or you want examples for a specific change (e.g., adding a new source adapter or extending map parsing), tell me which area and I will expand this file with a short, focused example patch.
