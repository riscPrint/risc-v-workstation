import json

import pytest

from rvw.formal.scenario_compile import compile_scenario

pytestmark = pytest.mark.fast


def description():
    return dict(schema='rvw.scenario/1', resources={'bus': 1}, actions=[
        dict(id='write', kind='write', claims={'bus': 1}, args={'address':4096,'value':85}, expect={'value':85}),
        dict(id='read', kind='read', after=['write'], claims={'bus': 1}, args={'address':4096}, expect={'value':85})],
        backends={name:dict(unit='cycles', bindings={'read':dict(operation='read32',duration=1),
            'write':dict(operation='write32',duration=1)}) for name in ['baremetal','pyuvm']})


def test_emit_image_and_virtual_sequence_without_execution(tmp_path):
    out = tmp_path / 'compiled'
    report = compile_scenario(description(), out, finisher=8192)
    assert report['status'] == 'generated'
    assert report['actions'] == 2
    code = (out / 'program.S').read_text()
    assert code.index('sw t0,0(t1)') < code.index('lw t0,0(t1)')
    assert 'bne t0,t2,scenario_fail' in code
    assert 'li t1,0x00002000' in code
    compile((out / 'scenario_sequence.py').read_text(), 'scenario_sequence.py', 'exec')
    assert not (out / 'pyuvm-observations.json').exists()
    plans = [json.loads((out / name).read_text()) for name in ('baremetal-plan.json','pyuvm-plan.json')]
    assert plans[0]['scenario_id'] == plans[1]['scenario_id']
    assert plans[0]['plan_id'] != plans[1]['plan_id']


@pytest.mark.parametrize('change,match', [('alignment','aligned'),('value','32-bit'),('data','dynamic data'),('binding','read32 or write32')])
def test_refuse_unimplemented_execution_forms(tmp_path, change, match):
    data = description()
    if change == 'alignment': data['actions'][0]['args']['address'] += 1
    if change == 'value': data['actions'][0]['args']['value'] = -1
    if change == 'data':
        data['actions'][0]['produces'] = ['x']
    if change == 'binding': data['backends']['baremetal']['bindings']['write']['operation'] = 'unknown'
    with pytest.raises(ValueError, match=match):
        compile_scenario(data, tmp_path / 'out', finisher=8192)
    assert not (tmp_path / 'out').exists()


def test_clobber_is_refused(tmp_path):
    with pytest.raises(FileExistsError):
        compile_scenario(description(), tmp_path, finisher=8192)


def test_unaligned_finisher_is_refused(tmp_path):
    with pytest.raises(ValueError, match='finisher must be word aligned'):
        compile_scenario(description(), tmp_path / 'out', finisher=8193)
    assert not (tmp_path / 'out').exists()
