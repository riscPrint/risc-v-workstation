"""Review metadata shared by generated checks and lint settings version 2."""
from datetime import date, datetime, timezone


def validate_review(entry, today=None):
    if not isinstance(entry, dict):
        raise ValueError('waiver/disposition must be an object')
    for key in ('reason', 'owner', 'expires'):
        if not isinstance(entry.get(key), str) or not entry[key].strip():
            raise ValueError(f'waiver/disposition needs {key}')
    try:
        expiry = date.fromisoformat(entry['expires'])
    except ValueError as exc:
        raise ValueError('waiver expires must be YYYY-MM-DD') from exc
    if expiry.isoformat() != entry['expires']:
        raise ValueError('waiver expires must be YYYY-MM-DD')
    today = today or datetime.now(timezone.utc).date()
    if expiry < today:
        raise ValueError(f"expired waiver/disposition: {entry['expires']} owner {entry['owner']}")


def stale_state(matches, evaluated):
    """Absence is stale only when the relevant observation actually ran."""
    return matches == 0 if evaluated else None
