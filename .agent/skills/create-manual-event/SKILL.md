---
name: create-manual-event
description: Guidelines and steps for manually adding events to the MTBO scraper. Use this when you have an event PDF or URL that needs to be added manually because it's not on Eventor.
---

# Create Manual Event

Use this skill when you need to add an event to the system that cannot be scraped automatically (e.g., from a PDF bulletin or a standalone website).

## Workflow

1.  **Determine the Event ID**

    - Format: `{CountryCode}-MAN-{ShortName}{Year}`
    - Example: `DK-MAN-MTBOCAMP26`
    - Ensure it starts with the country code (e.g., `DK`, `SWE`, `NOR`) followed by `MAN` to indicate it is manual.

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
    - `python src/main.py --start-date YYYY-MM-DD --end-date YYYY-MM-DD`

## `event.yaml` Template

```yaml
id: "DK-MAN-EVENTID"
name: "Event Name"
start_date: "YYYY-MM-DD"
end_date: "YYYY-MM-DD"
country: "DNK" # ISO 3 code (DNK, SWE, NOR, etc.)
organizers: ["Organizer Name"]
status: "Planned" # Planned, Active, Cancelled
url: "http://event-website.com"
lat: 55.000 # Latitude (approximate middle if multiple locations)
lon: 12.000 # Longitude (approximate middle if multiple locations)
documents:
  - name: "Bulletin 1"
    url: "file://Bulletin1.pdf" # Relative to this yaml file
    type: "Bulletin"
races:
  - name: "Race 1 Name"
    # Create a unique but readable race_id: {EventID}-{race-slug}
    # (The loader will generate one if not specified, but explicit is better for stability)
    date: "YYYY-MM-DD"
    time: "10:00"
    distance: "Sprint" # Sprint, Middle, Long, Ultra Long
    night_or_day: "day"
  - name: "Race 2 Name"
    date: "YYYY-MM-DD"
    time: "14:00"
    distance: "Middle"
```

## Tips

- **Country Codes**: Use 3-letter ISO codes for the `country` field (e.g., `DNK` for Denmark), but 2-letter codes for the ID prefix if that's the project convention (e.g., `DK-MAN...`).
- **Dates**: Always use `YYYY-MM-DD`.
- **Files**: Keep filenames simple and place them in the same directory as `event.yaml`. refer to them with `file://Filename.pdf`.
