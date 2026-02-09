import hashlib
from typing import Any, TypedDict

from ..models import EventDict


class Participant(TypedDict):
    name: str
    club: str
    class_name: str
    start_number: str | int | None


class Fingerprinter:
    """Handles participant participant merging and fingerprint generation."""

    @staticmethod
    def _normalize(text: str) -> str:
        return text.strip().lower()

    @staticmethod
    def generate_fingerprint_for_participant(
        p: Participant, known_hashes: set[str] | None = None
    ) -> str:
        """Generates a SHA256 fingerprint for a single participant.

        If known_hashes is provided, it checks if a reversed version of the name
        matches an existing hash to handle "Last First" vs "First Last" issues.
        """
        norm_name = Fingerprinter._normalize(p["name"])
        norm_club = Fingerprinter._normalize(p["club"])

        def _get_hash(name: str) -> str:
            raw = f"{name}|{norm_club}"
            return hashlib.sha256(raw.encode("utf-8")).hexdigest()

        h1 = _get_hash(norm_name)

        if known_hashes and h1 not in known_hashes:
            # Check if reversed name matches a known hash
            words = norm_name.split()
            if len(words) > 1:
                reversed_name = " ".join(reversed(words))
                if reversed_name != norm_name:
                    h2 = _get_hash(reversed_name)
                    if h2 in known_hashes:
                        return h2

        return h1

    @staticmethod
    def merge_participants(lists: list[list[Participant]]) -> list[Participant]:
        """Merges multiple lists of participants, removing duplicates based on
        Name+Club.

        Args:
            lists: A list of participant lists (each being a list of Participants).

        Returns:
            A single merged list of unique participants.
        """
        seen: set[tuple[str, str]] = set()
        merged: list[Participant] = []

        for participant_list in lists:
            for p in participant_list:
                # Use normalized name+club as key for uniqueness
                key = (
                    Fingerprinter._normalize(p.get("name", "")),
                    Fingerprinter._normalize(p.get("club", "")),
                )

                if key not in seen:
                    seen.add(key)
                    merged.append(p)

        return merged

    @staticmethod
    def generate_fingerprints(
        participants: list[dict[str, Any]], known_hashes: set[str] | None = None
    ) -> list[str]:
        """Generates a sorted list of unique fingerprints from a list of participants.

        Args:
            participants: A list of participant dictionaries.
            known_hashes: Optional set of existing fingerprints for the current
                year/context.

        Returns:
            A sorted list of unique hash strings.
        """
        fingerprints = set()
        for p in participants:
            input_p: Participant = {
                "name": p.get("name", ""),
                "club": p.get("club", ""),
                "class_name": p.get("class_name", ""),
                "start_number": p.get("start_number", None),
            }
            fp = Fingerprinter.generate_fingerprint_for_participant(
                input_p, known_hashes
            )
            fingerprints.add(fp)

        return sorted(fingerprints)

    @staticmethod
    def extract_year_to_fingerprints(events: list[EventDict]) -> dict[str, set[str]]:
        """Extracts existing fingerprints from a list of events, grouped by year.

        Args:
            events: A list of event dictionaries.

        Returns:
            A dictionary mapping year (str) to a set of fingerprint hashes.
        """
        year_to_fps: dict[str, set[str]] = {}
        for ev in events:
            # Extract year from start_time (ISO format)
            start_time = ev.get("start_time", "")
            year = start_time[:4] if len(start_time) >= 4 else None

            if year:
                if year not in year_to_fps:
                    year_to_fps[year] = set()
                for race in ev.get("races", []):
                    for fp in race.get("fingerprints", []):
                        year_to_fps[year].add(fp)
        return year_to_fps
