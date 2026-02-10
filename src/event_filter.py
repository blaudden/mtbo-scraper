"""Event filtering and anomaly detection for MTBO events.

Provides:
- ``is_excluded`` / ``SKIP_LIST`` — hardcoded non-events to drop entirely.
- ``has_mtbo_signal`` / ``detect_anomaly`` — keyword + tag analysis.
- ``OringenFilter`` — two-step class that filters O-Ringen umbrella
  events so that only MTBO classes, counts and fingerprints are kept.

Custom tags added by this module
--------------------------------
``CLASSES_FILTERED``
    The event's class list was reduced to only MTBO classes. Counts
    and fingerprints reflect only the MTBO portion of the event.

``EVENT_SKIP``
    An O-Ringen umbrella event where no MTBO classes were found.
    Counts and fingerprints are zeroed out.
"""

import re

from src.models import Event

# Events that are purely uninteresting and excluded from the scrape.
SKIP_LIST: frozenset[str] = frozenset(
    {
        "SWE_55298",  # Val till SOFTs Ungdomsråd (election, not an event)
    }
)

# Keywords that indicate an MTBO event (checked case-insensitively).
# "mtb" alone is excluded to avoid false positives with pure MTB events.
MTBO_KEYWORDS: list[str] = ["mtbo", "mtb-o", "mtb o", "mtb-orientering"]

# Tags added by the filter
TAG_CLASSES_FILTERED = "CLASSES_FILTERED"
TAG_EVENT_SKIP = "EVENT_SKIP"


def is_excluded(event: Event) -> bool:
    """Check if an event should be excluded from the scrape.

    Args:
        event: The event to check.

    Returns:
        True if the event is in the skip list.
    """
    return event.id in SKIP_LIST


def has_mtbo_signal(event: Event) -> bool:
    """Check if an event has MTBO keywords in name or classes.

    Args:
        event: The event to check.

    Returns:
        True if any MTBO keyword is found in name or classes.
    """
    name_lower = event.name.lower()
    if any(kw in name_lower for kw in MTBO_KEYWORDS):
        return True

    classes_lower = " ".join(c.lower() for c in event.classes)
    return any(kw in classes_lower for kw in MTBO_KEYWORDS)


def detect_anomaly(event: Event) -> str | None:
    """Detect if an event has non-MTBO tags without MTBO signal.

    Args:
        event: The event to check.

    Returns:
        "suspect-no-signal" if anomalous, None otherwise.
    """
    if not event.tags:
        return None
    if has_mtbo_signal(event):
        return None
    return "suspect-no-signal"


def _is_mtbo_class(class_name: str) -> bool:
    """Check if a class name contains an MTBO keyword."""
    lower = class_name.lower()
    return any(kw in lower for kw in MTBO_KEYWORDS)


def _filter_counts(
    counts: dict[str, int] | None, allowed: set[str]
) -> dict[str, int] | None:
    """Keep only keys present in *allowed*; pass through None."""
    if not counts:
        return counts
    return {k: v for k, v in counts.items() if k in allowed}


class OringenFilter:
    """Two-step filter for O-Ringen umbrella events.

    Detects O-Ringen umbrella events (name contains "O-Ringen" and has
    non-empty discipline tags) and filters them to only MTBO content.

    Usage in the scraping pipeline::

        of = OringenFilter(event)
        of.filter_classes()                    # Step 1: before counts/fingerprints
        source.fetch_and_process_lists(event)  # populates counts + fingerprints
        of.finalize()                          # Step 2: filter counts, add tags
    """

    def __init__(self, event: Event) -> None:
        self._event = event
        self._is_umbrella = self._detect_umbrella()
        self._mtbo_class_set: set[str] = set()

    def _detect_umbrella(self) -> bool:
        """Check if the event is an O-Ringen umbrella."""
        if not re.search(r"o-ringen|oringen", self._event.name, re.IGNORECASE):
            return False
        return bool(self._event.tags)

    @property
    def is_umbrella(self) -> bool:
        """Whether this event is an O-Ringen umbrella."""
        return self._is_umbrella

    @property
    def allowed_classes(self) -> set[str] | None:
        """The set of allowed MTBO classes, or None if no filtering needed.

        Returns None for non-umbrella events (all classes allowed).
        Returns the MTBO class set for umbrella events (may be empty).
        """
        if not self._is_umbrella:
            return None
        return self._mtbo_class_set

    def filter_classes(self) -> None:
        """Step 1: Filter event.classes to only MTBO classes.

        Must be called before counts and fingerprints are computed so
        that the fingerprinting step can use ``event.classes`` to decide
        which participants to include.

        No-op for non-umbrella events.
        """
        if not self._is_umbrella:
            return

        self._mtbo_class_set = {c for c in self._event.classes if _is_mtbo_class(c)}
        self._event.classes = [
            c for c in self._event.classes if c in self._mtbo_class_set
        ]

    def finalize(self) -> None:
        """Step 2: Filter counts and add tags.

        Must be called after counts and fingerprints are populated.
        Filters counts to only MTBO class keys and adds the appropriate
        tag (``CLASSES_FILTERED`` or ``EVENT_SKIP``).

        No-op for non-umbrella events.
        """
        if not self._is_umbrella:
            return

        if not self._mtbo_class_set:
            # No MTBO classes — tag as EVENT_SKIP
            if TAG_EVENT_SKIP not in self._event.tags:
                self._event.tags.append(TAG_EVENT_SKIP)
            for race in self._event.races:
                race.entry_counts = None
                race.start_counts = None
                race.result_counts = None
                race.fingerprints = []
            return

        # MTBO classes exist — filter counts and tag
        if TAG_CLASSES_FILTERED not in self._event.tags:
            self._event.tags.append(TAG_CLASSES_FILTERED)

        for race in self._event.races:
            race.entry_counts = _filter_counts(race.entry_counts, self._mtbo_class_set)
            race.start_counts = _filter_counts(race.start_counts, self._mtbo_class_set)
            race.result_counts = _filter_counts(
                race.result_counts, self._mtbo_class_set
            )
