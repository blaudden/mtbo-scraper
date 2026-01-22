import datetime
from typing import Any


def calculate_stats(
    old_events: list[dict[str, Any]], new_events: list[dict[str, Any]]
) -> str:
    """Calculates statistics between two lists of events.

    Args:
        old_events: List of event dicts from the previous run.
        new_events: List of event dicts from the current run.

    Returns:
        A formated commit message string summarizing the changes.
    """
    old_map = {e["id"]: e for e in old_events}
    new_map = {e["id"]: e for e in new_events}

    new_ids = set(new_map.keys()) - set(old_map.keys())
    deleted_ids = set(old_map.keys()) - set(new_map.keys())
    common_ids = set(old_map.keys()) & set(new_map.keys())

    changed_count = 0
    for eid in common_ids:
        # Simple equality check might fail if order of keys differs
        # or types match loosely. But for JSON-loaded dicts,
        # equality operator works well.
        if old_map[eid] != new_map[eid]:
            changed_count += 1

    today = datetime.date.today().isoformat()
    msg = f"Update MTBO events: {today}\n"
    msg += f"New: {len(new_ids)}, Changed: {changed_count}, Deleted: {len(deleted_ids)}"
    return msg
