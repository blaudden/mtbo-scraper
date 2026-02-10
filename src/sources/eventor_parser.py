import json
import logging
import re
from datetime import UTC, datetime

from bs4 import BeautifulSoup, Tag

from src.models import (
    Area,
    Document,
    Event,
    ListCountDict,
    Official,
    Organiser,
    ParsedServiceLinkDict,
    Position,
    Race,
    Url,
)
from src.utils.country import get_iso_country_code
from src.utils.crypto import Crypto
from src.utils.date_and_time import (
    extract_time_from_date,
    format_iso_datetime,
    parse_date_to_iso,
)
from src.utils.fingerprint import Participant


class EventorParser:
    """Parses HTML content from Eventor to extract event lists and details.

    This parser handles both single-day and multi-day events, including
    extraction of race details, results/start list links, and document links.
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    @property
    def _now_iso(self) -> str:
        """Returns the current UTC time in ISO 8601 format."""
        return datetime.now(UTC).isoformat()

    @staticmethod
    def split_multi_value_field(value: str) -> list[str]:
        """Splits multi-value fields using delimiters from source HTML.

        This function relies ONLY on delimiters that exist in the original HTML:
        - Newlines (from <br> tags or actual newlines)
        - Commas

        NO heuristic splitting is performed. If the HTML doesn't have proper
        delimiters, the value is returned as-is.

        Args:
            value: The input string to split.

        Returns:
            A list of extracted string values.
        """
        # Split by newlines (from <br> tags converted by BeautifulSoup)
        if "\n" in value:
            parts = [v.strip() for v in value.split("\n") if v.strip()]
            return parts if parts else [value]

        # Split by commas
        if "," in value:
            parts = [v.strip() for v in value.split(",") if v.strip()]
            return parts if parts else [value]

        # No delimiters found - return as single value
        return [value] if value else []

    def _map_status(self, raw_status: str) -> str:
        s = raw_status.lower()
        if "cancel" in s:
            return "Canceled"  # IOF spelling
        if "active" in s or "sanctioned" in s or "approved" in s:
            return "Sanctioned"
        if "planned" in s or "applied" in s:
            return "Planned"
        if "propose" in s:
            return "Proposed"
        return "Planned"  # Default

    def _map_night_or_day(self, text: str) -> str | None:
        """Maps text to 'day', 'night', 'combined' or None."""
        if not text:
            return None
        text = text.lower().strip()
        if "combined" in text:
            return "combined"
        if "night" in text or "natt" in text:
            return "night"
        if "day" in text or "dag" in text:
            return "day"
        return None

    def _map_discipline(self, val: str) -> str:
        v = val.lower()
        if "sprint" in v:
            return "Sprint"
        if "long" in v or "lång" in v:
            return "Long"
        if "middle" in v or "mellan" in v:
            return "Middle"
        if "ultra" in v:
            return "Ultralong"
        return "Other"

    def _extract_types(self, attributes: dict[str, str], country: str) -> list[str]:
        """Extracts event types directly from Eventor attributes.

        Args:
            attributes: Dictionary of event attributes.
            country: Country code (e.g., "IOF", "SWE", "NOR").

        Returns:
            List of event type strings from Eventor.
        """
        if country == "IOF":
            # For IOF events, look for "Event type" or "Event types"
            for k, v in attributes.items():
                k_stripped = k.strip()
                if k_stripped in ("Event type", "Event types"):
                    # Split by newlines to get multiple types
                    types = [t.strip() for t in v.split("\n") if t.strip()]
                    return types
        else:
            # For SWE and NOR events, look for "Event classification"
            for k, v in attributes.items():
                if k.strip() == "Event classification":
                    # Remove trailing " event" suffix
                    cleaned = v.strip()
                    if cleaned.endswith(" event"):
                        cleaned = cleaned[:-6]  # Remove " event"
                    return [cleaned]

        # Return empty list if attribute not found
        return []

    def _map_form(self, attributes: dict[str, str]) -> str | None:
        for _k, v in attributes.items():
            vl = v.lower()
            if "relay" in vl or "stafett" in vl:
                return "Relay"
            if "team" in vl or "patrull" in vl:
                return "Team"
            if "individual" in vl or "natt" in vl or "distans" in vl:
                return "Individual"
        return None

    def _parse_disciplines(self, attributes: dict[str, str]) -> list[str]:
        """Parses additional discipline tags from attributes.

        Extracts disciplines like FootO, SkiO, TrailO, Indoor from
        the Disciplines or Discipline field.

        Args:
            attributes: Dictionary of additional event attributes.

        Returns:
            List of discipline tags (excluding MTBO).
        """
        tags = []
        for key, value in attributes.items():
            if "discipline" in key.lower():
                # Split by common separators and normalize
                parts = self.split_multi_value_field(value)
                for part in parts:
                    # Normalize common variations
                    normalized = part.strip()
                    if normalized:
                        tags.append(normalized)
                break  # Only process first discipline field

        # Remove MTBO from tags as all our events are MTBO
        tags = [tag for tag in tags if tag != "MTBO"]

        return tags

    def _format_url(self, url: str, base_url: str | None) -> str:
        """Formats the URL.

        If the URL is absolute and starts with base_url, it strips the base_url
        to return a relative path.
        If the URL is strictly relative (starts with /), it returns it as is.
        Otherwise it returns the URL as is (assumed external or already correct).
        """
        if not url:
            return url

        # If we have a base_url and the url starts with it, make it relative
        if base_url and url.startswith(base_url):
            return url[len(base_url) :]

        return url

    def parse_event_list(
        self, html_content: str, country: str, base_url: str | None = None
    ) -> list[Event]:
        """Parses the event list page and returns a list of Event objects.

        Args:
            html_content: The HTML content of the event list page.
            country: The country code (e.g. "SWE").
            base_url: Optional base URL for resolving relative links.

        Returns:
            A list of Event objects with basic information.

        Example:
            >>> parser = EventorParser()
            >>> html = "<html>...</html>"  # Eventor event list HTML
            >>> events = parser.parse_event_list(html, "SWE", "https://eventor.se")
            >>> for event in events:
            ...     print(f"{event.id}: {event.name}")
        """
        soup = BeautifulSoup(html_content, "lxml")
        events = []

        # Try multiple selectors to find the event table
        event_rows = soup.select("div#eventList table tbody tr")
        if not event_rows:
            event_rows = soup.select("div#eventList tbody tr")

        for row in event_rows:
            event = self._parse_event_list_row(row, country, base_url)
            if event:
                events.append(event)

        return events

    def _parse_event_list_row(
        self, row: Tag, country: str, base_url: str | None = None
    ) -> Event | None:
        """Parses a single row from the event list table."""
        if not row.find("td"):
            return None

        try:
            cols = row.find_all("td")
            if len(cols) < 4:
                return None

            # Column 0: Date
            date_col = cols[0]
            date_span = date_col.find("span", attrs={"data-date": True})
            start_date_str = ""
            end_date_str = ""

            if date_span:
                full_date = str(date_span["data-date"])
                # Usually returned as YYYY-MM-DD
                start_date_str = full_date.split(" ")[0]
                end_date_str = start_date_str  # Default to single day
            else:
                # Basic fallback
                pass

            # Column 1: Name and URL
            name_col = cols[1]
            name_link = name_col.find("a")
            if not name_link:
                return None

            name = name_link.get_text(strip=True)
            # Ensure URL is formatted (relative if internal)
            # Casting to str is necessary because BS4 can return list if
            # multi-valued attribute
            url = self._format_url(str(name_link["href"]), base_url)

            event_id_match = re.search(r"/Events/Show/(\d+)", url)
            if not event_id_match:
                return None
            source_id = event_id_match.group(1)
            event_id = f"{country}_{source_id}"

            # Column 2: Organizer(s)
            org_col = cols[2]
            org_text = org_col.get_text(separator="\n", strip=True)
            # simple split by newline for organisers.
            organiser_names = [
                org.strip() for org in org_text.split("\n") if org.strip()
            ]
            organiser_names = [
                org.strip() for org in org_text.split("\n") if org.strip()
            ]

            organisers = []
            for org_name in organiser_names:
                org_country = country

                # If it's an IOF event, try to resolve the real country
                # from the organizer name
                if country == "IOF":
                    resolved_code = get_iso_country_code(org_name)
                    if resolved_code:
                        org_country = resolved_code

                organisers.append(Organiser(name=org_name, country_code=org_country))

            # Status
            raw_status = "Active"
            if row.select_one(".cancelled"):
                raw_status = "Cancelled"
            status = self._map_status(raw_status)

            # Base Event without details
            # Create default race
            # Calculate Race datetime with offset from the plain start date
            race_start_datetime = format_iso_datetime(start_date_str, None, country)

            race = Race(
                race_number=1,
                name=name,
                datetimez=race_start_datetime,
                discipline="Other",
            )

            return Event(
                id=event_id,
                name=name,
                start_time=start_date_str,
                end_time=end_date_str,
                status=status,
                original_status=raw_status,
                races=[race],
                organisers=organisers,
                urls=[],
                url=url,
                region=None,  # Will be populated if possible
            )
        except Exception as e:
            self.logger.warning(f"Error parsing event row: {e}", exc_info=True)
            return None

    def _detect_link_type(self, a_tag: Tag) -> str | None:
        """Identifies the type of Eventor service link based on its URL pattern.

        This method analyzes the 'href' and 'class' attributes of an anchor tag
        to determine if it points to a specific Eventor service like a start list,
        result list, or Livelox.

        Args:
            a_tag: The anchor tag to analyze.

        Returns:
            A string representing the link type (e.g., 'EntryList', 'StartList'),
            or None if the type could not be determined.
        """
        # Extract the href attribute, convert to string, and make it lowercase
        # for case-insensitive matching.
        # Using .get() with a default empty string handles cases where
        # 'href' might be missing.
        href = str(a_tag.get("href", "")).lower()

        # 1. Entry List: Check for specific URL patterns indicating an entry list.
        #    Eventor entry lists often contain "groupby=eventclass" in their URL.
        if "/events/entries" in href and "groupby=eventclass" in href:
            return "EntryList"

        # 2. Start List
        if "/events/startlist" in href:
            return "StartList"

        # 3. Result List
        if "/events/resultlist" in href:
            return "ResultList"

        # 4. Livelox
        if "livelox" in href:
            return "Livelox"

        # 5. Series
        if "/standings/view/series" in href:
            return "Series"

        return None

    def _extract_links_from_infoboxes(
        self, soup: Tag, base_url: str | None = None
    ) -> list[ParsedServiceLinkDict]:
        """Extracts Start/Result/Entry/Livelox links from eventInfoBox containers.

        Args:
            soup: The BeautifulSoup object of the page.

        Returns:
            A list of dictionaries containing 'race_index' (1-based), 'type', and 'url'.
        """
        links: list[ParsedServiceLinkDict] = []
        boxes = soup.find_all("div", class_="eventInfoBox")

        # Track counters per type to handle sequences without explicit stage numbers
        counters = {
            "StartList": 0,
            "ResultList": 0,
            "EntryList": 0,
            "Livelox": 0,
            "Series": 0,
        }

        for box in boxes:
            header = box.find("h3")
            if not header:
                continue

            header_text = header.get_text(strip=True).lower()
            l_type = None
            if any(x in header_text for x in ["startlist", "starttider", "startliste"]):
                l_type = "StartList"
            elif any(x in header_text for x in ["resultlist", "resultat"]):
                l_type = "ResultList"
            elif any(
                x in header_text for x in ["entries", "anmälan", "påmelding", "entry"]
            ):
                l_type = "EntryList"
            elif "livelox" in header_text:
                l_type = "Livelox"
            elif "serier" in header_text or "series" in header_text:
                l_type = "Series"

            if not l_type:
                continue

            counters[l_type] += 1

            # Default to ordinal position for this type
            race_index: int | None = counters[l_type]
            if l_type == "Series":
                # Series links apply to the entire event, not a specific race.
                # Setting index to None ensures it is assigned to the Event object.
                race_index = None

            # Try to extract explicit stage number "etapp X", "stage X", ...
            index_match = re.search(
                r"(?:etapp|stage|race|del|day)\s*(\d+)", header_text, re.I
            )
            if index_match:
                race_index = int(index_match.group(1))

            # A box can sometimes have multiple links (e.g. variants of start lists)
            # in that case we need to check for duplicates and only add the first one
            for a in box.find_all("a", href=True):
                href = self._format_url(a["href"], base_url)

                # Check duplication
                if not any(
                    link["race_index"] == race_index
                    and link["type"] == l_type
                    and link["url"] == href
                    for link in links
                ):
                    title = a.get_text(strip=True)
                    links.append(
                        ParsedServiceLinkDict(
                            race_index=race_index,
                            type=l_type,
                            url=href,
                            title=title,
                        )
                    )

        return links

    def parse_event_details(
        self, html: str, event: Event, base_url: str | None = None
    ) -> Event:
        """Parses the event detail page and updates the Event object with details.

        Args:
            html: The HTML content of the event detail page.
            event: The Event object to update.
            base_url: Optional base URL for resolving relative links.

        Returns:
            The updated Event object.

        Example:
            >>> parser = EventorParser()
            >>> event = Event(id="SWE_123", name="Test", ...)
            >>> html = "<html>...</html>"  # Eventor event detail HTML
            >>> detailed_event = parser.parse_event_details(html, event, "https://...")
            >>> print(f"Classes: {detailed_event.classes}")
        """
        soup = BeautifulSoup(html, "lxml")

        # Global scope: use #content if available, otherwise warn and use soup
        content_root = soup.find(id="content")
        if not isinstance(content_root, Tag):
            if content_root is not None:
                self.logger.warning(
                    f"Event {event.id}: #content is not a Tag, using entire page."
                )
            else:
                self.logger.debug(f"Event {event.id}: No #content div found.")
            content_root = soup

        # 1. Attributes & Country
        # Extract federation country from event ID (e.g., "IOF", "SWE", "NOR")
        federation_country = (
            event.id.split("_")[0] if "_" in event.id else event.id.split("-")[0]
        )

        if federation_country == "IOF":
            (
                attributes,
                venue_country,
                iof_organisers,
            ) = self._extract_iof_attributes_and_country(content_root, event)

            # If we successfully extracted IOF organisers,
            # overwrite the event's organisers
            if iof_organisers:
                event.organisers = iof_organisers
        else:
            (
                attributes,
                venue_country,
            ) = self._extract_default_attributes_and_country(content_root, event)

        self._apply_attributes(event, attributes, federation_country)

        # Add a relative path URL for the event by stripping the base URL if present
        if event.url:
            path = event.url
            if "://" in path:
                path = path.split("://", 1)[1].split("/", 1)[1]
            elif path.startswith("/"):
                path = path.lstrip("/")

            # Check for existing Path URL to avoid duplication
            path_url = Url(type="Path", url=path)
            if not any(u.type == "Path" and u.url == path for u in event.urls):
                event.urls.append(path_url)

        # 2. Info Text
        event.information = self._extract_info_text(content_root)

        # 3. Contacts / Officials
        officials, web_urls = self._extract_officials_and_urls(content_root)
        # Overwrite officials as the detail page is authoritative
        event.officials = officials

        # Merge web_urls avoiding duplicates
        for w_url in web_urls:
            if not any(
                existing.url == w_url.url and existing.type == w_url.type
                for existing in event.urls
            ):
                event.urls.append(w_url)

        # 4. Classes
        event.classes = self._extract_classes_list(content_root)

        # 5. Documents
        # Overwrite documents as the detail page is authoritative
        event.documents = self._extract_documents_list(content_root, base_url)

        # 6. Races extraction
        event.races = self._extract_races_strategy(
            content_root,
            event,
            attributes,
            venue_country,
            base_url,
        )

        # 7. Service Links
        self._assign_service_links(content_root, event, base_url)

        # 8. Map Positions
        self._assign_map_positions(content_root, event)

        return event

    def _extract_map_positions(
        self, soup: Tag
    ) -> list[tuple[Position | None, list[Area]]]:
        """
        Extracts map positions. Returns list of objects with lat, lon, polygon.
        (Using a temporary SimpleNamespace or similar for internal passing)
        """

        results = []
        options_inputs = soup.select(".mapPosition input.options")
        for input_el in options_inputs:
            try:
                raw_value = input_el.get("value", "")
                try:
                    data = json.loads(str(raw_value))
                except json.JSONDecodeError:
                    clean_value = str(raw_value).replace("&quot;", '"')
                    data = json.loads(clean_value)

                lat = float(data.get("latitude") or data.get("centerLatitude") or 0)
                lon = float(data.get("longitude") or data.get("centerLongitude") or 0)

                polygon = None
                if "polygonVertices" in data and isinstance(
                    data["polygonVertices"], list
                ):
                    polygon = []
                    for v in data["polygonVertices"]:
                        p_lat = float(v.get("Latitude", 0))
                        p_lon = float(v.get("Longitude", 0))
                        # Ensure coordinate order matches [lat, lng]
                        # as per Position struct
                        polygon.append([p_lat, p_lon])

                pos = Position(lat=lat, lng=lon) if lat != 0 or lon != 0 else None
                areas = [Area(lat=lat, lng=lon, polygon=polygon)] if polygon else []

                results.append((pos, areas))
            except (ValueError, json.JSONDecodeError) as e:
                self.logger.warning(
                    f"Failed to parse map position data: {e}",
                    extra={"raw_value": str(input_el.get("value", ""))[:100]},
                )
                continue
            except Exception as e:
                self.logger.error(
                    f"Unexpected error in map position extraction: {e}", exc_info=True
                )
                continue
        return results

    def parse_list_count(self, html: str) -> ListCountDict:
        """
        Parses Entry/Start/Result list pages.
        """
        soup = BeautifulSoup(html, "lxml")
        total_count = 0
        class_counts = {}

        headers = soup.select("div.eventClassHeader")
        for header in headers:
            class_name_tag = header.find("h3")
            if not class_name_tag:
                continue
            class_name = class_name_tag.get_text(strip=True)

            table = header.find_next_sibling("table")
            if not table:
                continue

            # Iterate rows
            tbody = table.find("tbody")
            if tbody and isinstance(tbody, Tag):
                count = len(tbody.find_all("tr"))
                class_counts[class_name] = count
                total_count += count

        if total_count == 0:
            tables = soup.select(
                "table.resultList, table.entryList, table.startList, "
                "table.competitorList"
            )
            for table in tables:
                tbody = table.find("tbody")
                if tbody and isinstance(tbody, Tag):
                    total_count += len(tbody.find_all("tr"))

        return ListCountDict(total_count=total_count, class_counts=class_counts)

    def _extract_raw_general_info(self, soup: Tag) -> dict[str, str]:
        """Extracts raw key-value pairs from the 'General information' table.

        Strictly looks for the English header 'General information' first,
        as we scrape in English.

        Args:
            soup: The BeautifulSoup object.

        Returns:
            A dictionary of raw attributes.
        """
        attributes = {}
        # English header is primary source of truth
        general_info_table = soup.find(
            "caption",
            string=re.compile(r"General information", re.I),
        )

        if general_info_table:
            table = general_info_table.find_parent("table")
            if table:
                for row in table.find_all("tr"):
                    th = row.find("th")
                    td = row.find("td")
                    if th and td:
                        key = th.get_text(strip=True)
                        value = td.get_text(separator="\n", strip=True)
                        # Skip Event and Date rows as they are standard headers
                        if key not in ["Event", "Date"]:
                            attributes[key] = value

        return attributes

    def _resolve_iof_organisers(
        self, attributes: dict[str, str]
    ) -> tuple[str, list[Organiser] | None]:
        """Processes raw attributes to resolve IOF organisers and venue country.

        Args:
            attributes: The raw dictionary of attributes.

        Returns:
            A tuple containing:
            - resolved venue country string (default "IOF" if not found)
            - list of specific Organiser objects or None
        """
        venue_country = "IOF"
        organising_federation = None
        organising_club = None

        for key, value in attributes.items():
            if "federation" in key.lower():
                organising_federation = value.strip()
                # Resolve country code from federation name
                resolved_code = get_iso_country_code(organising_federation)
                if resolved_code:
                    venue_country = resolved_code
                else:
                    venue_country = organising_federation

            if "club" in key.lower() or "klubb" in key.lower():
                organising_club = value.strip()

        organisers = None
        if organising_federation:
            organisers = []
            organisers.append(
                Organiser(name=organising_federation, country_code=venue_country)
            )
            # Only add club if it's different from federation (avoid duplicates)
            if organising_club and organising_club != organising_federation:
                organisers.append(
                    Organiser(name=organising_club, country_code=venue_country)
                )

        return venue_country, organisers

    def _extract_default_attributes_and_country(
        self, soup: Tag, event: Event
    ) -> tuple[dict[str, str], str]:
        """Extracts general attributes and venue country for standard events.

        Args:
            soup: The BeautifulSoup object.
            event: The Event object (used for ID-based country fallback).

        Returns:
            A tuple containing a dictionary of attributes and the venue country string.
        """
        # Step 1: Extract raw attributes
        attributes = self._extract_raw_general_info(soup)

        # Step 2: Determine country from ID (Default logic)
        venue_country = event.id.split("_")[0]
        if "_" not in event.id and "-" in event.id:
            venue_country = event.id.split("-")[0]

        return attributes, venue_country

    def _extract_iof_attributes_and_country(
        self, soup: Tag, event: Event
    ) -> tuple[dict[str, str], str, list[Organiser] | None]:
        """Extracts attributes, country, and organisers specifically for IOF events.

        Args:
            soup: The BeautifulSoup object.
            event: The Event object.

        Returns:
            A tuple containing:
            - dictionary of attributes
            - resolved venue country string
            - list of specific Organiser objects (Federation + Club)
              or None if not found
        """
        # Step 1: Extract raw attributes
        attributes = self._extract_raw_general_info(soup)

        # Step 2: Process attributes for IOF specific logic
        venue_country, organisers = self._resolve_iof_organisers(attributes)

        return attributes, venue_country, organisers

    def _apply_attributes(
        self, event: Event, attributes: dict[str, str], country: str
    ) -> None:
        """Applies extracted attributes to the Event object.

        Args:
            event: The Event object to update.
            attributes: The dictionary of attributes.
            country: Country code (e.g., "IOF", "SWE", "NOR").
        """
        event.start_time = parse_date_to_iso(event.start_time)
        event.end_time = parse_date_to_iso(event.end_time)

        # Extract event types using the country code
        event.types = self._extract_types(attributes, country)

        event.form = self._map_form(attributes)

        for k, v in attributes.items():
            if "district" in k.lower() or "region" in k.lower():
                event.region = v
                break

        for k, v in attributes.items():
            if "punching" in k.lower() or "stämpling" in k.lower():
                event.punching_system = v
                break

        # Parse discipline tags
        event.tags = self._parse_disciplines(attributes)

    def _extract_info_text(self, soup: Tag) -> str | None:
        """Extracts the main information text from the event page.

        Args:
            soup: The BeautifulSoup object.

        Returns:
            The extracted information text, or None if not found.
        """
        info_paragraphs = soup.select("div.showEventInfoContainer p.info")
        for info_p in info_paragraphs:
            for br in info_p.find_all("br"):
                br.replace_with("\n")
            text = info_p.get_text(separator="\n", strip=True)
            if info_p.find_parent(class_=["mapPosition", "eventCenterMaps"]):
                continue
            if text.startswith("Keep in mind that as a competitor"):
                continue
            return text if text else None
        return None

    def _extract_officials_and_urls(
        self, soup: Tag
    ) -> tuple[list[Official], list[Url]]:
        """Extracts officials and contact URLs.

        Args:
            soup: The BeautifulSoup object.

        Returns:
            A tuple containing a list of Official objects and a list of Url objects.
        """
        officials: list[Official] = []
        urls: list[Url] = []

        contact_table = soup.find(
            "caption",
            string=re.compile(r"(Contact|Kontakt)", re.I),
        )
        if not contact_table:
            return officials, urls

        table = contact_table.find_parent("table")
        if not table:
            return officials, urls

        for row in table.find_all("tr"):
            th = row.find("th")
            td = row.find("td")
            if not (th and td):
                continue

            key = th.get_text(strip=True)
            value = td.get_text(separator="\n", strip=True)

            if any(
                x in key.lower()
                for x in ["hemsideadress", "website", "homepage", "hjemmeside"]
            ):
                a_tag = row.find("a", href=True)
                if a_tag:
                    urls.append(
                        Url(
                            type="Website",
                            url=self._format_url(str(a_tag["href"]), None),
                        )
                    )

            if "Contact email" in key or "Kontakt" in key:
                email_img = row.find("img", class_="emailSpamProtection")
                if email_img and email_img.get("src"):
                    src = email_img["src"]
                    match = re.search(r"/SpamProtection/([0-9A-Fa-f]+)", src)
                    if match:
                        try:
                            hex_str = match.group(1)
                            email = bytes.fromhex(hex_str).decode("utf-8")
                            enc_email = Crypto.encrypt(email)
                            officials.append(Official(role=key, name=enc_email))
                            continue
                        except Exception:
                            pass

            if any(
                x in key.lower()
                for x in [
                    "director",
                    "setter",
                    "controller",
                    "ledare",
                    "läggare",
                    "kontrollant",
                    "contact",
                    "kontakt",
                ]
            ):
                names = self.split_multi_value_field(value)
                for n in names:
                    officials.append(Official(role=key, name=n))

        return officials, urls

    def _extract_classes_list(self, soup: Tag) -> list[str]:
        """Extracts available classes from the 'Class information' table.

        Args:
            soup: The BeautifulSoup object.

        Returns:
            A sorted list of unique class names.
        """
        class_table = soup.find(
            "caption",
            string=re.compile(r"Class information", re.I),
        )
        if not class_table:
            return []

        table = class_table.find_parent("table")
        if not table or "no classes" in table.get_text().lower():
            return []

        all_classes = []
        for row in table.find_all("tr"):
            td = row.find("td")
            if td:
                row_classes = [
                    c.strip()
                    for c in td.get_text(separator=",").split(",")
                    if c.strip()
                ]
                all_classes.extend(row_classes)
        return sorted(set(all_classes))

    def _extract_documents_list(
        self, soup: Tag, base_url: str | None = None
    ) -> list[Document]:
        """Extracts linked documents (Bulletins, Start Lists, etc.).

        Args:
            soup: The BeautifulSoup object.
            base_url: Base URL for resolving relative links.

        Returns:
            A list of Document objects.
        """
        documents: list[Document] = []
        doc_header = soup.find(
            lambda tag: tag.name in ["h2", "h3", "h4"] and "Documents" in tag.get_text()
        )
        if not doc_header:
            return documents

        doc_list = doc_header.find_next("ul", class_="documents")
        if not doc_list or not isinstance(doc_list, Tag):
            return documents

        for li in doc_list.find_all("li"):
            link = li.find("a", class_="documentName")
            if not link:
                link = li.find("a", class_="external")
                if link and link.find("img"):
                    link = li.find_all("a")[-1]

            if link:
                name = link.get_text(strip=True)
                url = self._format_url(link["href"], base_url)

                doc_type = "Other"
                lower_name = name.lower()
                if any(
                    x in lower_name for x in ["inbjudan", "invitation", "innbydelse"]
                ):
                    doc_type = "Invitation"
                elif any(x in lower_name for x in ["pm", "bulletin"]):
                    doc_type = "Bulletin"
                elif "start" in lower_name:
                    doc_type = "StartList"
                elif "result" in lower_name:
                    doc_type = "ResultList"
                elif "embargo" in lower_name:
                    doc_type = "EmbargoMap"

                # Extract published time
                published_time = None
                size_date_span = li.find("span", class_="documentSizeAndDate")
                if size_date_span:
                    # Text format: "(3 446 kB, 14/05/2025)"
                    text = size_date_span.get_text(strip=True)
                    # Extract the date part (DD/MM/YYYY)
                    # We look for a date pattern inside the parentheses
                    date_match = re.search(r"(\d{1,2}/\d{1,2}/\d{4})", text)
                    if date_match:
                        raw_date = date_match.group(1)
                        published_time = parse_date_to_iso(raw_date)

                documents.append(
                    Document(
                        type=doc_type,
                        title=name,
                        url=str(url),
                        published_time=published_time,
                    )
                )

        return documents

    def _extract_races_strategy(
        self,
        soup: Tag,
        event: Event,
        attributes: dict[str, str],
        venue_country: str,
        base_url: str | None = None,
    ) -> list[Race]:
        races = []

        race_captions = soup.find_all(
            "caption",
            string=re.compile(r"(Stage|Race|Etapp)", re.I),
        )
        if race_captions:
            for idx, cap in enumerate(race_captions):
                races.append(
                    self._parse_race_table(cap, idx + 1, event, venue_country, base_url)
                )

            self._enrich_races_from_infoboxes(soup, races, base_url)
            return races

        tables = soup.select("table.eventInfo")
        for table in tables:
            caption = table.find("caption")
            if not caption or not isinstance(caption, Tag):
                continue
            cap_text = caption.get_text(strip=True)
            if any(
                x in cap_text.lower()
                for x in ["general", "contact", "class", "entry", "document"]
            ):
                continue

            if self._table_looks_like_race(table):
                races.append(
                    self._parse_race_table(
                        caption, len(races) + 1, event, venue_country, base_url
                    )
                )

        if races:
            self._enrich_races_from_infoboxes(soup, races, base_url)
            return races

        default_race = (
            event.races[0]
            if event.races
            else Race(
                race_number=1,
                name=event.name,
                datetimez=event.start_time,
                discipline="Other",
            )
        )

        self._update_race_from_attributes(default_race, attributes)
        races = [default_race]

        return races

    def _parse_race_table(
        self,
        caption_tag: Tag,
        race_number: int,
        event: Event,
        venue_country: str,
        base_url: str | None = None,
    ) -> Race:
        """Parses an Eventor race table to extract race details and associated links.

        Separates concern by first extracting raw table data and then processing
        it into a Race model.

        Args:
            caption_tag: The <caption> element of the race table.
            race_number: The sequential 1-based number of this race.
            event: The Event object this race belongs to.
            venue_country: The country code of the event venue.

        Returns:
            A populated Race object.
        """
        table_rows = self._extract_race_table_data(caption_tag)
        race_data = {label: val for label, val, _ in table_rows}

        # Process dates and disciplines
        date_str = race_data.get("date", "")
        date_only, time, offset = extract_time_from_date(date_str)
        date_only = parse_date_to_iso(date_only)

        dist = race_data.get(
            "race distance",
            race_data.get("competition format", race_data.get("distance", "")),
        )
        discipline = self._map_discipline(dist)

        race_datetime = format_iso_datetime(
            date_only, time, venue_country, offset=offset
        )

        # Extract links and internal Eventor ID
        race_urls, internal_eventor_id = self._extract_links_from_race_rows(
            table_rows, base_url
        )

        # Fallback for internal_eventor_id from caption if still missing
        if not internal_eventor_id:
            caption_link = caption_tag.find("a", href=True)
            if caption_link and isinstance(caption_link, Tag):
                match = re.search(r"eventRaceId=(\d+)", str(caption_link["href"]))
                if match:
                    internal_eventor_id = match.group(1)

        race = Race(
            race_number=race_number,
            name=caption_tag.get_text(strip=True),
            datetimez=race_datetime,
            discipline=discipline,
            night_or_day=self._map_night_or_day(race_data.get("time of event", "")),
            urls=race_urls,
        )
        # Store the internal Eventor ID (this is NOT the race_number)
        race._internal_eventor_id = internal_eventor_id
        return race

    def _extract_race_table_data(
        self, caption_tag: Tag
    ) -> list[tuple[str, str, list[Tag]]]:
        """Extracts raw key-value pairs and associated anchor tags from a race table.

        Args:
            caption_tag: The <caption> element of the race table.

        Returns:
            A list of tuples: (lowercase_label, text_value, list_of_anchor_tags).
        """
        table = caption_tag.find_parent("table")
        extracted_data: list[tuple[str, str, list[Tag]]] = []

        if not table:
            return extracted_data

        for row in table.find_all("tr"):
            th = row.find("th")
            td = row.find("td")
            if th and td:
                label = th.get_text(strip=True).lower()
                val = td.get_text(strip=True)
                links = td.find_all("a", href=True)
                extracted_data.append((label, val, links))

        return extracted_data

    def _extract_links_from_race_rows(
        self,
        table_rows: list[tuple[str, str, list[Tag]]],
        base_url: str | None = None,
    ) -> tuple[list[Url], str | None]:
        """Identifies service links and internal Eventor ID from extracted table rows.

        Args:
            table_rows: The data structure returned by _extract_race_table_data.

        Returns:
            A tuple of (list of Url objects, internal Eventor ID string or None).
        """
        race_urls: list[Url] = []
        internal_id = None

        for label, val, links in table_rows:
            for a in links:
                href = self._format_url(str(a["href"]), base_url)

                l_type = self._detect_link_type(a)

                # Contextual detection based on row header
                if not l_type:
                    if "result" in label:
                        l_type = "ResultList"
                    elif "start" in label:
                        l_type = "StartList"

                if l_type:
                    if not any(u.url == href for u in race_urls):
                        race_urls.append(
                            Url(
                                type=l_type,
                                url=href,
                                title=val or l_type,
                            )
                        )

                # Capture internal Eventor ID (eventRaceId)
                if not internal_id:
                    match = re.search(r"eventRaceId=(\d+)", str(href))
                    if match:
                        internal_id = match.group(1)

        return race_urls, internal_id

    def _table_looks_like_race(self, table: Tag) -> bool:
        for row in table.find_all("tr"):
            th = row.find("th")
            if th:
                key = th.get_text(strip=True).lower()
                if "date" in key or "format" in key or "distance" in key:
                    return True
        return False

    def _update_race_from_attributes(
        self, race: Race, attributes: dict[str, str]
    ) -> None:
        for k, v in attributes.items():
            if any(x in k.lower() for x in ["distance", "format", "discipline"]):
                new_disc = self._map_discipline(v)
                if new_disc != "Other" or race.discipline == "Other":
                    race.discipline = new_disc
            if "time" in k.lower() or "tid" in k.lower():
                race.night_or_day = self._map_night_or_day(v)

    def _enrich_races_from_infoboxes(
        self, soup: Tag, races: list[Race], base_url: str | None = None
    ) -> None:
        for box in soup.select("div.eventInfoBox"):
            header = box.find("h3")
            if not header:
                continue

            header_text = header.get_text(strip=True)
            match = re.search(r"(?:etapp|stage|race|del)\s*(\d+)", header_text, re.I)

            if match:
                try:
                    race_idx = int(match.group(1)) - 1
                    if 0 <= race_idx < len(races):
                        race = races[race_idx]
                        if not getattr(race, "_internal_eventor_id", None):
                            for link in box.find_all("a", href=True):
                                id_match = re.search(
                                    r"eventRaceId=(\d+)",
                                    str(link["href"]),
                                )
                                if id_match:
                                    race._internal_eventor_id = id_match.group(1)
                                    break
                except ValueError:
                    pass

    def _assign_service_links(
        self, soup: Tag, event: Event, base_url: str | None = None
    ) -> None:
        """Distributes event-wide service links to the event or specific races.

        This method first collects all links already assigned during race table
        parsing. It then extracts links from event infoboxes and the general
        page content, attempting to map them to specific races based on
        internal Eventor IDs or simple event structures.

        Args:
            soup: The BeautifulSoup object representing the event details page.
            event: The Event object to populate with links.
            base_url: Base URL for resolving relative links.
        """
        box_links = self._extract_links_from_infoboxes(soup, base_url)
        assigned_urls = set()

        # Add links already assigned in _parse_race_table
        for r in event.races:
            for u in r.urls:
                assigned_urls.add(u.url)

        for bl in box_links:
            idx = bl.get("race_index")
            url_obj = Url(
                type=bl["type"],
                url=bl["url"],
                title=bl.get("title"),
            )
            assigned_urls.add(bl["url"])

            if idx and 1 <= idx <= len(event.races):
                if not any(
                    u.type == url_obj.type and u.url == url_obj.url
                    for u in event.races[idx - 1].urls
                ):
                    event.races[idx - 1].urls.append(url_obj)
            else:
                if not any(
                    u.type == url_obj.type and u.url == url_obj.url for u in event.urls
                ):
                    event.urls.append(url_obj)

        race_map = {
            r._internal_eventor_id: r
            for r in event.races
            if getattr(r, "_internal_eventor_id", None)
        }

        # Iterate through all links in the soup (which is now the content_root)
        for a in soup.find_all("a", href=True):
            href_val = a["href"]
            href = self._format_url(str(href_val), base_url)

            if href in assigned_urls:
                continue

            l_type = self._detect_link_type(a)

            if l_type:
                race_id_match = re.search(r"eventRaceId=(\d+)", str(href))
                assigned = False

                if race_id_match and race_map:
                    r_id = race_id_match.group(1)
                    if r_id in race_map:
                        if not any(u.url == href for u in race_map[r_id].urls):
                            title = a.get_text(strip=True)
                            race_map[r_id].urls.append(
                                Url(
                                    type=l_type,
                                    url=href,
                                    title=title,
                                )
                            )
                        assigned = True

                if not assigned:
                    if len(event.races) == 1:
                        if not any(u.url == href for u in event.races[0].urls):
                            title = a.get_text(strip=True)
                            event.races[0].urls.append(
                                Url(
                                    type=l_type,
                                    url=href,
                                    title=title,
                                )
                            )
                    else:
                        if not any(u.url == href for u in event.urls):
                            title = a.get_text(strip=True)
                            event.urls.append(
                                Url(
                                    type=l_type,
                                    url=href,
                                    title=title,
                                )
                            )

    def _assign_map_positions(self, soup: Tag, event: Event) -> None:
        map_positions = self._extract_map_positions(soup)
        for i, (pos, areas) in enumerate(map_positions):
            if i < len(event.races):
                if pos and not event.races[i].position:
                    event.races[i].position = pos

                if areas:
                    event.races[i].areas.extend(areas)

    def parse_participant_list(self, html_content: str) -> list[Participant]:
        """Parses a start, result, or entry list to extract participants.

        Args:
            html_content: The HTML content of the page.

        Returns:
            A list of participant dictionaries containing:
            - name
            - club
            - class_name
            - start_number (optional)
        """
        soup = BeautifulSoup(html_content, "html.parser")
        participants: list[Participant] = []

        # Eventor lists usually follow the pattern:
        # div.eventClassHeader -> table (startList, resultList, entryList, etc)

        class_headers = soup.find_all("div", class_="eventClassHeader")

        for header in class_headers:
            h3 = header.find("h3")
            if not h3:
                continue
            class_name = h3.get_text(strip=True)

            # The table is usually the next sibling found
            # Sometimes there might be a <p> or <a> in between
            table = header.find_next_sibling("table")
            if not table:
                continue

            # Iterate rows
            tbody = table.find("tbody")
            if not tbody:
                continue

            for row in tbody.find_all("tr"):
                # Use class names to find columns robustly
                name_cell = row.find("td", class_="n")
                club_cell = row.find("td", class_="o")
                num_cell = row.find(
                    "td", class_="b"
                )  # 'b' seems to be bib/start number in start lists

                # Standard Eventor uses 'n' for name and 'o' for club.
                # If combined in a single cell, parsing logic handles it.

                if name_cell and club_cell:
                    name = name_cell.get_text(strip=True)
                    club = club_cell.get_text(strip=True)
                    start_number_str = (
                        num_cell.get_text(strip=True) if num_cell else None
                    )

                    # Data Quality: Normalize start_number
                    start_number: str | int | None = None
                    if start_number_str:
                        # Extract only digits for integer conversion
                        # to handle hidden characters or non-breaking spaces
                        digits_only = "".join(re.findall(r"\d+", start_number_str))
                        if digits_only and digits_only == start_number_str.strip():
                            start_number = int(digits_only)
                        else:
                            start_number = start_number_str.strip()

                    if name:  # basic validation
                        participants.append(
                            Participant(
                                name=name,
                                club=club,
                                class_name=class_name,
                                start_number=start_number,
                            )
                        )

        return participants
