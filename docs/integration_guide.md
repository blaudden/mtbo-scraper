# MTBO Scraper Integration Instructions

This document provides technical instructions for an AI agent to integrate the [mtbo-scraper](https://github.com/blaudden/mtbo-scraper) data into an Astro-based website.

## 🏗️ Architecture Overview

The scraper produces a partitioned data structure:
1.  **Umbrella Index**: `data/events/mtbo_events.json` - Contains metadata, partition links, and global source statistics.
2.  **Partitions**: `data/events/YYYY/events.json` - Contains the actual event data and source registry for that partition.
3.  **Schema**: `schema.json` - A JSON Schema (v2.0) that validates both the index and the partitions.

## 🎯 Integration Goals

The agent must implement a script (triggered by a webhook) that:
1.  **Syncs Data**: Downloads the latest `data/events/mtbo_events.json` and all relevant partition files.
2.  **Validates**: Ensures the downloaded files adhere to the schema.
3.  **Updates Astro**: Adapts the Astro Content Collections to consume this new schema and partitioned data.

## 🛠️ Step-by-Step Instructions

### 1. File Synchronization Script

Create a script (e.g., `scripts/sync-events.ts`) that:
- Fetches `data/events/mtbo_events.json` from the scraper repository.
- Parses `data/events/mtbo_events.json` to identify active partitions in the `partitions` object.
- Downloads each `path` defined in the partitions (e.g., `data/events/2025/events.json`).
- **Optimization**: Use the `last_updated_at` field in the index to skip unchanged files.

### 2. Validation

- Use the `schema.json` from the scraper repository for validation.
- Implement validation using a library like `ajv` (TS) or `jsonschema` (Python).
- The schema contains a `oneOf` rule: it validates both the `UmbrellaIndex` (data/events/mtbo_events.json) and the `EventListWrapper` (partition files).
- **Example Validation Logic**:
  ```python
  from jsonschema import validate
  with open("schema.json") as s, open("data/events/mtbo_events.json") as d:
      validate(instance=json.load(d), schema=json.load(s))
  ```

### 3. Astro Content Collection Adaptation

Update `src/content/config.ts` to match the **v2.0 schema**.
> [!IMPORTANT]
> The schema follows IOF 3.0 terminology. Significant fields:
> - `id`: String (e.g., `SWE_53106`)
> - `status`: Enum (`Planned`, `Applied`, `Proposed`, `Sanctioned`, `Canceled`, `Rescheduled`)
> - `types`: Array of Strings (e.g., `["World Championships", "World Cup"]`)
> - `races`: Array of `Race` objects (each with `datetimez`, `discipline`, `position`, `urls`, `documents`)
> - `urls` and `documents`: Structured lists with `type`, `title`, and `url`.

### 4. Standalone Strategy

- Commit the JSON files to the Astro repository under `src/content/events/data/`.
- This ensures the website is self-contained and avoids external dependencies during build-time.
- Configure a webhook to trigger the synchronization and commit flow.

### 5. Source Information & Metadata

The scraper aggregates data from multiple sources (Eventor instances). Use this metadata for filtering or UI attribution.

- **Global Sources**: In `data/events/mtbo_events.json`, the `sources` object provides a count and the last update timestamp for each source backend (IOF, SWE, NOR, MAN).
- **Partition Sources**: In each partition file, the `meta.sources` array provides the display names and base URLs (e.g., "Swedish Eventor" -> `https://eventor.orientering.se`).
- **Event IDs**: Every event `id` is prefixed with its source (e.g., `SWE_53106` belongs to the `SWE` source).

## 🔍 Validation Strategy

The agent should:
1.  Run the sync script and verify files are placed correctly.
2.  Validate all JSON files against `schema.json`.
3.  Run `npm run astro check` to ensure the Content Collection schema matches the data.
