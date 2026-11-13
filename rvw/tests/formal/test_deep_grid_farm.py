import json
import sys
from types import SimpleNamespace
from rvw.formal import grid_farm
from rvw.farm.executor import worker


def model():
    return {'states': {'a': {'x': 0}}, 'initial': ['a'], 'edges': [['a', 'a']],
            'properties': {'safe': [], 'broken': ['a']}}


def test_real_adapter_over_farm_transport(tmp_path, monkeypatch):
    # Run the existing farm payload endpoint locally. This does not test SSH.
    def remote(cmd, **kwargs):
        request = json.loads(kwargs['input'])
        reply = worker(request)
        return SimpleNamespace(stdout=json.dumps(reply), stderr='', returncode=0, timed_out=False)
    monkeypatch.setattr(grid_farm, 'run_group', remote)
    r = grid_farm.distributed(model(), [{'name': 'test', 'address': 'test', 'python': sys.executable}],
                              tmp_path / 'out', workers=1, method='cegar')
    assert r['status'] == 'fail'
    assert [s['status'] for s in r['shards']] == ['pass', 'fail']
    assert len(r['rows']) == 2


def test_remote_loss_cannot_pass(tmp_path, monkeypatch):
    monkeypatch.setattr(grid_farm, 'run_group', lambda *a, **k: SimpleNamespace(returncode=255, stderr='lost', timed_out=False))
    monkeypatch.setattr(grid_farm, 'cancel_host', lambda c: {'acknowledged': False})
    r = grid_farm.distributed(model(), [{'name': 'test', 'address': 'test'}], tmp_path / 'out')
    assert r['status'] == 'inconclusive'
    assert r['shards'][1]['cancellation']['acknowledged'] is False
