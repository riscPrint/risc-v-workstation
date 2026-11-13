from copy import deepcopy
from itertools import permutations

import pytest

from rvw.formal.scenario import check, fits, plan


def scenario():
    return dict(schema='rvw.scenario/1', resources=dict(bus=1, cpu=2), inputs=dict(seed=7), actions=[
        dict(id='prepare', kind='prepare', claims=dict(cpu=1), needs=['seed'], produces=['buffer'], expect=dict(size=4)),
        dict(id='write', kind='transfer', claims=dict(bus=1), needs=['buffer'], expect=dict(done=True)),
        dict(id='read', kind='transfer', claims=dict(bus=1), needs=['buffer'], expect=dict(done=True))],
        backends={name:dict(unit=unit,bindings=dict(prepare=dict(operation=f'{name}.prepare',duration=n),
                                                  transfer=dict(operation=f'{name}.transfer',duration=2*n)))
                  for name,unit,n in [('model','steps',1),('rtl','cycles',3),('fpga','ticks',10)]})


def observations(p):
    rows = []
    for action in p['actions']:
        rows.append(dict(id=action['id'], operation=action['operation'], start=action['start'], end=action['end'],
                         outputs=action.get('expect', {}), data={k:[1,2,3,4] for k in action.get('produces', [])},
                         inputs={k:7 if k == 'seed' else [1,2,3,4] for k in action.get('needs', [])}))
    return dict(schema='rvw.scenario-observation/1', plan_id=p['plan_id'], backend=p['backend'], unit=p['unit'], actions=rows)


def test_backend_portability_and_determinism():
    source = scenario()
    plans = [plan(source, b) for b in ('model','rtl','fpga')]
    assert len({p['scenario_id'] for p in plans}) == 1
    assert len({p['plan_id'] for p in plans}) == 3
    expected = plans[0]
    for order in permutations(source['actions']):
        assert plan(dict(source, actions=list(order)), 'model') == expected
    by_id = {a['id']:a for a in expected['actions']}
    assert by_id['prepare']['end'] <= by_id['read']['start']
    assert by_id['read']['end'] <= by_id['write']['start']
    assert all(check(p, observations(p))['status'] == 'match' for p in plans)


def test_capacity_segments():
    assert fits([(0,2,1),(2,4,1)], 0,4,1,2)
    assert not fits([(0,3,1),(2,4,1)], 0,4,1,2)


@pytest.mark.parametrize('fault', ['outcome','data','dependency','resource','operation','missing','empty_expect'])
def test_observation_faults(fault):
    source = scenario()
    if fault == 'empty_expect':
        for a in source['actions']:
            a.pop('expect')
    p = plan(source,'rtl')
    obs = observations(p)
    rows = {a['id']:a for a in obs['actions']}
    if fault == 'outcome': rows['write']['outputs'] = dict(done=False)
    if fault == 'data': rows['write']['inputs']['buffer'] = [9]
    if fault == 'dependency': rows['write'].update(start=0,end=1)
    if fault == 'resource': rows['write'].update(start=rows['read']['start'],end=rows['read']['end'])
    if fault == 'operation': rows['write']['operation'] = 'wrong.adapter'
    if fault == 'missing': obs['actions'].pop()
    assert check(p,obs)['status'] == ('inconclusive' if fault in ('missing','empty_expect') else 'mismatch')


@pytest.mark.parametrize('fault', ['cycle','producer','claim','constraint','binding'])
def test_invalid_scenarios(fault):
    source = scenario()
    if fault == 'cycle': source['actions'][0]['after'] = ['write']
    if fault == 'producer': source['actions'][1]['needs'] = ['absent']
    if fault == 'claim': source['actions'][1]['claims']['bus'] = 2
    if fault == 'constraint': source['actions'][0].update(args=dict(size=4),constraints=[dict(field='size',op='lt',value=2)])
    if fault == 'binding': source['backends']['model']['bindings'].pop('prepare')
    with pytest.raises((ValueError,KeyError)):
        plan(source,'model')


def test_stale_result_removed(tmp_path):
    from argparse import Namespace
    from rvw.formal.scenario import run
    source, output = tmp_path / 'invalid.json', tmp_path / 'result.json'
    source.write_text('{}')
    output.write_text('{"status":"match"}')
    with pytest.raises(ValueError):
        run(Namespace(source=str(source), out=str(output), backend='model', action='plan'))
    assert not output.exists()


def test_cli_plan_and_check(tmp_path):
    import json
    from rvw.cli import main
    source, planned = tmp_path / 'scenario.json', tmp_path / 'plan.json'
    source.write_text(json.dumps(scenario()))
    assert main(['formal','scenario','plan',str(source),'--backend','rtl','--out',str(planned)]) == 0
    data = json.loads(planned.read_text())
    observed, result = tmp_path / 'observed.json', tmp_path / 'check.json'
    observed.write_text(json.dumps(observations(data)))
    assert main(['formal','scenario','check',str(planned),'--observed',str(observed),'--out',str(result)]) == 0
    assert json.loads(result.read_text())['status'] == 'match'
