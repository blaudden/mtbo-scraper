import os
import re
import time

import cloudscraper
from bs4 import BeautifulSoup

# Configuration
TEST_DATA_DIR = "tests/data"
URLS_FILE = os.path.join(TEST_DATA_DIR, "eventor_test_urls.txt")


def get_scraper() -> cloudscraper.CloudScraper:
    scraper = cloudscraper.create_scraper()
    scraper.headers.update({"Accept-Language": "en-GB,en;q=0.9"})
    return scraper


def parse_urls(file_path: str) -> list[dict[str, str]]:
    events = []
    with open(file_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                # Extract ID and Country from URL
                # https://eventor.orientering.se/Events/Show/51338 -> SWE, 51338
                # https://eventor.orientering.no/Events/Show/21169 -> NOR, 21169
                # https://eventor.orienteering.org/Events/Show/8558 -> IOF, 8558

                parts = line.split("/")
                event_id = parts[-1]
                domain = parts[2]

                if "orientering.se" in domain:
                    country = "SWE"
                elif "orientering.no" in domain:
                    country = "NOR"
                elif "orienteering.org" in domain:
                    country = "IOF"
                else:
                    country = "UNKNOWN"

                events.append(
                    {
                        "url": line,
                        "id": event_id,
                        "country": country,
                        "base_url": f"https://{domain}",
                    }
                )
    return events


def fetch_and_save(
    scraper: cloudscraper.CloudScraper, url: str, filename: str
) -> str | None:
    filepath = os.path.join(TEST_DATA_DIR, filename)
    print(f"Fetching {url} -> {filename}")
    try:
        response = scraper.get(url)
        response.raise_for_status()
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(str(response.text))
        return str(response.text)
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
        return None


def main() -> None:
    if not os.path.exists(TEST_DATA_DIR):
        os.makedirs(TEST_DATA_DIR)

    scraper = get_scraper()
    events = parse_urls(URLS_FILE)

    for event in events:
        # 1. Fetch Main Event Page
        # Determine if single or multi based on content (simple heuristic or
        # just save as _main for now)
        # The user requested standardized names: COUNTRY_ID_TYPE.html
        # We'll use _main.html for the event page, and _entries, _start_list,
        # _result_list for lists.
        # If it's multi-day, the main page is still the entry point.

        main_filename = f"{event['country']}_{event['id']}_main.html"
        html = fetch_and_save(scraper, event["url"], main_filename)

        if not html:
            continue

        # Check for list links in the main page
        soup = BeautifulSoup(html, "lxml")

        # Helper to extract list URL
        def get_list_url(soup: BeautifulSoup, list_type: str) -> str | None:
            # list_type: 'Entries', 'StartList', 'ResultList'
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if f"/Events/{list_type}" in href and "groupBy=EventClass" in href:
                    if "PressResultList" in href:
                        continue
                    return str(href)
            return None

        # Check if this is a multi-race event with separate race pages
        # Look for race links (IOF events) or eventRaceId parameters (SWE events)
        race_links = []
        race_ids = set()

        # IOF: Look for separate race detail pages
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/Events/Show/" in href and href != event["url"]:
                match = re.search(r"/Events/Show/(\d+)", str(href))
                if match and match.group(1) != event["id"]:
                    race_links.append((match.group(1), f"{event['base_url']}{href}"))

        # SWE/NOR: Look for eventRaceId parameters
        for match in re.finditer(r"eventRaceId=(\d+)", html):
            race_ids.add(match.group(1))

        # Fetch race-specific pages for IOF events
        if race_links:
            print(f"  Found {len(race_links)} race detail pages")
            for i, (race_id, race_url) in enumerate(race_links, 1):
                # Fetch race detail page
                race_filename = f"{event['country']}_{event['id']}_race{i}_main.html"
                race_html = fetch_and_save(scraper, race_url, race_filename)

                if race_html:
                    # Fetch lists for this race
                    for list_type, suffix in [
                        ("StartList", "start_list"),
                        ("ResultList", "result_list"),
                    ]:
                        list_url = (
                            f"{event['base_url']}/Events/{list_type}"
                            f"?eventId={race_id}&groupBy=EventClass"
                        )
                        list_filename = (
                            f"{event['country']}_{event['id']}_race{i}_{suffix}.html"
                        )
                        fetch_and_save(scraper, list_url, list_filename)
                        time.sleep(1)
                time.sleep(1)

        # Fetch race-specific lists for SWE/NOR multi-race events
        elif race_ids:
            print(f"  Found {len(race_ids)} race IDs")
            for i, race_id in enumerate(sorted(race_ids), 1):
                for list_type, suffix in [
                    ("StartList", "start_list"),
                    ("ResultList", "result_list"),
                ]:
                    list_url = (
                        f"{event['base_url']}/Events/{list_type}"
                        f"?eventId={event['id']}&eventRaceId={race_id}"
                        "&groupBy=EventClass"
                    )
                    list_filename = (
                        f"{event['country']}_{event['id']}_race{i}_{suffix}.html"
                    )
                    fetch_and_save(scraper, list_url, list_filename)
                    time.sleep(1)

        # Fetch single-event lists (for single-race events or event-level lists)
        else:
            for list_type, suffix in [
                ("Entries", "entries"),
                ("StartList", "start_list"),
                ("ResultList", "result_list"),
            ]:
                list_href = get_list_url(soup, list_type)
                if list_href:
                    full_url = (
                        f"{event['base_url']}{list_href}"
                        if list_href.startswith("/")
                        else list_href
                    )
                    list_filename = f"{event['country']}_{event['id']}_{suffix}.html"
                    fetch_and_save(scraper, full_url, list_filename)
                    time.sleep(1)

        time.sleep(1)


if __name__ == "__main__":
    main()
