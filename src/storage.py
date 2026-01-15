import json
import os
import logging
from typing import List, Dict
from .models import Event

logger = logging.getLogger(__name__)

class Storage:
    def __init__(self, filepath: str):
        self.filepath = filepath

    def load(self) -> Dict[str, Event]:
        """Loads events from the JSON file."""
        if not os.path.exists(self.filepath):
            return {}
        
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                events = {}
                for item in data:
                    # Reconstruct Event objects
                    # Note: This is a simplified reconstruction. 
                    # Ideally, we'd have a from_dict method on Event.
                    # For now, we'll just store the dicts or implement a basic reconstruction if needed for logic.
                    # Actually, for merging, we mainly need the IDs.
                    # Let's keep it simple: load as dicts, but return a dict mapping ID -> Event object
                    # To do this properly, we should add from_dict to models.py, but for now let's just return raw dicts 
                    # or handle it here.
                    
                    # Let's assume we want to work with Event objects.
                    # I'll implement a basic reconstruction here for now.
                    e = Event(
                        event_id=item['id'],
                        name=item['name'],
                        start_date=item.get('start_date', ''),
                        end_date=item.get('end_date', ''),
                        organizers=item.get('organizers', []),
                        country=item['country'],
                        status=item['status'],
                        url=item['url']
                    )
                    # Populate other fields... this is getting tedious without a proper deserializer.
                    # Maybe we just keep existing data as dicts and only overwrite with new Event objects?
                    # Yes, that's safer.
                    events[item['id']] = item
                return events
        except Exception as e:
            logger.error(f"Failed to load storage: {e}")
            return {}

    def save(self, events: List[Event]):
        """Saves a list of Event objects to the JSON file, merging with existing data."""
        existing_data = self.load()
        
        # Update existing data with new events
        for event in events:
            existing_data[event.event_id] = event.to_dict()
            
        # Convert back to list and sort by start_date then ID
        sorted_events = sorted(existing_data.values(), key=lambda x: (x.get('start_date', ''), x.get('id', '')))
        
        try:
            with open(self.filepath, 'w', encoding='utf-8') as f:
                json.dump(sorted_events, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved {len(sorted_events)} events to {self.filepath}")
            return sorted_events
        except Exception as e:
            logger.error(f"Failed to save storage: {e}")
            return []
