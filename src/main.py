import logging
import random
import resource
import sys
import time
from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Literal, TypedDict

import click
import structlog

from src.event_filter import is_excluded
from src.html_cache import HtmlCache
from src.models import Event, EventDict
from src.scraper import Scraper
from src.sources.eventor_source import EventorSource
from src.sources.manual_source import ManualSource

# Use absolute imports for script execution
from src.storage import Storage
from src.utils.diff import calculate_stats
from src.utils.fingerprint import Fingerprinter

# Setup logging (will be configured in main() based on CLI flags)
logger = structlog.get_logger(__name__)


class SourceConfig(TypedDict):
    country: str
    url: str | None
    type: Literal["eventor", "manual"]


# Configuration
SOURCE_CONFIGS: list[SourceConfig] = [
    {"country": "SWE", "url": "https://eventor.orientering.se", "type": "eventor"},
    {"country": "NOR", "url": "https://eventor.orientering.no", "type": "eventor"},
    {"country": "IOF", "url": "https://eventor.orienteering.sport", "type": "eventor"},
    {"country": "MAN", "url": None, "type": "manual"},
]
MANUAL_EVENTS_DIR = "manual_events"


def irregular_chunk_date_range(
    start_date: str, end_date: str
) -> Iterator[tuple[str, str]]:
    """Yields date ranges (start, end) in irregular chunks.

    Chunk size is random between 1 day and 150 days (approx 5 months).

    Args:
        start_date: Start date string (YYYY-MM-DD).
        end_date: End date string (YYYY-MM-DD).

    Yields:
        Tuple of (chunk_start_date, chunk_end_date).
    """
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    current = start
    while current <= end:
        # Random duration between 1 day and 150 days
        days = random.randint(0, 150)
        chunk_end = current + timedelta(days=days)

        # Determine actual end for this chunk
        if chunk_end > end:
            chunk_end = end

        yield current.strftime("%Y-%m-%d"), chunk_end.strftime("%Y-%m-%d")

        # Move start to next day after current chunk
        current = chunk_end + timedelta(days=1)


def split_range_by_year(start_date: str, end_date: str) -> Iterator[tuple[str, str]]:
    """Yields date ranges (start, end) split by year boundaries.

    Each segment is at most one calendar year long, ending on Dec 31st
    or the overall end_date.

    Args:
        start_date: Start date string (YYYY-MM-DD).
        end_date: End date string (YYYY-MM-DD).

    Yields:
        Tuple of (segment_start_date, segment_end_date).
    """
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    current = start
    while current <= end:
        # End of current year
        year_end = datetime(current.year, 12, 31)

        # Segment end is either end of year or overall end date
        segment_end = min(year_end, end)

        yield current.strftime("%Y-%m-%d"), segment_end.strftime("%Y-%m-%d")

        # Prepare for next iteration
        current = segment_end + timedelta(days=1)


