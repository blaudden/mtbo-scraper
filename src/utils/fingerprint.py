import hashlib
from typing import TypedDict


class Participant(TypedDict):
    name: str
    club: str
    class_name: str
    start_number: str | None


class Fingerprinter:
    """Handles participant participant merging and fingerprint generation."""

    @staticmethod
    def _normalize(text: str) -> str:
        return text.strip().lower()

    @staticmethod
    def generate_fingerprint_for_participant(p: Participant) -> str:
        """Generates a SHA256 fingerprint for a single participant."""
        norm_name = Fingerprinter._normalize(p["name"])
        norm_club = Fingerprinter._normalize(p["club"])
        raw = f"{norm_name}|{norm_club}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def merge_participants(lists: list[list[dict]]) -> list[dict]:
        """Merges multiple lists of participants, removing duplicates based on
        Name+Club.

        Args:
            lists: A list of participant lists (each being a list of dicts/Participant).

        Returns:
            A single merged list of unique participants.
        """
        seen = set()
        merged = []

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
    def generate_fingerprints(participants: list[dict]) -> list[str]:
        """Generates a sorted list of unique fingerprints from a list of participants.

        Args:
            participants: A list of participant dictionaries.

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
            fp = Fingerprinter.generate_fingerprint_for_participant(input_p)
            fingerprints.add(fp)

        return sorted(fingerprints)
