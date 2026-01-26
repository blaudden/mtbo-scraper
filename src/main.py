import logging
import sys
import time
from collections.abc import Iterator
from datetime import datetime, timedelta

import click
import structlog

from src.models import Event
from src.sources.eventor_source import EventorSource
from src.sources.manual_source import ManualSource

# Use absolute imports for script execution
from src.storage import Storage
from src.utils.diff import calculate_stats

# Setup logging (will be configured in main() based on CLI flags)
logger = structlog.get_logger(__name__)

# Configuration
SOURCE_CONFIGS = [
    {"country": "SWE", "url": "https://eventor.orientering.se", "type": "eventor"},
    {"country": "NOR", "url": "https://eventor.orientering.no", "type": "eventor"},
    {"country": "IOF", "url": "https://eventor.orienteering.sport", "type": "eventor"},
    {"country": "MAN", "url": None, "type": "manual"},
]
MANUAL_EVENTS_DIR = "manual_events"


def chunk_date_range(
    start_date: str, end_date: str, chunk_months: int = 6
) -> Iterator[tuple[str, str]]:
    """Yields date ranges (start, end) in chunks.

    Args:
        start_date: Start date string (YYYY-MM-DD).
        end_date: End date string (YYYY-MM-DD).
        chunk_months: Number of months per chunk.

    Yields:
        Tuple of (chunk_start_date, chunk_end_date).
    """
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    current = start
    while current <= end:
        # Calculate chunk end (approx 6 months)
        chunk_end = current + timedelta(days=30 * chunk_months)

        # Determine actual end for this chunk
        # If chunk_end exceeds global end, cap it
        if chunk_end > end:
            actual_end = end
        else:
            actual_end = chunk_end

        yield current.strftime("%Y-%m-%d"), actual_end.strftime("%Y-%m-%d")

        # Move start to next day after current chunk
        current = actual_end + timedelta(days=1)