def _get_local_events(
    events_dict: dict[str, EventDict],
    country: str,
    start_date: str,
    end_date: str,
) -> list[Event]:
    """Filter locally stored events by country and date range.

    Used in history mode to avoid fetching event listings from Eventor.
    Events are matched by country prefix and start_time within the range.

    Args:
        events_dict: All known events keyed by ID.
        country: Country code to filter by (e.g. "SWE").
        start_date: Inclusive start date (YYYY-MM-DD).
        end_date: Inclusive end date (YYYY-MM-DD).

    Returns:
        List of Event objects matching the criteria.
    """
    prefix = f"{country}_"
    matched: list[Event] = []
    for event_id, event_data in events_dict.items():
        if not event_id.startswith(prefix):
            continue
        event_start = event_data.get("start_time", "")
        if start_date <= event_start <= end_date:
            event = Event.from_dict(event_data)
            # Reconstruct the detail URL from the numeric ID
            numeric_id = event_id.split("_", 1)[1]
            event.url = f"/Events/Show/{numeric_id}"
            matched.append(event)
    return matched


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
@click.option("--start-date", help="Start date (YYYY-MM-%d)")
@click.option("--end-date", help="End date (YYYY-MM-%d)")
@click.option(
    "--output", "-o", default="data/events/mtbo_events.json", help="Output file path"
)
@click.option(
    "--refresh", is_flag=True, help="Force refresh of startlists for qualifying events"
)
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
    "source_filter",
    multiple=True,
    help="Specific source(s) to scrape (e.g., SWE, NOR, IOF, MAN). "
    "Can be used multiple times or as a comma-separated list.",
)
@click.option(
    "--shuffle/--no-shuffle",
    default=True,
    help="Shuffle chunks and events (default: True)",
)
@click.option(
    "--event-id",
    "event_ids",
    multiple=True,
    help="Fetch specific event(s) by ID (e.g. SWE_5115). Can be repeated.",
)
@click.option(
    "--purge-event-id",
    "purge_ids",
    multiple=True,
    help="Remove event(s) by ID from data and exit. Can be repeated.",
)
@click.option(
    "--fetch-listing/--no-fetch-listing",
    "fetch_listing",
    default=None,
    help="Force fetch/skip event listings from Eventor. "
    "Default: auto (skip in history mode).",
)
def main(
    start_date: str | None,
    end_date: str | None,
    output: str,
    refresh: bool,
    commit_msg_file: str | None,
    verbose: int,
    json_logs: bool,
    mode: str,
    source_filter: tuple[str, ...],
    shuffle: bool,
    event_ids: tuple[str, ...],
    purge_ids: tuple[str, ...],
    fetch_listing: bool | None,
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
        # Disable colors if not a TTY (e.g. redirected to a file)
        colors = sys.stdout.isatty()
        processors.append(structlog.dev.ConsoleRenderer(colors=colors, sort_keys=False))

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

    # Check resource limits (ulimit -n)
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        if soft < 1024:
            logger.warning(
                "low_open_file_limit",
                suggestion=(
                    "Run 'ulimit -n 1024' or higher to avoid "
                    "'Too many open files' errors."
                ),
            )
        else:
            logger.debug(
                "resource_limits_check_passed", soft_limit=soft, hard_limit=hard
            )
    except Exception as e:
        logger.warning("resource_limit_check_failed", error=str(e))

    # Validate source if provided
    active_configs = SOURCE_CONFIGS
    if source_filter:
        # source_filter is a tuple due to multiple=True.
        # Flatten any comma-separated strings inside the tuple.
        requested_sources: list[str] = []
        for s in source_filter:
            requested_sources.extend([part.strip().upper() for part in s.split(",")])

        active_configs = [
            c for c in SOURCE_CONFIGS if c["country"] in requested_sources
        ]

        # Verify all requested sources were found
        found_sources = {c["country"] for c in active_configs}
        missing_sources = [s for s in requested_sources if s not in found_sources]

        if missing_sources:
            valid_sources = ", ".join([c["country"] for c in SOURCE_CONFIGS])
            logger.error(
                "invalid_source",
                provided=source_filter,
                missing=missing_sources,
                valid_sources=valid_sources,
            )
            sys.exit(1)

    start_date, end_date = determine_date_range(start_date, end_date, mode)

    logger.info("date_range_determined", start_date=start_date, end_date=end_date)

    storage = Storage(output)

    # Handle purge-event-id: remove events and exit
    if purge_ids:
        removed = storage.purge(list(purge_ids))
        if removed:
            logger.info("purge_completed", removed=removed)
        else:
            logger.warning("purge_no_events_found", requested=list(purge_ids))
        return
    # Load old events to calculate diff later
    old_events_dict = storage.load()
    old_events = list(old_events_dict.values())

    year_to_fps = Fingerprinter.extract_year_to_fingerprints(old_events)

    # Determine delay range based on start date threshold (4 weeks ago)
    # If start_date is older than 4 weeks ago, assume History Mode (slower)
    start_dt = datetime.strptime(start_date, "%Y-%m-%d")
    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
    threshold_date = (datetime.now() - timedelta(weeks=4)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    # Restriction: prevent mixed history/current mode scrapes
    if start_dt.date() < threshold_date.date() <= end_dt.date():
        logger.error(
            "mixed_mode_scrape_prevented",
            start_date=start_date,
            end_date=end_date,
            threshold=threshold_date.strftime("%Y-%m-%d"),
            reason="Scrapes crossing the 4-week history threshold are not allowed. "
            "Please split into two runs: one for historical data (<4 weeks old) "
            "and one for recent/future data.",
        )
        sys.exit(1)

    if start_dt.date() < threshold_date.date():
        delay_range = (0.5, 1.5)
        html_cache: HtmlCache | None = HtmlCache()
        use_local_listing = fetch_listing is not True
        logger.info(
            "history_mode_detected",
            delay="0.5-1.5s",
            cache_enabled=True,
            local_listing=use_local_listing,
            reason="start_date_older_than_4_weeks",
            start_date=start_date,
            threshold=threshold_date.strftime("%Y-%m-%d"),
        )
    else:
        delay_range = (1.0, 3.0)
        html_cache = None
        use_local_listing = fetch_listing is False
        logger.info(
            "standard_mode_detected",
            delay="1-3s",
            local_listing=use_local_listing,
            start_date=start_date,
        )

    # Initialize Scraper
    scraper = Scraper(
        delay_range=delay_range,
        html_cache=html_cache,
    )

    # Initialize Sources
    eventor_sources: list[EventorSource] = []
    run_manual = False

    for config in active_configs:
        if config["type"] == "eventor":
            assert config["url"] is not None
            eventor_sources.append(
                EventorSource(
                    config["country"],
                    config["url"],
                    known_fingerprints=year_to_fps,
                    refresh=refresh,
                    scraper=scraper,
                )
            )
        elif config["type"] == "manual":
            run_manual = True

    # Track failures for final report
    failed_event_ids: list[str] = []

    # 1. Load Manual Events
    if run_manual:
        manual_source = ManualSource(MANUAL_EVENTS_DIR)
        manual_events = manual_source.load_events()
        # Save manual events immediately
        new_events = storage.save({"MAN": manual_events})
        logger.debug(
            "manual_events_loaded_and_saved",
            count=len(manual_events),
            source_dir=MANUAL_EVENTS_DIR,
        )
    else:
        new_events = list(storage.load().values())

    # 2. Fetch specific events by ID (skip date-range listing)
    current_pass_events: dict[str, list[Event]] = {}

    if event_ids and eventor_sources:
        # Load existing events from disk to use as stubs
        existing_map = storage.load()

        # Map country code to source
        source_by_country = {s.country: s for s in eventor_sources}

        for eid in event_ids:
            parts = eid.split("_", 1)
            if len(parts) != 2:
                logger.error("invalid_event_id", event_id=eid)
                continue
            country, numeric_id = parts
            source = source_by_country.get(country)
            if not source:
                logger.error(
                    "no_source_for_event_id",
                    event_id=eid,
                    country=country,
                )
                continue

            if country not in current_pass_events:
                current_pass_events[country] = []

            # Require existing event from disk (rescrape only)
            existing = existing_map.get(eid)
            if not existing:
                logger.warning(
                    "event_not_found_locally",
                    event_id=eid,
                    message="Use --event-id only for rescraping existing events.",
                )
                continue

            stub = Event.from_dict(existing)
            stub.url = stub.url or f"/Events/Show/{numeric_id}"
            logger.info(
                "fetching_event_by_id",
                event_id=eid,
                from_disk=True,
            )
            detailed = source.fetch_event_details(stub)
            if detailed:
                if is_excluded(detailed):
                    logger.info(
                        "event_excluded",
                        event_id=detailed.id,
                        name=detailed.name,
                    )
                    continue
                current_pass_events[country].append(detailed)
            else:
                failed_event_ids.append(eid)

        if current_pass_events:
            new_events = storage.save(current_pass_events)
            logger.info(
                "event_id_fetch_completed",
                fetched=sum(len(v) for v in current_pass_events.values()),
                failed=len(failed_event_ids),
            )

    # 3. Process Eventor Sources by date range (normal mode)
    elif eventor_sources:
        # Split the total range into year segments
        year_segments = list(split_range_by_year(start_date, end_date))
        total_segments = len(year_segments)

        for seg_idx, (segment_start, segment_end) in enumerate(year_segments):
            segment_year_str = segment_start[:4]

            # Generate chunks for this segment
            chunks = list(irregular_chunk_date_range(segment_start, segment_end))
            if shuffle:
                random.shuffle(chunks)

            # Accumulator for this segment/year
            current_pass_events = {}

            total_chunks = len(chunks)
            for i, (chunk_start, chunk_end) in enumerate(chunks):
                logger.info(
                    "processing_chunk",
                    year=segment_year_str,
                    chunk_index=i + 1,
                    total_chunks=total_chunks,
                    chunk=f"{chunk_start} to {chunk_end}",
                    segment_progress=f"{seg_idx + 1}/{total_segments}",
                )

                for source in eventor_sources:
                    if source.country not in current_pass_events:
                        current_pass_events[source.country] = []

                    try:
                        # 1. Fetch List for this chunk
                        if use_local_listing:
                            # Use local events as list for this chunk
                            events = _get_local_events(
                                old_events_dict,
                                source.country,
                                chunk_start,
                                chunk_end,
                            )
                            logger.info(
                                "local_listing_used",
                                country=source.country,
                                count=len(events),
                                chunk=f"{chunk_start} to {chunk_end}",
                            )
                        else:
                            # Fetch events from Eventor
                            events = source.fetch_event_list(chunk_start, chunk_end)
                        total_events = len(events)

                        if total_events == 0:
                            continue

                        # 2. Fetch Details
                        # Shuffle events to process detailed pages in random order
                        if shuffle:
                            random.shuffle(events)

                        for idx, event in enumerate(events):
                            # Log progress
                            if (
                                idx == 0
                                or (idx + 1) % 5 == 0
                                or (idx + 1) == total_events
                            ):
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
                                if is_excluded(detailed_event):
                                    logger.info(
                                        "event_excluded",
                                        event_id=detailed_event.id,
                                        name=detailed_event.name,
                                    )
                                    continue
                                current_pass_events[source.country].append(
                                    detailed_event
                                )
                            else:
                                failed_event_ids.append(event.id)

                    except Exception as e:
                        logger.error(
                            "source_processing_failed",
                            country=source.country,
                            chunk=f"{chunk_start}-{chunk_end}",
                            error=str(e),
                        )
                        continue

                # Sleep between chunks, unless using local listing
                if i < len(chunks) - 1 and not use_local_listing:
                    sleep_sec = 0.5
                    logger.info("sleeping_between_chunks", seconds=sleep_sec)
                    time.sleep(sleep_sec)

            # PERIODIC SAVE: after each year/segment
            if current_pass_events:
                # We update 'new_events' so that if this is the last loop,
                # we have the final state for stats calculation.
                intermediate_saved_events = storage.save(current_pass_events)
                new_events = intermediate_saved_events
                logger.info("year_segment_completed_and_saved", year=segment_year_str)
            else:
                logger.info("year_segment_completed_no_events", year=segment_year_str)

        logger.info("scraping_completed")

        if failed_event_ids:
            logger.warning(
                "scraping_failures_summary",
                count=len(failed_event_ids),
                failed_ids=failed_event_ids[:50],
                more_hidden=len(failed_event_ids) > 50,
            )

    # Calculate stats and write commit message
    sources_used = [c["country"] for c in active_configs] if source_filter else None
    stats_msg = calculate_stats(
        old_events,
        new_events,
        start_date=start_date,
        end_date=end_date,
        sources=sources_used,
        refresh=refresh,
    )
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
