---
name: create-manual-event
description: Guidelines and steps for manually adding events to the MTBO scraper. Use this when you have an event PDF or URL that needs to be added manually because it's not on Eventor.
---

# Create Manual Event

Use this skill when you need to add an event to the system that cannot be scraped automatically (e.g., from a PDF bulletin or a standalone website).

## Workflow

1.  **Determine the Event ID**

    - Format: `MAN_{CountryCode}_{ShortName}{Year}`
    - Example: `MAN_DNK_MTBOCAMP26`
    - Ensure it starts with the 3-letter country code (e.g., `DNK`, `SWE`, `NOR`).

2.  **Create Event Directory**

    - Create a directory in `manual_events/` matching the ID.
    - `mkdir -p manual_events/{EventID}`

3.  **Gather Assets & Location**

    - Download any relevant PDFs (Bulletins, invitation) to this directory.
    - If you have a PDF, use `pdftotext` to extract text for analysis: `pdftotext "Bulletin.pdf" -`
    - Determine the event coordinates (latitude and longitude). It doesn't need to be exact. If there are multiple locations, approximate the middle.

4.  **Create `event.yaml`**

    - Create a file named `event.yaml` in the event directory.
    - Use the template below.

5.  **Verify**
    - Run the scraper locally for the event's date range to ensure it loads correctly.
    - `uv run python -m src.main --start-date YYYY-MM-DD --end-date YYYY-MM-DD`

> [!IMPORTANT]
> **NEVER** delete `data/events/*.json` files manually before running the scraper unless you intend to wipe all scraped data. The scraper is designed to merge manual and Eventor events safely into the existing data.

To sync manual events quickly without a full Eventor scrape, use:
```bash
uv run python -m src.main --source MAN
```

## Data Extraction Prompt
When you have extracted text from a PDF (e.g., using `pdftotext`), use the following prompt with an LLM to generate the `event.yaml` content:

> [!TIP]
> **Extraction Prompt**:
> "Extract MTBO event details from the following text into YAML format.
> Map races to: name, date (YYYY-MM-DD), discipline (Sprint, Middle, Long, Ultra Long, Training), and time (HH:mm).
> Identify officials (roles: Contact email, Event controller, etc.), entry deadlines, and the main website URL.
> Reference internal PDFs as 'file://filename.pdf' in the documents section."

## `event.yaml` Template

```yaml
id: "MAN_DNK_EVENTID"
name: "Event Name"
start_date: "YYYY-MM-DD"
end_date: "YYYY-MM-DD"
country: "DNK" # ISO 3 code (DNK, SWE, NOR, etc.)
organizers: ["Organizer Name"]
status: "Planned" # Planned, Sanctioned, Canceled
url: "http://event-website.com"
lat: 55.000 # Latitude (approximate middle if multiple locations)
lon: 12.000 # Longitude (approximate middle if multiple locations)
documents:
  - name: "Bulletin 1"
    url: "file://Bulletin1.pdf" # Relative to this yaml file
    type: "Bulletin"
races:
  - name: "Race 1 Name"
    date: "YYYY-MM-DD"
    time: "10:00"
    discipline: "Sprint" # Sprint, Middle, Long, Ultralong
    night_or_day: "day"
  - name: "Race 2 Name"
    date: "YYYY-MM-DD"
    time: "14:00"
    discipline: "Middle"
```

## Tips

- **Country Codes**: Always use 3-letter ISO codes for the `country` field and the ID prefix (e.g., `DNK` for Denmark).
- **Dates**: Always use `YYYY-MM-DD`.
- **Files**: Keep filenames simple and place them in the same directory as `event.yaml`. Refer to them with `file://Filename.pdf`.
