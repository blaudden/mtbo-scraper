# MTBO Scraper Design Document

## Overview

The MTBO Scraper is a Python-based tool designed to collect Mountain Bike Orienteering event data from three Eventor instances:

- Sweden (https://eventor.orientering.se)
- Norway (https://eventor.orientering.no)
- IOF (https://eventor.orienteering.org)

The scraper extracts event details, document links, entry statistics, and precise map locations (including embargoed area polygons) into a structured JSON format.

## Architecture

### Components

1.  **Scraper (`src.scraper.Scraper`)**:

    - Handles HTTP requests.
    - Uses `cloudscraper` to bypass Cloudflare protection.
    - Implements rate limiting and exponential backoff.

2.  **Parser (`src.parsers.EventorParser`)**:

    - Parses HTML content using `BeautifulSoup` and `lxml`.
    - **List Parsing**: Extracts basic event info from the event list page.
    - **Detail Parsing**: Extracts detailed properties, document links, and statistics.
    - **Map Extraction**: Implements a specific recipe to extract map coordinates and polygons from the `input.options` JSON embedded in the page.

3.  **Models (`src.models`)**:

    - `Event`: Data class representing a single event.
    - `MapPosition`: Data class representing a specific competition leg (etapp) location.

4.  **Storage (`src.storage.Storage`)**:

    - Manages persistence to `mtbo_events.json`.
    - Merges new data with existing data to prevent duplicates while updating records.

5.  **Controller (`src.main`)**:
    - CLI entry point using `click`.
    - Orchestrates the scraping flow: List -> Details -> Storage.

## Data Flow

1.  **CLI** receives start/end dates.
2.  **Scraper** fetches the event list for each configured country.
3.  **Parser** extracts event summaries.
4.  **Scraper** fetches detail pages for each event.
5.  **Parser** extracts full details and map data.
6.  **Storage** saves the aggregated list to `mtbo_events.json`.

## Map Extraction Logic

The scraper looks for hidden `<input class="options">` elements within `.mapPosition` containers. These inputs contain a JSON string with:

- `latitude` / `longitude` (Event center)
- `polygonVertices` (Embargoed area polygon)

This data is normalized to a consistent `[lon, lat]` format for GeoJSON compatibility.
