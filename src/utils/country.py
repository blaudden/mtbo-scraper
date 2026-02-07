import logging
from functools import lru_cache

import pycountry

logger = logging.getLogger(__name__)


@lru_cache(maxsize=128)
def get_iso_country_code(name: str) -> str | None:
    """
    Resolve a country name to its 3-letter ISO code (Alpha-3).

    Args:
        name: The country name string (e.g. "Italy", "Sweden").

    Returns:
        ISO 3-letter code (e.g. "ITA", "SWE") or None if not found.
    """
    if not name:
        return None

    try:
        # First try exact match or common name match
        search_result = pycountry.countries.search_fuzzy(name)
        if search_result:
            # mypy: pycountry types are dynamic
            return str(getattr(search_result[0], "alpha_3", None))
    except LookupError:
        pass
    except Exception as e:
        logger.warning(f"Error resolving country code for '{name}': {e}")

    return None
