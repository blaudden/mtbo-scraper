#!/bin/bash
# scrape_now.sh
# Script to run the MTBO scraper. Suitable for manual use or cron.

# Ensure we are in the project directory
cd "$(dirname "$0")"

# Activate environment and run scraper
# Using 'uv run' handles the virtual environment automatically
echo "Starting scrape at $(date)"
uv run python -m src.main "$@"
EXIT_CODE=$?

echo "Scrape finished at $(date) with exit code $EXIT_CODE"
exit $EXIT_CODE
