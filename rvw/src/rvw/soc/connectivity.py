"""Read project-owned connection tables without executing expressions."""
import csv
import io
import json
from pathlib import Path
import tomllib


def load(path, *, format_path=None):
    path = Path(path)
    suffix = Path(format_path or path).suffix.lower()
    text = path.read_text()
    if suffix == '.csv':
        rows = list(csv.DictReader(io.StringIO(text)))
    else:
        plan = json.loads(text) if suffix == '.json' else tomllib.loads(text)
        if not isinstance(plan, dict) or set(plan) != {'connection'}:
            raise ValueError('manifest supports only connection declarations')
        rows = plan['connection']
    if not isinstance(rows, list) or not rows or not all(isinstance(r, dict) for r in rows):
        raise ValueError('manifest needs connection rows')
    normalized = []
    for i, original in enumerate(rows):
        row = {k: v for k, v in original.items() if v != ''}
        for alias, target in [('condition', 'enable'), ('delay', 'latency')]:
            if alias in row:
                if target in row:
                    raise ValueError(f'use either {alias} or {target}')
                row[target] = row.pop(alias)
        row.setdefault('id', f'connection-{i + 1}')
        row.setdefault('kind', 'required')
        if suffix == '.csv':
            if 'latency' in row:
                row['latency'] = int(row['latency'])
            if 'inversion' in row:
                if row['inversion'].lower() not in ('true', 'false', '0', '1'):
                    raise ValueError('inversion must be Boolean')
                row['inversion'] = row['inversion'].lower() in ('true', '1')
        normalized.append(row)
    ids = [r['id'] for r in normalized]
    if any(not isinstance(i, str) or not i for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('connection IDs must be nonempty and unique')
    return normalized
