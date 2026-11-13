"""Local and farm proof grids over pinned, independently exported RTL properties."""
import base64
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
from pathlib import Path
import re
from .portfolio import race


def bundle(plan, root):
    properties, blobs = {}, {}
    for case in plan['cases']:
        name = case['id']
        if not re.fullmatch(r'[A-Za-z0-9_-]+', name) or name in properties or name == 'sources':
            raise ValueError('property IDs must be unique simple names')
        sources = []
        for source in case['sources']:
            data = (Path(root) / source['path']).read_bytes()
            digest = sha256(data).hexdigest()
            if digest != source['sha256']:
                raise ValueError('grid source hash mismatch')
            blobs[digest] = base64.b64encode(data).decode()
            sources.append({**source, 'path': digest + '.input'})
        properties[name] = {**case, 'sources': sources, 'engines': case.get('engines', plan.get('engines', ['abc:pdr']))}
    if not properties:
        raise ValueError('grid needs properties')
    return {'input_kind': 'rtl', 'properties': properties, 'blobs': blobs,
            'engine_timeout': plan.get('engine_timeout', 15), 'cross_check': plan.get('cross_check', False)}


def local(model, out, *, workers=1, **unused):
    if not model.get('properties'):
        raise ValueError('grid needs properties')
    if workers < 1:
        raise ValueError('positive workers required')
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    source = out / 'sources'
    source.mkdir()
    for digest, text in model['blobs'].items():
        data = base64.b64decode(text, validate=True)
        if sha256(data).hexdigest() != digest:
            raise ValueError('grid payload hash mismatch')
        (source / (digest + '.input')).write_bytes(data)
    def solve(item):
        name, case = item
        # Transported manifests are trusted but cannot escape the owned directory.
        if not re.fullmatch(r'[A-Za-z0-9_-]+', name):
            raise ValueError('invalid property ID')
        for s in case['sources']:
            if s['path'] != s['sha256'] + '.input':
                raise ValueError('invalid grid source path')
        report = race(case, source, out / name, timeout=model['engine_timeout'], cross_check=model['cross_check'])
        return {'property': name, 'status': report['status'], 'proof_kind': report.get('proof_kind'),
                'winner': report['winner'], 'result': str(out / name / 'result.json')}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(solve, model['properties'].items()))
    status = 'fail' if any(r['status'] == 'fail' for r in rows) else 'pass' if all(r['status'] == 'pass' for r in rows) else 'inconclusive'
    report = {'schema': 'rvw.formal-rtl-grid/1', 'status': status, 'rows': rows,
              'model_sha256': sha256(json.dumps(model, sort_keys=True).encode()).hexdigest(),
              'limits': 'Each case is a separately exported safety problem. Source assumptions require separate activation checks.'}
    (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report
