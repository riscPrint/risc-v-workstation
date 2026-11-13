import json
from argparse import Namespace
from pathlib import Path
import shutil
import pytest
from rvw.formal.autocheck import expand
from rvw.formal.apps import generate, run


def plan():
    return {'schema': 'rvw.autocheck/1', 'top': 'Top', 'clock': 'clk', 'reset': 'reset',
            'ports': {'clk': {'direction': 'input', 'width': 1},
                      'reset': {'direction': 'input', 'width': 1},
                      'state': {'direction': 'output', 'width': 2}},
            'fsms': [{'signal': 'state', 'states': [0, 1, 2], 'transitions': [[0, 1], [1, 2], [2, 0]]}],
            'dead_code': [{'id': 'unused_state', 'expression': 'state == 3'}], 'verilog': ['Top.sv']}


def test_obligations_include_each_bit_and_fsm_edge():
    spec = expand(plan())
    assert len(spec['properties']) == 11
    assert len({p['id'] for p in spec['properties']}) == 11
    for prop in spec['properties']:
        text = generate(spec, prop)
        assert 'assert (' in text
    edge = next(p for p in spec['properties'] if p['kind'] == 'fsm_transition')
    assert 'rvwa_previous' in generate(spec, edge)


def test_invalid_fsm_and_budget():
    spec = plan()
    spec['fsms'][0]['transitions'] = [[0, 3]]
    with pytest.raises(ValueError, match='endpoint'):
        expand(spec)
    with pytest.raises(ValueError, match='property count'):
        expand(plan(), 2)


def test_native_fsm_and_constants(tmp_path):
    if not all(shutil.which(t) for t in ('yosys', 'sby', 'yices-smt2')):
        pytest.skip('native formal tools required')
    spec = expand(plan())
    # Four independent jobs cover reached state/edge, dead state and constant bit.
    spec['properties'] = [dict(id='state1', kind='fsm_state', signal='state', value=1),
                          dict(id='edge01', kind='fsm_transition', signal='state', source_value=0, value=1),
                          dict(id='dead3', kind='dead_code', target='state == 3'),
                          dict(id='constant_high', kind='stuck_at', signal='state', bit=1, value=0)]
    (tmp_path / 'Top.sv').write_text('module Top(input clk, reset, output reg [1:0] state);\n'
        'always @(posedge clk) if (reset) state <= 0; else state <= !state; endmodule\n')
    path = tmp_path / 'apps.json'
    path.write_text(json.dumps(spec))
    args = Namespace(manifest=str(path), out=str(tmp_path / 'out'), depth=6,
                     engine='smtbmc:yices', timeout=15, mode='bmc', json=False)
    assert run(args) == 1
    result = json.loads((tmp_path / 'out/result.json').read_text())
    observations = {p['property_id']: p['observation'] for p in result['properties']}
    assert observations == {'state1': 'reached', 'edge01': 'reached',
                            'dead3': 'not_observed_bounded', 'constant_high': 'holds_bounded'}


def test_existing_contract_failure_is_not_a_constant_result():
    from rvw.formal.automonitors import observation
    assert observation('deadlock', {'status': 'fail', 'proof_kind': 'bounded'}) == 'violated'
    assert observation('stuck_at', {'status': 'pass', 'proof_kind': 'unbounded'}) == 'constant_conditional'
    assert observation('fsm_state', {'status': 'unknown', 'proof_kind': 'bounded'}) == 'inconclusive'


def test_native_autocheck_xprop(tmp_path):
    if not all(shutil.which(t) for t in ('yosys', 'sby', 'yices-smt2')):
        pytest.skip('native formal tools required')
    from rvw.formal.autocheck import run as auto_run
    spec = plan()
    spec['fsms'], spec['dead_code'] = [], []
    (tmp_path / 'Top.sv').write_text('module Top(input clk, reset, output reg [1:0] state);\n'
        'always @(posedge clk) if (reset) state <= 0; else state <= 1; endmodule\n')
    manifest = tmp_path / 'plan.json'
    manifest.write_text(json.dumps(spec))
    args = Namespace(manifest=str(manifest), out=str(tmp_path / 'auto'), depth=5,
                     engine='smtbmc:yices', timeout=15, mode='bmc', json=False,
                     max_properties=8, xprop=True)
    auto_run(args)
    result = json.loads((tmp_path / 'auto/result.json').read_text())
    assert result['xprop']['status'] == 'pass'
    assert (tmp_path / 'auto/spec.json').is_file()


def test_mcp_passes_manifest_positionally():
    from rvw.formal.mcp_tools import _argv
    argv = _argv('autocheck', dict(manifest='plan.json', out='out', xprop=True))
    assert '--manifest' not in argv and argv[-1] == '--xprop'
