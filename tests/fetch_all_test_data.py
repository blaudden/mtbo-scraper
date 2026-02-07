import json
import os
import re
import time
from typing import TypedDict, cast

from src.scraper import Scraper

# Configuration
TEST_DATA_DIR = "tests/data"
MANIFEST_FILE = os.path.join(TEST_DATA_DIR, "eventor_test_urls.json")


class FileEntry(TypedDict):
    url: str
    filename: str


class ManifestEntry(TypedDict, total=False):
    description: str
    used_for: str
    files: list[FileEntry]


def get_scraper() -> Scraper:
    # Use a 30s timeout by default for test data fetching
    return Scraper(default_timeout=30)


def load_manifest(filepath: str) -> list[ManifestEntry]:
    """Loads JSON manifest while skipping lines starting with #."""
    if not os.path.exists(filepath):
        return []

    try:
        with open(filepath, encoding="utf-8") as f:
            return cast(list[ManifestEntry], json.load(f))
    except json.JSONDecodeError as e:
        print(f"Error parsing manifest {filepath}: {e}")
        return []


def fetch_and_save(scraper: Scraper, url: str, filename: str) -> str | None:
    filepath = os.path.join(TEST_DATA_DIR, filename)

    def redact_contents(content: str) -> str:
        # Redact Google Maps API keys
        # Patterns: key=AIzaSy..., "key":"AIzaSy...",
        # &quot;key&quot;:&quot;AIzaSy...&quot;
        # We look for the prefix AIzaSy and redact until a
        # non-alphanumeric/hyphen/underscore char
        pattern = r"(AIzaSy[A-Za-z0-9_-]+)"
        replacement = "AIzaSy_REDACTED_API_KEY_00000"
        return re.sub(pattern, replacement, content)

    print(f"Fetching {filename}...")
    try:
        # Scraper handles culture=en-GB and retries automatically
        response = scraper.get(url, retries=2, timeout=30)
        if response:
            # Check for generic errors in text
            if "An error occurred" in response.text:
                print("  -> Error detected in text ('An error occurred') - skipping")
                return None

            response.raise_for_status()
            redacted_content = redact_contents(response.text)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(redacted_content)
            return redacted_content
        return None
    except Exception as e:
        if hasattr(e, "response") and e.response.status_code == 404:
            print("  -> Not found (404) - skipping")
        else:
            print(f"  -> Failed: {e}")
        return None


def main() -> None:
    if not os.path.exists(TEST_DATA_DIR):
        os.makedirs(TEST_DATA_DIR)

    manifest = load_manifest(MANIFEST_FILE)
    if not manifest:
        print(f"Manifest is empty or not found: {MANIFEST_FILE}")
        return

    scraper = get_scraper()

    for entry in manifest:
        print(f"Processing event: {entry.get('description', 'Unknown')}")
        for file_entry in entry["files"]:
            url = file_entry.get("url")
            filename = file_entry.get("filename")
            if url and filename:
                fetch_and_save(scraper, url, filename)
                time.sleep(0.5)

    print("\nFetch complete.")


if __name__ == "__main__":
    main()
