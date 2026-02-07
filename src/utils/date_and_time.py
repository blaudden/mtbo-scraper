import re
import zoneinfo
from datetime import datetime


def get_timezone_for_country(country_info: str) -> str:
    """Determines the timezone name for common countries.

    Args:
        country_info: The country code or name.

    Returns:
        The timezone name (e.g., 'Europe/Stockholm') or 'UTC' if unknown.
    """
    if not country_info:
        return "UTC"

    ci = country_info.strip().upper()

    mapping = {
        "SWE": "Europe/Stockholm",
        "NOR": "Europe/Oslo",
        "PRT": "Europe/Lisbon",
        "FIN": "Europe/Helsinki",
        "DNK": "Europe/Copenhagen",
        "EST": "Europe/Tallinn",
        "LTU": "Europe/Vilnius",
        "LVA": "Europe/Riga",
        "CZE": "Europe/Prague",
        "SVK": "Europe/Bratislava",
        "HUN": "Europe/Budapest",
        "AUT": "Europe/Vienna",
        "CHE": "Europe/Zurich",
        "POL": "Europe/Warsaw",
        "FRA": "Europe/Paris",
        "ESP": "Europe/Madrid",
        "ITA": "Europe/Rome",
        "GBR": "Europe/London",
    }

    return mapping.get(ci, "UTC")


def format_iso_datetime(
    date_str: str,
    time_str: str | None,
    country: str,
    offset: str | None = None,
) -> str:
    """Combines date and time into a full ISO 8601 string with timezone offset.

    Handles both YYYY-MM-DD and existing ISO 8601 strings.

    Args:
        date_str: The date string (YYYY-MM-DD or ISO).
        time_str: Optional time string (HH:MM:SS).
        country: The country code for timezone lookup.
        offset: Optional offset string (e.g., "+02:00").

    Returns:
        A complete ISO 8601 datetime string.
    """
    if not date_str:
        return ""

    try:
        # 1. Parse date and time first
        if "T" in date_str:
            # Be careful with dashes in YYYY-MM-DD
            # Better way to split ISO:
            iso_match = re.match(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})", date_str)
            if iso_match:
                dt = datetime.fromisoformat(iso_match.group(1))
            else:
                dt = datetime.fromisoformat(date_str.split("+")[0].split("Z")[0])

            if time_str:
                parts = time_str.split(":")
                h = int(parts[0])
                m = int(parts[1])
                s = int(parts[2]) if len(parts) > 2 else 0
                dt = dt.replace(hour=h, minute=m, second=s)
        else:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            if time_str:
                parts = time_str.split(":")
                h = int(parts[0])
                m = int(parts[1])
                s = int(parts[2]) if len(parts) > 2 else 0
                dt = dt.replace(hour=h, minute=m, second=s)

        # 2. Add timezone/offset
        if offset:
            # Handle UTC+2, UTC+02:00, or +02:00
            clean_offset = offset.replace("UTC", "").replace("local time", "").strip()
            # If it's just +2, make it +02:00
            if re.match(r"^[+-]\d{1,2}$", clean_offset):
                sign = clean_offset[0]
                val = int(clean_offset[1:])
                clean_offset = f"{sign}{val:02d}:00"
            elif re.match(r"^[+-]\d{1,2}:\d{2}$", clean_offset):
                sign = clean_offset[0]
                h_off, m_off = clean_offset[1:].split(":")
                clean_offset = f"{sign}{int(h_off):02d}:{m_off}"

            # Use fixed offset
            # We can use datetime.fromisoformat style or manual
            return f"{dt.strftime('%Y-%m-%dT%H:%M:%S')}{clean_offset}"

        # 3. Fallback to country-based lookup
        tz_name = get_timezone_for_country(country)
        tz = zoneinfo.ZoneInfo(tz_name)
        dt = dt.replace(tzinfo=tz)
        return dt.isoformat()

    except Exception as e:
        import logging

        logging.getLogger(__name__).debug(
            f"format_iso_datetime fallback for {date_str}: {e}"
        )
        return date_str


def parse_date_to_iso(date_str: str) -> str:
    """Parses various date formats to ISO format (YYYY-MM-DD).

    Args:
        date_str: The input date string.

    Returns:
        The date in YYYY-MM-DD format, or the original string if parsing fails.
    """
    if not date_str:
        return ""

    # Already in ISO format
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return date_str

    # Try various date formats
    formats = [
        "%A %d %B %Y",  # Monday 20 July 2026
        "%d %B %Y",  # 20 July 2026
        "%A, %d %B %Y",  # Monday, 20 July 2026
        "%d/%m/%Y",  # 20/07/2026
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    return date_str


def extract_time_from_date(date_str: str) -> tuple[str, str | None, str | None]:
    """Extracts time and UTC offset from a date string if present.

    Example: "26 August 2026 at 10:00 local time (UTC+2)"
        -> ("26 August 2026", "10:00", "+02:00")

    Args:
        date_str: The input date string containing potential time info.

    Returns:
        A tuple of (date_only_str, time_str, offset_str).
    """
    time = None
    offset = None

    # Pattern for time: "at HH:MM"
    time_match = re.search(r"at (\d{1,2}:\d{2})", date_str)
    if time_match:
        time = time_match.group(1)

    # Pattern for offset: "(UTC+X)" or "(UTC+XX:XX)"
    offset_match = re.search(r"\(UTC([+-]\d{1,2}(?::\d{2})?)\)", date_str)
    if offset_match:
        offset = offset_match.group(1)
        # Normalize offset to +HH:MM
        if ":" not in offset:
            sign = offset[0]
            val = int(offset[1:])
            offset = f"{sign}{val:02d}:00"
        else:
            sign = offset[0]
            h, m = offset[1:].split(":")
            offset = f"{sign}{int(h):02d}:{m}"

    # Clean up date string
    date_only = re.sub(r"\s*at\s+\d{1,2}:\d{2}.*$", "", date_str)
    date_only = re.sub(r"\(UTC[+-].*\)", "", date_only).strip()

    return (date_only, time, offset)
