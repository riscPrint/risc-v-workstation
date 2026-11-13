"""Split explicit-model properties across local workers."""
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
from pathlib import Path
from .deep_model import validate, induction, abstract


def grid(model, out, *, workers=1, method='cegar', max_k=8, max_refinements=32):
    validate(model)
    if workers < 1 or method not in ('cegar', 'induction'):
        raise ValueError('positive workers and a known method are required')
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    raw = json.dumps(model, sort_keys=True).encode()
    (out / 'model.json').write_bytes(raw)
    def solve(prop):
        if method == 'induction':
            result = induction(model, prop, max_k, model.get('samples', []))
        else:
            result = abstract(model, prop, model.get('visible', []), max_refinements)
        return {'property': prop, **result}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        rows = list(pool.map(solve, model['properties']))
    status = 'fail' if any(r['status'] == 'fail' for r in rows) else 'pass' if all(r['status'] == 'pass' for r in rows) else 'inconclusive'
    report = {'schema': 'rvw.formal-model-grid/1', 'status': status, 'model_sha256': sha256(raw).hexdigest(),
              'rows': rows, 'method': method, 'workers': workers,
              'limits': 'Proof covers only this explicit transition graph. No RTL translation or memory-contract proof is implied.'}
    (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report
