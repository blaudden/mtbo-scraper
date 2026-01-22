import json
import logging
import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from src.models import Area, Document, Event, Official, Organiser, Position, Race, Url
from src.utils.crypto import Crypto
from src.utils.date_and_time import (
    extract_time_from_date,
    format_iso_datetime,
    parse_date_to_iso,
)


class EventorParser:
    """Parses HTML content from Eventor to extract event lists and details.

    This parser handles both single-day and multi-day events, including
    extraction of race details, results/start list links, and document links.
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger(__name__)

    @staticmethod
    def split_multi_value_field(value: str) -> list[str]:
        """Splits multi-value fields that are concatenated or comma-separated.

        Args:
            value: The input string to split.

        Returns:
            A list of extracted string values.
        """
        # First try newline separation (from <br> or actual newlines)
        if "\n" in value:
            return [v.strip() for v in value.split("\n") if v.strip()]

        # Then try comma separation
        if "," in value:
            return [v.strip() for v in value.split(",") if v.strip()]

        # If all uppercase, assume it's an acronym (e.g. MTBO) and don't split
        if value.isupper():
            return [value]

        # Check for non-ASCII characters (e.g., Swedish ä, ö, å)
        # If present, skip complex splitting to avoid breaking words
        if not value.isascii():
            return [value]

        # Try to split concatenated names (e.g., "Henrik JohnssonGustav Jonsson")
        parts = re.findall(r"[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*", value)

        if parts:
            # Group into pairs (firstname lastname)
            result = []
            i = 0
            while i < len(parts):
                if i + 1 < len(parts):
                    # Check if next part looks like a lastname (single capitalized word)
                    if " " not in parts[i] and " " not in parts[i + 1]:
                        result.append(f"{parts[i]} {parts[i + 1]}")
                        i += 2
                    else:
                        result.append(parts[i])
                        i += 1
                else:
                    result.append(parts[i])
                    i += 1
            if result:
                return result

        # Try to split camelCase/PascalCase patterns (for disciplines)
        parts = re.findall(r"[A-Z][a-z]*[OI]?", value)
        if len(parts) > 1:
            return parts

        # Return as single item if no pattern found
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

    def _map_classification(self, attributes: dict[str, str]) -> str | None:
        for k, v in attributes.items():
            # Check keys like "Event classification", "Event type"
            if "class" in k.lower() or "type" in k.lower():
                vl = v.lower()
                if "international" in vl or "wre" in vl:
                    return "International"
                if "national" in vl or "sm" in vl:
                    return "National"
                if "region" in vl or "dm" in vl:
                    return "Regional"
                if "local" in vl or "club" in vl:
                    return "Local"
        return None

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

    def parse_event_list(self, html_content: str, country: str) -> list[Event]:
        """Parses the event list page and returns a list of Event objects.

        Args:
            html_content: The HTML content of the event list page.
            country: The country code (e.g. "SWE").

        Returns:
            A list of Event objects with basic information.

        Example:
            >>> parser = EventorParser()
            >>> html = "<html>...</html>"  # Eventor event list HTML
            >>> events = parser.parse_event_list(html, "SWE")
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
            if not row.find("td"):
                continue

            try:
                cols = row.find_all("td")
                if len(cols) < 4:
                    continue

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
                    continue

                name = name_link.get_text(strip=True)
                url = str(name_link["href"])

                event_id_match = re.search(r"/Events/Show/(\d+)", url)
                if not event_id_match:
                    continue
                source_id = event_id_match.group(1)
                event_id = f"{country}_{source_id}"

                # Column 2: Organizer(s)
                org_col = cols[2]
                org_text = org_col.get_text(separator="\n", strip=True)
                organiser_names = [
                    org.strip() for org in org_text.split("\n") if org.strip()
                ]
                organisers = [
                    Organiser(name=o, country_code=country) for o in organiser_names
                ]

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

                events.append(
                    Event(
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
                )
            except Exception as e:
                print(f"Error parsing row: {e}")
                continue

        return events

    def _extract_links_from_infoboxes(self, soup: Tag) -> list[dict[str, Any]]:
        """Extracts Start/Result/Entry/Livelox links from eventInfoBox containers.

        Args:
            soup: The BeautifulSoup object of the page.

        Returns:
            A list of dictionaries containing 'race_index' (1-based), 'type', and 'url'.
        """
        from typing import Any

        links: list[dict[str, Any]] = []
        boxes = soup.find_all("div", class_="eventInfoBox")

        # Track counters per type to handle sequences without explicit stage numbers
        counters = {"StartList": 0, "ResultList": 0, "EntryList": 0, "Livelox": 0}

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

            if not l_type:
                continue

            counters[l_type] += 1

            # Default to ordinal position for this type
            race_index = counters[l_type]

            # Try to extract explicit stage number "etapp X", "stage X", ...
            index_match = re.search(
                r"(?:etapp|stage|race|del|day)\s*(\d+)", header_text, re.I
            )
            if index_match:
                race_index = int(index_match.group(1))

            # A box can sometimes have multiple links (e.g. variants of start lists)
            # in that case we need to check for duplicates and only add the first one
            for a in box.find_all("a", href=True):
                href = a["href"]
                # Store relative URL as found

                # Check duplication
                if not any(
                    link["race_index"] == race_index
                    and link["type"] == l_type
                    and link["url"] == href
                    for link in links
                ):
                    links.append(
                        {"race_index": race_index, "type": l_type, "url": href}
                    )

        return links

    def parse_event_details(self, html: str, event: Event) -> Event:
        """Parses the event detail page and updates the Event object with details.

        Args:
            html: The HTML content of the event detail page.
            event: The Event object to update.

        Returns:
            The updated Event object.

        Example:
            >>> parser = EventorParser()
            >>> event = Event(id="SWE_123", name="Test", ...)
            >>> html = "<html>...</html>"  # Eventor event detail HTML
            >>> detailed_event = parser.parse_event_details(html, event)
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
        attributes, venue_country = self._extract_attributes_and_country(
            content_root,
            event,
        )
        self._apply_attributes(event, attributes)

        # 2. Info Text
        event.information = self._extract_info_text(content_root)

        # 3. Contacts / Officials
        officials, web_urls = self._extract_officials_and_urls(content_root)
        event.officials.extend(officials)
        event.urls.extend(web_urls)

        # 4. Classes
        event.classes = self._extract_classes_list(content_root)

        # 5. Documents
        event.documents = self._extract_documents_list(content_root)

        # 6. Races extraction
        event.races = self._extract_races_strategy(
            content_root,
            event,
            attributes,
            venue_country,
        )

        # 7. Service Links
        self._assign_service_links(content_root, event)

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
            except Exception:
                continue
        return results

    def parse_list_count(self, html: str) -> dict[str, Any]:
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
            if table:
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

        return {"total_count": total_count, "class_counts": class_counts}

    def _extract_attributes_and_country(
        self, soup: Tag, event: Event
    ) -> tuple[dict[str, str], str]:
        """Extracts general attributes and venue country from the
        General Information table.

        Args:
            soup: The BeautifulSoup object.
            event: The Event object (used for ID-based country fallback).

        Returns:
            A tuple containing a dictionary of attributes and the venue country string.
        """
        attributes = {}
        venue_country = event.id.split("_")[0]

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
                        # Skip Event and Date rows
                        if key not in ["Event", "Date"]:
                            attributes[key] = value

                        if venue_country == "IOF" and "federation" in key.lower():
                            venue_country = value.strip()

        return attributes, venue_country

    def _apply_attributes(self, event: Event, attributes: dict[str, str]) -> None:
        """Applies extracted attributes to the Event object.

        Args:
            event: The Event object to update.
            attributes: The dictionary of attributes.
        """
        event.start_time = parse_date_to_iso(event.start_time)
        event.end_time = parse_date_to_iso(event.end_time)
        event.classification = self._map_classification(attributes)
        event.form = self._map_form(attributes)

        for k, v in attributes.items():
            if "district" in k.lower() or "region" in k.lower():
                event.region = v
                break

        for k, v in attributes.items():
            if "punching" in k.lower() or "stämpling" in k.lower():
                event.punching_system = v
                break

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
                    urls.append(Url(type="Website", url=a_tag["href"]))

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

    def _extract_documents_list(self, soup: Tag) -> list[Document]:
        """Extracts linked documents (Bulletins, Start Lists, etc.).

        Args:
            soup: The BeautifulSoup object.

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
                url = link["href"]

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

                documents.append(Document(type=doc_type, title=name, url=str(url)))

        return documents

    def _extract_races_strategy(
        self,
        soup: Tag,
        event: Event,
        attributes: dict[str, str],
        venue_country: str,
    ) -> list[Race]:
        races = []

        race_captions = soup.find_all(
            "caption",
            string=re.compile(r"(Stage|Race|Etapp)", re.I),
        )
        if race_captions:
            for idx, cap in enumerate(race_captions):
                races.append(self._parse_race_table(cap, idx + 1, event, venue_country))

            self._enrich_races_from_infoboxes(soup, races)
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
                        caption, len(races) + 1, event, venue_country
                    )
                )

        if races:
            self._enrich_races_from_infoboxes(soup, races)
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
        self, caption_tag: Tag, race_number: int, event: Event, venue_country: str
    ) -> Race:
        table = caption_tag.find_parent("table")
        race_name = caption_tag.get_text(strip=True)
        race_data = {}

        if table:
            for row in table.find_all("tr"):
                th = row.find("th")
                td = row.find("td")
                if th and td:
                    race_data[th.get_text(strip=True).lower()] = td.get_text(strip=True)

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

        race_id = None
        links = table.find_all("a", href=True) if table else []
        caption_link = caption_tag.find("a", href=True)
        if caption_link and isinstance(caption_link, Tag):
            links.append(caption_link)

        for link in links:
            href_val = link["href"]
            match = re.search(r"eventRaceId=(\d+)", str(href_val))
            if match:
                race_id = match.group(1)
                break

        race = Race(
            race_number=race_number,
            name=race_name,
            datetimez=race_datetime,
            discipline=discipline,
            night_or_day=self._map_night_or_day(race_data.get("time of event", "")),
            punching_system=event.punching_system,
        )
        race._internal_eventor_id = race_id
        return race

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

    def _enrich_races_from_infoboxes(self, soup: Tag, races: list[Race]) -> None:
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

    def _assign_service_links(self, soup: Tag, event: Event) -> None:
        box_links = self._extract_links_from_infoboxes(soup)
        assigned_urls = set()

        for bl in box_links:
            idx = bl.get("race_index")
            url_obj = Url(type=bl["type"], url=bl["url"])
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
            href = str(href_val)
            if href in assigned_urls:
                continue

            l_type = None
            if "/Events/Entries" in href and "groupBy=EventClass" in href:
                l_type = "EntryList"
            elif "/Events/StartList" in href:
                l_type = "StartList"
            elif "/Events/ResultList" in href:
                l_type = "ResultList"
            elif (
                "livelox" in str(a.get("class", "")).lower()
                or "livelox" in href.lower()
            ):
                a_class = a.get("class", "")
                a_class_str = str(a_class)
                if "livelox16x16" in a_class_str or "Livelox" in a.get_text():
                    l_type = "Livelox"

            if l_type:
                race_id_match = re.search(r"eventRaceId=(\d+)", str(href))
                assigned = False

                if race_id_match and race_map:
                    r_id = race_id_match.group(1)
                    if r_id in race_map:
                        if not any(u.url == href for u in race_map[r_id].urls):
                            race_map[r_id].urls.append(Url(type=l_type, url=href))
                        assigned = True

                if not assigned:
                    if len(event.races) == 1:
                        if not any(u.url == href for u in event.races[0].urls):
                            event.races[0].urls.append(Url(type=l_type, url=href))
                    else:
                        if not any(u.url == href for u in event.urls):
                            event.urls.append(Url(type=l_type, url=href))

    def _assign_map_positions(self, soup: Tag, event: Event) -> None:
        map_positions = self._extract_map_positions(soup)
        for i, (pos, areas) in enumerate(map_positions):
            if i < len(event.races):
                if pos and not event.races[i].position:
                    event.races[i].position = pos

                if areas:
                    event.races[i].areas.extend(areas)
