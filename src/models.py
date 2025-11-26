from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

@dataclass
class MapPosition:
    raceid: int
    lat: float
    lon: float
    polygon: Optional[List[List[float]]] = None

@dataclass
class Document:
    name: str
    url: str
    type: str

@dataclass
class Race:
    """
    Represents a single race/stage within a multi-day event.
    
    Date format: ISO 8601 (YYYY-MM-DD)
    Time format: Local time in HH:MM format (24-hour)
    Night or day: Indicates day/night racing (values: "day", "night", "combined day and night")
    """
    race_id: str # Eventor race ID (e.g. "52358") or synthetic ID (e.g. "50597-stage-1") if not available from Eventor
    name: str  # e.g., "Stage 1", "Middle", "Etapp 1"
    date: str  # ISO format: YYYY-MM-DD
    time: str  # Local time: HH:MM (24-hour format)
    distance: str  # Unified field for distance/format (e.g., "Long", "Middle", "Sprint")
    night_or_day: str = ""  # Day/night indicator: "day", "night", or "combined day and night"
    
    # Race-specific details
    map_positions: List[MapPosition] = field(default_factory=list)
    
    # List URLs (race-specific)
    entry_list_url: Optional[str] = None
    start_list_url: Optional[str] = None
    result_list_url: Optional[str] = None
    
    # List data (structured as dicts with total_count and class_counts)
    entry_list: Optional[Dict[str, Any]] = None
    start_list: Optional[Dict[str, Any]] = None
    result_list: Optional[Dict[str, Any]] = None
    
    livelox_links: List[Dict[str, str]] = field(default_factory=list) # [{"name": "...", "url": "..."}]

@dataclass
class Event:
    """
    Represents an orienteering event.
    
    Date formats:
    - start_date, end_date: ISO 8601 (YYYY-MM-DD)
    - For multi-day events, end_date is the date of the last race
    """
    event_id: str # Format: {Country}-{EventId} (e.g. SWE-12345)
    name: str
    start_date: str  # ISO format: YYYY-MM-DD
    end_date: str  # ISO format: YYYY-MM-DD
    organizers: List[str]
    country: str # ISO 3166-1 alpha-3 code (e.g. SWE, NOR, IOF)
    status: str
    url: str
    
    # Details
    info_text: str = "" # Free text from info box
    attributes: Dict[str, Any] = field(default_factory=dict) # General info (values can be str or List[str])
    contact: Dict[str, str] = field(default_factory=dict)
    classes: List[str] = field(default_factory=list) # List of class names or types
    races: List[Race] = field(default_factory=list)
    documents: List[Document] = field(default_factory=list)
    map_positions: List[MapPosition] = field(default_factory=list) # Event-level map positions (for IOF events)
    
    def to_dict(self):
        return {
            "id": self.event_id,
            "name": self.name,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "organizers": self.organizers,
            "country": self.country,
            "status": self.status,
            "url": self.url,
            "info_text": self.info_text,
            "attributes": self.attributes,
            "contact": self.contact,
            "classes": self.classes,
            "races": [
                {
                    "race_id": r.race_id,
                    "name": r.name,
                    "date": r.date,
                    "time": r.time,
                    "distance": r.distance,
                    "night_or_day": r.night_or_day,
                    "entry_list_url": r.entry_list_url,
                    "start_list_url": r.start_list_url,
                    "result_list_url": r.result_list_url,
                    "entry_list": r.entry_list,
                    "start_list": r.start_list,
                    "result_list": r.result_list,
                    "livelox_links": r.livelox_links,
                    "map_positions": [
                        {
                            "raceid": mp.raceid,
                            "lat": mp.lat,
                            "lon": mp.lon,
                            "polygon": mp.polygon
                        } for mp in r.map_positions
                    ]
                } for r in self.races
            ],
            "documents": [
                {
                    "name": d.name,
                    "url": d.url,
                    "type": d.type
                } for d in self.documents
            ],
            "map_positions": [
                {
                    "raceid": mp.raceid,
                    "lat": mp.lat,
                    "lon": mp.lon,
                    "polygon": mp.polygon
                } for mp in self.map_positions
            ]
        }

