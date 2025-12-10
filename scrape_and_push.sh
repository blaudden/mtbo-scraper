#!/bin/bash
# scrape_and_push.sh
# Scrapes MTBO events, verifies output, and pushes to git.

# Configuration
OUTPUT_FILE="mtbo_events.json"
MIN_SIZE_BYTES=100 # Minimum expected size in bytes (safeguard)
LOG_FILE="scraper.log"

# Ensure we are in the project directory
cd "$(dirname "$0")"

# 1. Run Scraper
echo "Starting scrape at $(date)" >> "$LOG_FILE"
./scrape_now.sh --output "$OUTPUT_FILE" "$@" >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "Scraper failed with exit code $EXIT_CODE. Aborting." >> "$LOG_FILE"
    exit $EXIT_CODE
fi

# 2. Verify Output
if [ ! -f "$OUTPUT_FILE" ]; then
    echo "Output file $OUTPUT_FILE missing. Aborting." >> "$LOG_FILE"
    exit 1
fi

# Check against previous file size if it exists (using git version)
if git show HEAD:"$OUTPUT_FILE" > /dev/null 2>&1; then
    PREV_SIZE=$(git show HEAD:"$OUTPUT_FILE" | wc -c)
    # Allow 10% shrinkage
    MIN_EXPECTED_SIZE=$((PREV_SIZE * 90 / 100))
    
    FILE_SIZE=$(stat -c%s "$OUTPUT_FILE")
    
    if [ "$FILE_SIZE" -lt "$MIN_EXPECTED_SIZE" ]; then
        echo "Output file size ($FILE_SIZE bytes) shrunk significantly from previous ($PREV_SIZE bytes). Aborting commit." >> "$LOG_FILE"
        exit 1
    fi
else
    # Fallback for first run
    FILE_SIZE=$(stat -c%s "$OUTPUT_FILE")
    if [ "$FILE_SIZE" -lt "$MIN_SIZE_BYTES" ]; then
        echo "Output file size ($FILE_SIZE bytes) is suspiciously small. Aborting commit." >> "$LOG_FILE"
        exit 1
    fi
fi

# 3. Git Commit and Push
# Check if there are changes
if git diff --quiet "$OUTPUT_FILE"; then
    echo "No changes to $OUTPUT_FILE." >> "$LOG_FILE"
else
    echo "Changes detected. Committing..." >> "$LOG_FILE"
    git add "$OUTPUT_FILE"
    git commit -m "Update MTBO events: $(date +'%Y-%m-%d')" >> "$LOG_FILE" 2>&1
    git push >> "$LOG_FILE" 2>&1
    echo "Pushed changes to git." >> "$LOG_FILE"
fi

echo "Scrape and push completed successfully at $(date)" >> "$LOG_FILE"
