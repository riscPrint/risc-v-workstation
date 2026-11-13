"""Searchable immutable-report references. An index is not a verification verdict."""
import hashlib
import json
import sqlite3
from pathlib import Path
from rvw.results import validate_run, validate_results, validate_verdict

PREFIXES = ('rvw.run/', 'rvw.results/', 'rvw.verdict/', 'rvw.bundle/', 'rvw.formal', 'rvw.coverage', 'rvw.lint/')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(root, db):
    root = Path(root).resolve()
    records, errors = [], []
    for path in sorted(root.rglob('*.json')):
        try:
            raw = path.read_bytes()
            data = json.loads(raw)
            schema = data.get('schema', '') if isinstance(data, dict) else ''
            if not schema.startswith(PREFIXES):
                continue
            validator = next((v for prefix, v in [('rvw.run/', validate_run), ('rvw.results/', validate_results), ('rvw.verdict/', validate_verdict)] if schema.startswith(prefix)), None)
            problems = validator(data) if validator else []
            records.append((str(path), hashlib.sha256(raw).hexdigest(), schema, json.dumps(data), json.dumps(problems)))
        except (ValueError, OSError) as exc:
            errors.append(dict(path=str(path), error=str(exc)))
    with sqlite3.connect(db) as connection:
        connection.execute('CREATE TABLE IF NOT EXISTS evidence(path TEXT PRIMARY KEY, sha TEXT, schema TEXT, data TEXT, errors TEXT)')
        connection.executemany('INSERT OR REPLACE INTO evidence VALUES (?,?,?,?,?)', records)
    return dict(indexed=len(records), errors=errors, status='indexed' if records else 'no_checks')


def query(db, text='', schema=None):
    connection = sqlite3.connect(Path(db).resolve().as_uri() + '?mode=ro', uri=True)
    try:
        rows = connection.execute('SELECT * FROM evidence WHERE data LIKE ? AND schema LIKE ?', ('%' + text + '%', (schema + '%') if schema else '%')).fetchall()
    finally:
        connection.close()
    results = []
    for path, digest, kind, raw, errors in rows:
        data = json.loads(raw)
        invalid = json.loads(errors)
        try:
            if sha(path) != digest:
                invalid.append('report changed since indexing')
        except OSError:
            invalid.append('report missing')
        dependencies = []
        # Explicit joins can refer to any tool output. Missing identity weakens the claim.
        for item in data.get('evidence_dependencies', []):
            target = Path(item['path'])
            if not target.is_absolute():
                target = Path(path).parent / target
            current = None
            try:
                current = sha(target)
            except OSError:
                pass
            valid = current is not None and current == item.get('sha256')
            dependencies.append(dict(path=str(target), expected_sha256=item.get('sha256'), actual_sha256=current, valid=valid))
            if not valid:
                invalid.append('missing or changed dependency: ' + str(target))
        results.append(dict(path=path, sha256=digest, schema=kind, recorded_status=data.get('verdict', data.get('status', 'not_recorded')),
            integrity='inconclusive' if invalid else 'unchanged', issues=invalid, dependencies=dependencies,
            observations=data, assumptions=data.get('assumptions'), configuration=data.get('config'),
            validation='schema' if kind.startswith(('rvw.run/', 'rvw.results/', 'rvw.verdict/')) else 'json_only'))
    return dict(schema='rvw.evidence-query/1', matches=results, status='reported' if results else 'no_checks', verdict='not_inferred')
