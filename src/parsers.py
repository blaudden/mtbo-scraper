import json
import re
from typing import List, Optional, Dict, Any
from datetime import datetime
from bs4 import BeautifulSoup
from .models import Event, MapPosition, Race, Document

class EventorParser:
    """
    Parses HTML content from Eventor to extract event lists and details.
    """
    
    @staticmethod
    def parse_date_to_iso(date_str: str) -> str:
        """
        Parse various date formats to ISO format (YYYY-MM-DD).
        Handles formats like:
        - "Monday 20 July 2026"
        - "20 July 2026"
        - "2026-07-20"
        """
        if not date_str:
            return ""
        
        # Already in ISO format
        if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
            return date_str
        
        # Try various date formats
        formats = [
            "%A %d %B %Y",  # Monday 20 July 2026
            "%d %B %Y",      # 20 July 2026
            "%A, %d %B %Y",  # Monday, 20 July 2026
            "%d/%m/%Y",      # 20/07/2026
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str.strip(), fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        
        # If no format matches, return original
        return date_str
    
    @staticmethod
    def extract_time_from_date(date_str: str) -> tuple[str, str]:
        """
        Extract time from date string if present.
        Returns (date_only, time) tuple.
        
        Examples:
        - "26 August 2026 at 10:00 local time (UTC+2)" -> ("26 August 2026", "10:00")
        - "Monday 20 July 2026" -> ("Monday 20 July 2026", "")
        """
        # Pattern: "at HH:MM"
        time_match = re.search(r'at (\d{1,2}:\d{2})', date_str)
        if time_match:
            time = time_match.group(1)
            # Remove time part from date
            date_only = re.sub(r'\s*at\s+\d{1,2}:\d{2}.*$', '', date_str)
            return (date_only.strip(), time)
        
        return (date_str, "")
    
    @staticmethod
    def split_multi_value_field(value: str) -> List[str]:
        """
        Split multi-value fields that are concatenated or comma-separated.
        Examples:
        - "FootOMTBOSkiO" -> ["FootO", "MTBO", "SkiO"]
        - "Orientering Terräng, Instruktör på plats" -> ["Orientering Terräng", "Instruktör på plats"]
        - "Henrik JohnssonGustav Jonsson" -> ["Henrik Johnsson", "Gustav Jonsson"]
        - "World Championships\nWorld Ranking Event" -> ["World Championships", "World Ranking Event"]
        """
        # First try newline separation (from <br> or actual newlines)
        if '\n' in value:
            return [v.strip() for v in value.split('\n') if v.strip()]

        # Then try comma separation
        if ',' in value:
            return [v.strip() for v in value.split(',') if v.strip()]
        
        # If all uppercase, assume it's an acronym (e.g. MTBO) and don't split
        if value.isupper():
            return [value]

        # Check for non-ASCII characters (e.g., Swedish ä, ö, å)
        # If present, skip complex splitting to avoid breaking words
        if not value.isascii():
            return [value]

        # Try to split concatenated names (e.g., "Henrik JohnssonGustav Jonsson")
        # Pattern: Capitalized word followed by another capitalized word without space
        # This handles: "FirstnameLastnameFirstnameLastname" -> ["Firstname Lastname", "Firstname Lastname"]
        # Match pattern: Uppercase letter followed by lowercase letters, then another Uppercase (no space)
        # We look for transitions from lowercase to uppercase as split points
        parts = re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*', value)
        
        if len(parts) > 1:
            # Group into pairs (firstname lastname)
            result = []
            i = 0
            while i < len(parts):
                if i + 1 < len(parts):
                    # Check if next part looks like a lastname (single capitalized word)
                    if ' ' not in parts[i] and ' ' not in parts[i+1]:
                        result.append(f"{parts[i]} {parts[i+1]}")
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
        # Pattern: split before uppercase letters that follow lowercase
        parts = re.findall(r'[A-Z][a-z]*[OI]?', value)
        if len(parts) > 1:
            return parts
        
        # Return as single item if no pattern found
        return [value] if value else []
    def parse_event_list(self, html_content: str, country: str) -> List[Event]:
        """
        Parses the event list page and returns a list of Event objects (basic info).
        """
        soup = BeautifulSoup(html_content, 'lxml')
        events = []
        
        # The actual table class in Eventor is not 'eventList' but uses other classes
        # Try multiple selectors to find the event table
        event_rows = soup.select('div#eventList table tbody tr')
        
        if not event_rows:
            # Fallback: try any table within the eventList div
            event_rows = soup.select('div#eventList tbody tr')
        
        for row in event_rows:
            # Skip headers or empty rows if any
            if not row.find('td'):
                continue
                
            try:
                cols = row.find_all('td')
                if len(cols) < 4:
                    continue

                # Column 0: Date
                date_col = cols[0]
                date_span = date_col.find('span', attrs={'data-date': True})
                if date_span:
                    # Parse from data-date attribute "YYYY-MM-DD HH:MM:SS"
                    full_date = date_span['data-date']
                    start_date = full_date.split(' ')[0]
                    end_date = start_date # Default to single day
                else:
                    # Fallback to text parsing if needed, or skip
                    date_text = date_col.get_text(strip=True)
                    # This is hard to parse "ons 1/10", so maybe rely on data-date being present
                    start_date = end_date = "" 

                # Column 1: Name and URL
                name_col = cols[1]
                name_link = name_col.find('a')
                if not name_link:
                    continue
                
                name = name_link.get_text(strip=True)
                url = name_link['href']
                
                event_id_match = re.search(r'/Events/Show/(\d+)', url)
                if not event_id_match:
                    continue
                event_id = f"{country}-{event_id_match.group(1)}"

                # Column 2: Organizer(s)
                org_col = cols[2]
                # Use separator to preserve newlines from <br> tags
                org_text = org_col.get_text(separator='\n', strip=True)
                # Split on newlines to handle multiple organizers
                organizers = [org.strip() for org in org_text.split('\n') if org.strip()]

                # Status might be a class or text
                status = "Active" # Default
                if row.select_one('.cancelled'):
                    status = "Cancelled"
                
                if event_id:
                    events.append(Event(
                        event_id=event_id,
                        name=name,
                        start_date=start_date,
                        end_date=end_date,
                        organizers=organizers,
                        country=country,
                        status=status,
                        url=url
                    ))
            except Exception as e:
                # Log error but continue
                print(f"Error parsing row: {e}")
                continue
                
        return events

    def _extract_livelox_links(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """
        Extracts Livelox links from the event details page.
        """
        links = []
        # Look for Livelox header
        livelox_header = soup.find('h3', string=lambda t: t and 'Livelox' in t)
        if livelox_header:
            # Look for link in following div or p
            container = livelox_header.find_next_sibling('div') or livelox_header.find_next_sibling('p')
            if container:
                link = container.find('a', href=True)
                if link and ('Livelox' in link.get_text() or 'RedirectToLivelox' in link['href']):
                     href = link['href']
                     if href.startswith('/'):
                         href = f"https://eventor.orientering.se{href}"
                     links.append({"name": "Livelox", "url": href})
        
        # Also check for specific class links if they exist in a table (rare on main page but possible)
        # Or just generic "Livelox" link with class 'livelox16x16'
        if not links:
            livelox_links = soup.find_all('a', class_='livelox16x16')
            for link in livelox_links:
                href = link['href']
                if href.startswith('/'):
                    href = f"https://eventor.orientering.se{href}"
                links.append({"name": link.get_text(strip=True) or "Livelox", "url": href})
                
        return links

    def parse_event_details(self, html: str, event: Event) -> Event:
        """
        Parses the event detail page and updates the Event object with details.
        """
        soup = BeautifulSoup(html, 'lxml')
        
        # Extract Properties
        # Look for dl/dt/dd or table structure for properties
        for dt in soup.select('dl.properties dt'):
            dd = dt.find_next_sibling('dd')
            if dd:
                key = dt.get_text(strip=True).rstrip(':')
                value = dd.get_text(strip=True)
                event.properties[key] = value

        # Extract the event info text
        # Find the first p.info that is NOT about embargo restrictions
        # Embargo text typically starts with "Keep in mind that as a competitor" or similar
        info_paragraphs = soup.select('div.showEventInfoContainer p.info')
        for info_p in info_paragraphs:
            # 1. Replace all <br> tags with a newline character (\n)
            for br in info_p.find_all('br'):
                br.replace_with('\n')
            
            # 2. Extract the text with clean formatting
            text = info_p.get_text(separator='\n', strip=True)
            # Skip paragraphs that are part of the map position/embargo section
            if info_p.find_parent(class_=['mapPosition', 'eventCenterMaps']):
                continue
                
            # Skip known embargo text patterns (legacy fallback)
            if text.startswith("Keep in mind that as a competitor"):
                continue
            # This is the actual event info
            event.info_text = text
            break

        # Extract Map Positions (The "HERE" Recipe)
        # 1. General Information & IOF Country
        # Look for table with caption "General information"
        # Also check for "Organising federation" here
        general_info_table = soup.find('caption', string=re.compile(r'General information', re.I))
        if general_info_table:
            table = general_info_table.find_parent('table')
            if table:
                for row in table.find_all('tr'):
                    th = row.find('th')
                    td = row.find('td')
                    if th and td:
                        key = th.get_text(strip=True)
                        # Use separator for splitting
                        value = td.get_text(separator='\n', strip=True)
                        
                        # Skip duplicate fields
                        if key in ['Event', 'Date']:
                            continue
                        
                        
                        # Known multi-value fields - ONLY PLURAL FORMS
                        # Singular forms should NOT be split
                        multi_value_keys = [
                            'Disciplines',  # plural only (singular: Discipline)
                            'Event attributes',  # plural only (singular: Event attribute)
                            'Event types',  # plural only (singular: Event type)
                            'Course setters',  # plural only (singular: Course setter)
                            'Organising clubs'  # plural only (singular: Organising club)
                        ]
                        
                        if key in multi_value_keys:
                            value_list = self.split_multi_value_field(value)
                            event.attributes[key] = value_list
                        else:
                            event.attributes[key] = value
                        
                        # IOF Country Extraction
                        if "Organising federation" in key:
                            # Extract country name from the value
                            event.country = value
                
                # Remove duplicate organizer info from attributes
                # (already stored in event.organizers)
                if "Organisers" in event.attributes:
                    del event.attributes["Organisers"]
                if "Organiser" in event.attributes:
                    del event.attributes["Organiser"]

        # 2. Contact Details
        contact_table = soup.find('caption', string=re.compile(r'Contact', re.I))
        if contact_table:
            table = contact_table.find_parent('table')
            if table:
                for row in table.find_all('tr'):
                    th = row.find('th')
                    td = row.find('td')
                    if th and td:
                        key = th.get_text(strip=True)
                        
                        # Check for spam-protected email
                        img = td.find('img', class_='emailSpamProtection')
                        if img and 'src' in img.attrs:
                            # Extract hex from URL path
                            hex_str = img['src'].split('/')[-1]
                            try:
                                value = bytes.fromhex(hex_str).decode('utf-8')
                            except:
                                value = ""
                        else:
                            # Use separator to preserve newlines from <br> tags
                            value = td.get_text(separator='\n', strip=True)
                        
                        # Known multi-value contact fields - ONLY PLURAL FORMS
                        # Singular forms (Event director, Course setter, Organising club) should NOT be split
                        multi_value_contact_keys = [
                            'Event directors',  # plural only
                            'Course setters'    # plural only
                        ]
                        
                        if key in multi_value_contact_keys and value:
                            value_list = self.split_multi_value_field(value)
                            event.contact[key] = value_list
                        else:
                            event.contact[key] = value

        # 3. Classes
        class_table = soup.find('caption', string=re.compile(r'Class information', re.I))
        if class_table:
            table = class_table.find_parent('table')
            if table:
                # Check if it says "no classes"
                if "no classes" in table.get_text().lower():
                    event.classes = []
                else:
                    # Extract classes from rows
                    # Usually "Classes" is a key
                    classes_row = table.find('th', string=re.compile(r'Classes', re.I))
                    if classes_row:
                        td = classes_row.find_next_sibling('td')
                        if td:
                            # Split by comma or newlines
                            event.classes = [c.strip() for c in td.get_text(separator=',').split(',') if c.strip()]

        # 4. Races / Stages
        # Look for "Stage", "Race", or "Etapp" captions (Swedish Eventor uses "Etapp" even in English mode)
        race_captions = soup.find_all('caption', string=re.compile(r'(Stage|Race|Etapp)', re.I))
        for cap in race_captions:
            table = cap.find_parent('table')
            if table:
                race_name = cap.get_text(strip=True)
                
                # Extract race_id from link if present
                race_id = ""
                link = cap.find('a')
                if link and 'href' in link.attrs:
                    match = re.search(r'/Events/Show/(\d+)', link['href'])
                    if match:
                        race_id = match.group(1)

                race_data = {}
                for row in table.find_all('tr'):
                    th = row.find('th')
                    td = row.find('td')
                    if th and td:
                        key = th.get_text(strip=True).lower()
                        val = td.get_text(strip=True)
                        race_data[key] = val
                
                # Extract and parse date
                date_str = race_data.get('date', '')
                date_only, time = self.extract_time_from_date(date_str)
                iso_date = self.parse_date_to_iso(date_only)
                
                # Map keys to Race object
                r = Race(
                    race_id=race_id,
                    name=race_name,
                    date=iso_date,
                    time=time,
                    distance=race_data.get('race distance', race_data.get('competition format', '')),
                    night_or_day=race_data.get('time of event', '')
                )
                event.races.append(r)

        # IOF: "Competitions" section
        # If we haven't found races yet (SWE/NOR style), try IOF style
        if not event.races:
            # Find all eventInfo tables
            tables = soup.select('table.eventInfo')
            for table in tables:
                caption = table.find('caption')
                if not caption: continue
                cap_text = caption.get_text(strip=True)
                
                # Skip known sections
                if any(x in cap_text.lower() for x in ['general', 'contact', 'class', 'entry']):
                    continue
                
                # Assume it's a race if it has Date/Distance/Format
                race_data = {}
                is_race = False
                for row in table.find_all('tr'):
                    th = row.find('th')
                    td = row.find('td')
                    if th and td:
                        key = th.get_text(strip=True).lower()
                        val = td.get_text(strip=True)
                        race_data[key] = val
                        if 'date' in key or 'format' in key or 'distance' in key:
                            is_race = True
                
                if is_race:
                    # Extract race_id from link if present
                    race_id = ""
                    link = caption.find('a')
                    if link and 'href' in link.attrs:
                        match = re.search(r'/Events/Show/(\d+)', link['href'])
                        if match:
                            race_id = match.group(1)

                    # Extract and parse date
                    date_str = race_data.get('date', '')
                    date_only, time = self.extract_time_from_date(date_str)
                    iso_date = self.parse_date_to_iso(date_only)
                    
                    r = Race(
                        race_id=race_id,
                        name=cap_text,
                        date=iso_date,
                        time=time,
                        distance=race_data.get('competition format', race_data.get('distance', '')),
                        night_or_day=""  # IOF doesn't typically have this field in competitions table
                    )
                    event.races.append(r)

        # 5. Documents
        # Look for "Documents and links" header
        doc_header = soup.find(lambda tag: tag.name in ['h2', 'h3', 'h4'] and 'Documents' in tag.get_text())
        if doc_header:
            # Try to find ul.documents nearby
            doc_list = doc_header.find_next('ul', class_='documents')
            if doc_list:
                for li in doc_list.find_all('li'):
                    link = li.find('a', class_='documentName')
                    if not link:
                        # Maybe just 'a' with class 'external'?
                        link = li.find('a', class_='external')
                        # But exclude the icon link
                        if link and link.find('img'):
                            # This is the icon link, find the next 'a'
                            link = li.find_all('a')[-1] # Last link usually text
                    
                    if link:
                        name = link.get_text(strip=True)
                        url = link['href']
                        
                        # Type from icon
                        icon = li.find('img', class_='documentIcon')
                        doc_type = "unknown"
                        if icon:
                            doc_type = icon.get('title', 'unknown')
                        elif "external" in link.get('class', []):
                            doc_type = "external"
                            
                        event.documents.append(Document(name, url, doc_type))

        # Extract map positions
        map_positions = self._extract_map_positions(soup)
        
        # Extract race IDs from eventInfoBox sections for multi-race events
        # This handles cases where race IDs aren't in the caption tables
        # but are in the "Resultat, etapp X" and "Starttider, etapp X" boxes
        race_id_map = {}  # Maps race index (0-based) to race_id
        
        # Look for eventInfoBox divs with h3 headers containing "etapp" or "stage"
        info_boxes = soup.find_all('div', class_='eventInfoBox')
        for box in info_boxes:
            h3 = box.find('h3')
            if not h3:
                continue
            
            header_text = h3.get_text(strip=True).lower()
            
            # Check if this is a result or start list box
            if any(keyword in header_text for keyword in ['resultat', 'result', 'starttider', 'start times', 'start list']):
                # Extract race number from header (e.g., "Resultat, etapp 1" -> 1)
                match = re.search(r'(etapp|stage|race)\s+(\d+)', header_text, re.I)
                if match:
                    race_num = int(match.group(2))
                    race_index = race_num - 1  # Convert to 0-based index
                    
                    # Find the first link with eventRaceId in this box
                    link = box.find('a', href=re.compile(r'eventRaceId='))
                    if link:
                        href = link['href']
                        race_id_match = re.search(r'eventRaceId=(\d+)', href)
                        if race_id_match:
                            extracted_race_id = race_id_match.group(1)
                            # Store this mapping
                            if race_index not in race_id_map:
                                race_id_map[race_index] = extracted_race_id
        
        # Update races with extracted race IDs if they don't have one
        for idx, race in enumerate(event.races):
            if not race.race_id and idx in race_id_map:
                race.race_id = race_id_map[idx]
        
        # Extract List URLs and assign to races
        # Look for links in toolbar or menu
        list_urls = {
            'entry': [],
            'start': [],
            'result': []
        }
        
        for a in soup.find_all('a', href=True):
            href = a['href']
            # Avoid "PressResultList" or other variants if possible, prefer standard lists
            if '/Events/Entries' in href and 'groupBy=EventClass' in href:
                list_urls['entry'].append(href)
            elif '/Events/StartList' in href and 'groupBy=EventClass' in href:
                list_urls['start'].append(href)
            elif '/Events/ResultList' in href and 'groupBy=EventClass' in href and 'PressResultList' not in href:
                list_urls['result'].append(href)
        
        # Helper to extract race ID from URL
        def extract_race_id_from_url(url: str) -> Optional[str]:
            match = re.search(r'eventRaceId=(\d+)', url)
            return match.group(1) if match else None

        # Assign to races
        if not event.races:
            # Create default race for single event
            # Use event_id numeric part as race_id if possible
            race_id = event.event_id.split('-')[-1] if '-' in event.event_id else event.event_id
            
            r = Race(
                race_id=race_id,
                name=event.name,
                date=event.start_date,
                time="", 
                distance=event.attributes.get('Race distance', ''),
                night_or_day=event.attributes.get('Time of event', '')
            )
            event.races.append(r)
        
        # Now assign list URLs to races (after races are created and race_ids are set)
        for list_type, urls in list_urls.items():
            for url in urls:
                race_id = extract_race_id_from_url(url)
                
                if race_id:
                    # Find the race with this ID
                    for race in event.races:
                        if race.race_id == race_id:
                            if list_type == 'entry':
                                race.entry_list_url = url
                            elif list_type == 'start':
                                race.start_list_url = url
                            elif list_type == 'result':
                                race.result_list_url = url
                            break
                else:
                    # No race ID in URL - single race event
                    # Assign to first (and likely only) race
                    if event.races:
                        if list_type == 'entry':
                            event.races[0].entry_list_url = url
                        elif list_type == 'start':
                            event.races[0].start_list_url = url
                        elif list_type == 'result':
                            event.races[0].result_list_url = url
            
            
        # Assign map positions
        # For IOF events, map positions typically belong to the event itself
        # For SWE/NOR events, they belong to individual races
        if event.country == "IOF" or event.country.startswith("IOF"):
            # Assign to event level
            event.map_positions = map_positions
        else:
            # Assign to races based on raceid
            for mp in map_positions:
                # 1-based index usually corresponds to race order
                idx = mp.raceid - 1
                if 0 <= idx < len(event.races):
                    event.races[idx].map_positions.append(mp)
        
        # Extract Livelox links from main page
        livelox_links = self._extract_livelox_links(soup)
        if livelox_links:
            # If single race, assign to it
            if len(event.races) == 1:
                event.races[0].livelox_links = livelox_links
            # If multiple races, we might need more logic, but for now only assign if it's clear
            # or if the link is generic for the event.
            # The user said "max one per race".
            # If we found links, and have multiple races, maybe we should assign to all?
            # Or maybe the links are specific?
            # For now, let's follow the "single race" rule strictly as requested for list counts,
            # but for Livelox, if it's on the main page, it might be for the whole event.
            # However, to be safe and follow "max one per race", we'll just assign to the first one 
            # if it's a single day event.
            # If it's multi-day, usually stages have their own pages.
            pass
        
        return event

    def parse_list_count(self, html: str) -> Dict[str, Any]:
        """
        Parses an Entry, Start, or Result list page and returns participant counts.
        Returns a dict: {
            "total_count": int,
            "class_counts": Dict[str, int]
        }
        """
        soup = BeautifulSoup(html, 'lxml')
        total_count = 0
        class_counts = {}
        
        # Strategy:
        # 1. Find all class headers (div.eventClassHeader)
        # 2. For each header, find the associated table
        # 3. Count rows in that table
        
        headers = soup.select('div.eventClassHeader')
        for header in headers:
            # Extract class name
            class_name_tag = header.find('h3')
            if not class_name_tag:
                continue
            class_name = class_name_tag.get_text(strip=True)
            
            # Find associated table (usually next sibling, or close by)
            table = header.find_next_sibling('table')
            if not table:
                continue
                
            tbody = table.find('tbody')
            if tbody:
                rows = tbody.find_all('tr')
                count = len(rows)
                class_counts[class_name] = count
                total_count += count
                
        # Fallback for pages without class headers (e.g. simple lists)?
        # If no class headers found, look for any list table and count total
        if total_count == 0:
            tables = soup.select('table.resultList, table.entryList, table.startList, table.competitorList')
            for table in tables:
                tbody = table.find('tbody')
                if tbody:
                    rows = tbody.find_all('tr')
                    total_count += len(rows)
                    
        return {
            "total_count": total_count,
            "class_counts": class_counts
        }

    def _extract_map_positions(self, soup: BeautifulSoup) -> List[MapPosition]:
        """
        Extracts map positions using the specific "HERE" recipe.
        """
        map_positions = []
        
        # Select 'input.options' under each 'div.mapPosition'
        options_inputs = soup.select('.mapPosition input.options')
        
        for i, input_el in enumerate(options_inputs):
            try:
                raw_value = input_el.get('value', '')
                # Unescape HTML entities if needed (BS4 usually handles this, but value might be raw)
                # The recipe says: JSON string (HTML-encoded in raw HTML; already decoded in the DOM)
                # In BS4, .get('value') returns the decoded string usually.
                
                # However, if it contains &quot;, we might need to replace it.
                # Let's try standard parsing first, then fallback.
                try:
                    data = json.loads(raw_value)
                except json.JSONDecodeError:
                    # Try replacing &quot; with "
                    clean_value = raw_value.replace('&quot;', '"')
                    data = json.loads(clean_value)
                
                lat = float(data.get('latitude') or data.get('centerLatitude') or 0)
                lon = float(data.get('longitude') or data.get('centerLongitude') or 0)
                
                polygon = None
                if 'polygonVertices' in data and isinstance(data['polygonVertices'], list):
                    polygon = []
                    for v in data['polygonVertices']:
                        p_lat = float(v.get('Latitude', 0))
                        p_lon = float(v.get('Longitude', 0))
                        polygon.append([p_lon, p_lat]) # GeoJSON order: [lon, lat]
                    
                    # Close the ring if needed
                    if polygon and (polygon[0] != polygon[-1]):
                        polygon.append(polygon[0])

                map_positions.append(MapPosition(
                    raceid=i + 1,
                    lat=lat,
                    lon=lon,
                    polygon=polygon
                ))
            except Exception as e:
                print(f"Error extracting map position {i}: {e}")
                continue
                
        return map_positions
