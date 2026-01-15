import datetime

def calculate_stats(old_events: list, new_events: list) -> str:
    """
    Calculates statistics between two lists of event dictionaries (or objects containing 'id').
    Returns a formatted commit message string.
    """
    # Normalize inputs to dictionaries if they are objects (assuming .to_dict() or attribute access if needed)
    # But based on storage.py, load() returns dicts. 
    # Let's assume input is list of dicts for simplicity as per storage.py implementation.
    
    old_map = {e['id']: e for e in old_events}
    new_map = {e['id']: e for e in new_events}
    
    new_ids = set(new_map.keys()) - set(old_map.keys())
    deleted_ids = set(old_map.keys()) - set(new_map.keys())
    common_ids = set(old_map.keys()) & set(new_map.keys())
    
    changed_count = 0
    for eid in common_ids:
        # Simple equality check might fail if order of keys differs or types match loosely.
        # But for JSON-loaded dicts, equality operator works well.
        if old_map[eid] != new_map[eid]:
            changed_count += 1
            
    today = datetime.date.today().isoformat()
    msg = f"Update MTBO events: {today}\n"
    msg += f"New: {len(new_ids)}, Changed: {changed_count}, Deleted: {len(deleted_ids)}"
    return msg
