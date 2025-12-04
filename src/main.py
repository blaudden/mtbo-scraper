import click
import logging
import sys
from datetime import datetime, timedelta
from typing import List

# Use absolute imports for script execution
from src.storage import Storage
from src.sources.eventor import EventorSource
from src.models import Event

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("scraper.log")
    ]
)
logger = logging.getLogger(__name__)

# Configuration
EVENTOR_CONFIGS = [
    {"country": "SWE", "url": "https://eventor.orientering.se"},
    {"country": "NOR", "url": "https://eventor.orientering.no"},
    {"country": "IOF", "url": "https://eventor.orienteering.org"}
]

@click.command()
@click.option('--start-date', help='Start date (YYYY-MM-DD)')
@click.option('--end-date', help='End date (YYYY-MM-DD)')
@click.option('--output', default='mtbo_events.json', help='Output JSON file')
def main(start_date, end_date, output):
    """MTBO Eventor Scraper"""
    logger.info("Starting MTBO Scraper")
    
    # Date Handling Logic
    if not start_date:
        # Default to 4 weeks ago
        start_date = (datetime.now() - timedelta(weeks=4)).strftime('%Y-%m-%d')
    
    start_dt = datetime.strptime(start_date, '%Y-%m-%d')
    max_duration = timedelta(days=456) # Approx 15 months
    
    if not end_date:
        # Default to start_date + 15 months
        end_dt = start_dt + max_duration
        end_date = end_dt.strftime('%Y-%m-%d')
    else:
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        if end_dt - start_dt > max_duration:
            logger.error(f"Date range exceeds 15 months limit. Start: {start_date}, End: {end_date}")
            raise click.BadParameter("Date range cannot exceed 15 months.")

    logger.info(f"Scraping events from {start_date} to {end_date}")
        
    storage = Storage(output)
    all_events: List[Event] = []
    
    # Initialize Sources
    sources = []
    for config in EVENTOR_CONFIGS:
        sources.append(EventorSource(config["country"], config["url"]))
    
    # Fetch Events
    for source in sources:
        try:
            # 1. Fetch List
            events = source.fetch_event_list(start_date, end_date)
            
            # 2. Fetch Details
            for event in events:
                detailed_event = source.fetch_event_details(event)
                if detailed_event:
                    all_events.append(detailed_event)
                else:
                    # If detail fetch failed, maybe keep basic info? 
                    # Original logic skipped it, so we skip it too.
                    pass
                    
        except Exception as e:
            logger.error(f"Error processing source {source.country}: {e}")
            continue
                
    storage.save(all_events)
    logger.info("Scraping completed.")

if __name__ == '__main__':
    main()
