# MTBO Scraper

## Overview

The MTBO Scraper is a Python-based tool designed to collect Mountain Bike Orienteering (MTBO) event data from Eventor instances in Sweden, Norway, and the IOF. It extracts event details, document links, entry statistics, and precise map locations (including embargoed area polygons) into a structured JSON format.

## Output

The scraper produces a JSON file (default: `events.json`) containing a list of events. Each event includes:

- Stable ID (`{Country}-{EventId}`)
- Name, Date, Organizers, Country, Status
- Document links
- Map positions (coordinates and polygons)

## Usage

Run the scraper using the provided bash script:

```bash
./scrape_now.sh [OPTIONS]
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
