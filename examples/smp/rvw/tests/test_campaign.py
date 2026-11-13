import runpy
from pathlib import Path
import pytest
pytestmark=pytest.mark.fast
campaign=runpy.run_path(str(Path(__file__).parents[1]/'campaign.py'))


def test_contention_checks_shared_total_after_all_harts_finish():
    for harts in (2,3,4):
        text=campaign['contention'](0,harts)
        assert 'li s0, 0x81000000' in text
        assert 'lr.d.aq' in text and 'sc.d.rl' in text
        assert f'li t2, {harts*32}' in text
        assert f'li t2, {harts}' in text
        assert 'amoadd.d.aqrl' in text


def test_prepare_has_fixed_budget_and_all_pinned_cases(tmp_path, monkeypatch):
    import json
    import rvw.memory.concurrent_build
    calls=[]
    def fake_random(out, **kwargs):
        calls.append(kwargs)
        return {'status':'built'}
    monkeypatch.setattr(rvw.memory.concurrent_build,'build',fake_random)
    monkeypatch.setattr(runpy,'run_path',lambda path:{'build':lambda *args,**kwargs:None})
    destination=tmp_path/'campaign'
    manifest=campaign['prepare'](destination,tmp_path/'pinned-tests')
    jobs=[json.loads(line) for line in manifest.read_text().splitlines()]
    spec=json.loads((destination/'campaign.json').read_text())
    assert len(jobs)==28
    assert len([case for case in spec['cases'] if case['kind']=='litmus'])==6
    assert [call['seed'] for call in calls]==list(range(1,17))
    assert all(call['length']==16 and call['harts']==2 for call in calls)
    assert [j['config'] for j in jobs[-6:]]==['smp2','smp2','smp3','smp3','smp4','smp4']
    assert all(j['rvfi_trace'] and j['wall_timeout']==120 for j in jobs)
