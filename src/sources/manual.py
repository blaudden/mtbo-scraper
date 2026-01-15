import os
import yaml
import logging
from typing import List, Optional
from src.models import Event, Race, Document, MapPosition

logger = logging.getLogger(__name__)

class ManualSource:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir

    def load_events(self) -> List[Event]:
        """
        Recursively scans base_dir for event.yaml files and loads them.
        """
        events = []
        if not os.path.exists(self.base_dir):
            logger.warning(f"Manual events directory not found: {self.base_dir}")
            return events

        for root, dirs, files in os.walk(self.base_dir):
            if "event.yaml" in files:
                yaml_path = os.path.join(root, "event.yaml")
                try:
                    event = self._parse_event_yaml(yaml_path)
                    if event:
                        events.append(event)
                except Exception as e:
                    logger.error(f"Failed to parse manual event at {yaml_path}: {e}")
        
        logger.info(f"Loaded {len(events)} manual events from {self.base_dir}")
        return events

    def _parse_event_yaml(self, yaml_path: str) -> Optional[Event]:
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        if not data:
            return None

        # Resolve document paths relative to the yaml file
        event_dir = os.path.dirname(yaml_path)
        
        documents = []
        for doc_data in data.get('documents', []):
            url = doc_data.get('url', '')
            if url.startswith('file://'):
                filename = url.replace('file://', '')
                # Create absolute path or relative to storage execution?
                # For now, let's keep it relative to the manual_events dir structure if possible
                # But to serve it, we might need to know where it is.
                # Let's verify it exists
                file_path = os.path.join(event_dir, filename)
                if not os.path.exists(file_path):
                    logger.warning(f"Document not found: {file_path}")
                # We can store the full path for now, or relative path from repo root
                # Using relative path from working directory is safer for portability if running from root
                rel_path = os.path.relpath(file_path, os.getcwd())
                url = f"file://{rel_path}"
            
            documents.append(Document(
                name=doc_data.get('name', ''),
                url=url,
                type=doc_data.get('type', 'Other')
            ))

        races = []
        for race_data in data.get('races', []):
            races.append(Race(
                race_id=f"{data.get('id')}-{race_data.get('name').replace(' ', '-').lower()}",
                name=race_data.get('name'),
                date=race_data.get('date'),
                time=race_data.get('time', '00:00'),
                distance=race_data.get('distance'),
                night_or_day=race_data.get('night_or_day', 'day')
            ))

        return Event(
            event_id=data.get('id'),
            name=data.get('name'),
            start_date=data.get('start_date'),
            end_date=data.get('end_date'),
            organizers=data.get('organizers', []),
            country=data.get('country'),
            status=data.get('status', 'Planned'),
            url=data.get('url', ''),
            documents=documents,
            races=races,
            classes=data.get('classes', []),
            info_text=data.get('info_text', ''),
            attributes=data.get('attributes', {}),
            contact=data.get('contact', {})
        )
