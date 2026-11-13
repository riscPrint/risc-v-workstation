from hashlib import sha256
import json
import shutil
import pytest
from rvw.formal.aiger_live import check
from test_aiger_live_model import progress_model


@pytest.mark.parametrize('method', ['l2s', 'k-live', 'rlive'])
def test_native_progress_and_fairness(tmp_path, method):
    if not shutil.which('rIC3'):
        pytest.skip('optional native rIC3 missing')
    for name, kind, fairness, expected in [
            ('toggle', 'toggle', None, 'pass'), ('stuck', 'stuck', None, 'fail'),
            ('fair', 'input', 'ready', 'pass'), ('unfair', 'input', None, 'fail'),
            ('infeasible', 'input', 'false', 'inconclusive')]:
        source = tmp_path / (name + '.aag')
        source.write_text(progress_model(kind, fairness))
        plan = {'path': source.name, 'sha256': sha256(source.read_bytes()).hexdigest()}
        out = tmp_path / name
        r = check(plan, tmp_path, out, method=method, k=4, timeout=12)
        (out / 'result.json').write_text(json.dumps(r, indent=2))
        if method == 'rlive' and r.get('reason') in ('error', 'timeout', 'inconclusive'):
            assert r['status'] == 'inconclusive' and r['proof_kind'] == 'none', r
            continue
        # K-liveness cannot turn a reachable bound into a counterexample.
        if method == 'k-live' and expected == 'fail':
            assert r['status'] == 'inconclusive' and r['reason'] == 'k_bound_reached', r
        else:
            assert r['status'] == expected, r
        if name == 'infeasible':
            assert r['fairness_check'] == 'infeasible', r
