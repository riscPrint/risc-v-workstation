"""Cross-navigation records from captured database artifacts."""
import gzip
import json

from .db import QueryError
from . import ops


def artifact(db, name):
    rows = db.q('SELECT encoding, content FROM artifacts WHERE name=?', (name,))
    if not rows:
        return None
    encoding, data = rows[0]
    if encoding not in ('identity', 'gzip'):
        raise QueryError(f'unsupported artifact encoding: {encoding}')
    return json.loads(gzip.decompress(data) if encoding == 'gzip' else data)


def navigation(db, signal):
    """Return source, diagram, wave and dependency entry points for one signal."""
    s = db.resolve_one(signal)
    comp = db.component(s.component_id)
    diagram = artifact(db, 'blocks.json')
    module = (diagram or {}).get('modules', {}).get(comp['module'], {})
    endpoints = []
    for port in module.get('ports', []):
        if port['name'] == s.name:
            endpoints.append({'kind': 'port', 'port': s.name})
    for node in module.get('nodes', []):
        if any(x['name'] == s.name for x in node.get('signals', [])):
            endpoints.append({'kind': 'node', 'id': node['id']})
    pdg = bool(db.q("SELECT 1 FROM artifacts WHERE name='pdg.json'"))
    where = ops.where(db, s.path)
    return {'schema': 'rvw.navigation/1', 'signal': s.path,
            'source': {'file': s.file, 'line': s.line, 'where': where},
            'block': {'instance': comp['path'], 'module': comp['module'], 'endpoints': endpoints,
                      'status': 'mapped' if endpoints else 'unmapped'},
            'wave': {'path': db.wave_path(s.path), 'status': 'pruned' if s.pruned else 'candidate'},
            'trace': {'signal': 'signal:' + s.path, 'top_module': db.top,
                      'extra_scopes': db.meta.get('extra_scopes', f'TOP {db.top}').split(),
                      'pdg_available': pdg, 'fallback': 'rvw wave why'},
            'database': db.capture.record(), 'warnings': db.staleness(),
            'accuracy': 'structural mapping; wave presence and source identity need separate checks'}