def determine_date_range(
    start_date: str | None, end_date: str | None, mode: str = "full"
) -> tuple[str, str]:
    """Determines the effective start and end dates.

    Args:
        start_date: Optional start date (YYYY-MM-DD)
        end_date: Optional end date (YYYY-MM-DD)
        mode: Scraping mode - 'full' or 'current'

    Returns:
        Tuple of (start_date, end_date)
    """
    if mode == "current":
        # Current mode: 1 week back, 2 weeks forward
        if not start_date:
            start_date = (datetime.now() - timedelta(weeks=1)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = (datetime.now() + timedelta(weeks=2)).strftime("%Y-%m-%d")
    else:
        # Full mode: default behavior
        if not start_date:
            # Default to 4 weeks ago
            start_date = (datetime.now() - timedelta(weeks=4)).strftime("%Y-%m-%d")

        # Default end date if not provided:
        # 1. Add ~6 months to start date
        # 2. Add 1 year to that year
        # 3. End on Dec 31st of that year
        if not end_date:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d")
            future_date = start_dt + timedelta(days=183)
            target_year = future_date.year + 1
            end_date = f"{target_year}-12-31"

    return start_date, end_date


@click.command()
@click.option("--start-date", help="Start date (YYYY-MM-DD)")
@click.option("--end-date", help="End date (YYYY-MM-DD)")
@click.option("--output", default="mtbo_events.json", help="Output JSON file")
@click.option("--commit-msg-file", default=None, help="File to write commit message to")
@click.option(
    "--verbose",
    "-v",
    count=True,
    default=1,
    help="Increase logging verbosity (can be used multiple times)",
)
@click.option(
    "--json-logs",
    is_flag=True,
    help="Output logs in JSON format for machine parsing",
)
@click.option(
    "--mode",
    type=click.Choice(["full", "current"], case_sensitive=False),
    default="full",
    help=(
        "Scraping mode: 'full' (default, entire range) or "
        "'current' (1 week back, 2 weeks forward)"
    ),
)
@click.option(
    "--source",
    help="Specific source to scrape (e.g., SWE, NOR, IOF, MAN)",
)
def main(
    start_date: str | None,
    end_date: str | None,
    output: str,
    commit_msg_file: str | None,
    verbose: int,
    json_logs: bool,
    mode: str,
    source: str | None,
) -> None:
    """MTBO Eventor Scraper"""
    # Configure logging based on verbosity
    if verbose == 0:
        log_level = logging.WARNING
    elif verbose == 1:
        log_level = logging.INFO
    else:
        log_level = logging.DEBUG

    # Configure structlog
    processors: list = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(
            fmt="iso" if json_logs else "%Y-%m-%d %H:%M:%S", utc=False
        ),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json_logs:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(sort_keys=False))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure standard logging for libraries
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )

    logger.info("scraper_starting", output_file=output)

    # Validate source if provided
    active_configs = SOURCE_CONFIGS
    if source:
        source_upper = source.upper()
        active_configs = [c for c in SOURCE_CONFIGS if c["country"] == source_upper]
        if not active_configs:
            valid_sources = ", ".join([c["country"] for c in SOURCE_CONFIGS])
            logger.error("invalid_source", provided=source, valid_sources=valid_sources)
            sys.exit(1)

    start_date, end_date = determine_date_range(start_date, end_date, mode)

    logger.info("date_range_determined", start_date=start_date, end_date=end_date)

    storage = Storage(output)
    # Load old events to calculate diff later
    old_events_dict = storage.load()
    old_events = list(old_events_dict.values())

    all_events_by_source: dict[str, list[Event]] = {}

    # Initialize Sources
    eventor_sources: list[EventorSource] = []
    run_manual = False

    for config in active_configs:
        if config["type"] == "eventor":
            eventor_sources.append(EventorSource(config["country"], config["url"]))
        elif config["type"] == "manual":
            run_manual = True

    # 1. Load Manual Events
    if run_manual:
        manual_source = ManualSource(MANUAL_EVENTS_DIR)
        manual_events = manual_source.load_events()
        all_events_by_source["MAN"] = manual_events
        logger.debug(
            "manual_events_loaded",
            count=len(manual_events),
            source_dir=MANUAL_EVENTS_DIR,
        )

    # 2. Process Eventor Sources in chunks
    if eventor_sources:
        chunk_size_months = 6
        chunks = list(chunk_date_range(start_date, end_date, chunk_size_months))

        for i, (chunk_start, chunk_end) in enumerate(chunks):
            logger.info(
                "processing_chunk",
                index=i + 1,
                total=len(chunks),
                start=chunk_start,
                end=chunk_end,
            )

            for source in eventor_sources:
                if source.country not in all_events_by_source:
                    all_events_by_source[source.country] = []

                try:
                    logger.info(
                        "scraping_source_start",
                        country=source.country,
                        chunk=f"{chunk_start}-{chunk_end}",
                    )

                    # 1. Fetch List for this chunk
                    events = source.fetch_event_list(chunk_start, chunk_end)
                    total_events = len(events)

                    # 2. Fetch Details
                    for idx, event in enumerate(events):
                        # Log progress every 5 events or for the first/last one
                        if idx == 0 or (idx + 1) % 5 == 0 or (idx + 1) == total_events:
                            percent = 0.0
                            if total_events > 0:
                                percent = round(((idx + 1) / total_events) * 100, 1)

                            logger.info(
                                "scraping_progress",
                                country=source.country,
                                current=idx + 1,
                                total=total_events,
                                percent=percent,
                            )

                        detailed_event = source.fetch_event_details(event)
                        if detailed_event:
                            all_events_by_source[source.country].append(detailed_event)
                except Exception as e:
                    logger.error(
                        "source_processing_failed",
                        country=source.country,
                        chunk=f"{chunk_start}-{chunk_end}",
                        error=str(e),
                    )
                    continue

            # Sleep between chunks if not the last one
            if i < len(chunks) - 1:
                sleep_sec = 5
                logger.info("sleeping_between_chunks", seconds=sleep_sec)
                time.sleep(sleep_sec)

    # Save returns the new list of events (merged)
    new_events = storage.save(all_events_by_source)
    logger.info("scraping_completed")

    # Calculate stats and write commit message
    stats_msg = calculate_stats(old_events, new_events)
    print(stats_msg)

    if commit_msg_file:
        try:
            with open(commit_msg_file, "w") as f:
                f.write(stats_msg)
            logger.info(f"Commit message written to {commit_msg_file}")
        except Exception as e:
            logger.error(f"Failed to write commit message: {e}")


if __name__ == "__main__":
    main()
