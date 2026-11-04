import copy
import json
from argparse import Namespace

import pytest

from rvw.formal.contracts import validate, harness, run
from rvw.formal.invariants import render


def plan():
    return {'signals': {'token': 1, 'accepted': 1},
            'predicates': {'token_ok': 'token == 1', 'accept_ok': 'accepted == 1'},
            'components': [
                {'id': 'producer', 'top': 'Producer', 'inputs': [], 'outputs': ['token'],
                 'assumes': [], 'guarantees': ['token_ok']},
                {'id': 'consumer', 'top': 'Consumer', 'inputs': ['token'], 'outputs': ['accepted'],
                 'assumes': ['token_ok'], 'guarantees': ['accept_ok']} ]}


def test_dag_and_closed_harness():
    p = plan()
    assert validate(p) == ['producer', 'consumer']
    assert 'assume(token == 1)' in harness(p, 'consumer')
    assert 'assume(' not in harness(p)
    assert '.token(token)' in harness(p)


@pytest.mark.parametrize('change,match', [
    (lambda p: p['components'][0]['assumes'].append('accept_ok'), 'outside component'),
    (lambda p: p['components'][0]['guarantees'].clear(), 'needs guarantees'),
    (lambda p: p['components'][1]['outputs'].append('token'), 'multiple interface'),
    (lambda p: p['predicates'].update(token_ok='token); assume(0);'), 'combinational'),
    (lambda p: p['predicates'].update(token_ok='$past(token)'), 'combinational'),
])
def test_invalid_contracts(change, match):
    p = plan()
    change(p)
    with pytest.raises(ValueError, match=match):
        validate(p)


def test_cycle_and_missing_provider():
    p = plan()
    p['components'][0]['inputs'] = ['accepted']
    p['components'][0]['assumes'] = ['accept_ok']
    with pytest.raises(ValueError, match='circular'):
        validate(p)
    p = plan()
    p['predicates']['other'] = 'token == 0'
    p['components'][0]['guarantees'] = ['other']
    with pytest.raises(ValueError, match='no neighbour'):
        validate(p)


def test_composition_requires_closed_proof(tmp_path, monkeypatch):
    from rvw.formal import cli
    def flow(_, args):
        out = __import__('pathlib').Path(args.out)
        out.mkdir()
        (out / 'module_ports.json').write_text(json.dumps({'modules': {
            n['top']: {'ports': {
                **{s: {'direction': 'input', 'bits': [0]} for s in ['clk', 'reset'] + n['inputs']},
                **{s: {'direction': 'output', 'bits': [0]} for s in n['outputs']}}}
            for n in plan()['components']}}))
        (out / 'result.json').write_text(json.dumps({
            'status': 'unknown' if out.name == 'closed' else 'pass', 'proof_kind': 'unbounded'}))
    monkeypatch.setattr(cli, '_flow', flow)
    p = plan()
    p['verilog'] = []
    manifest = tmp_path / 'plan.json'
    manifest.write_text(json.dumps(p))
    out = tmp_path / 'out'
    assert run(Namespace(manifest=manifest, out=out, budget=10, depth=8, engine='abc:pdr', json=False)) == 1
    assert json.loads((out / 'result.json').read_text())['status'] == 'inconclusive'


@pytest.mark.parametrize('kind', ['rob', 'credit', 'freelist', 'rename', 'issue', 'lsq'])
def test_template_no_hidden_assumptions(kind):
    text = render(kind)
    assert 'assert(' in text
    assert 'assume(' not in text


def test_parameter_overflow_refused():
    with pytest.raises(ValueError, match='overflow'):
        render('credit', 8, 3)


def test_port_width_changes_are_refused():
    from rvw.formal.contracts import check_ports
    model = {'modules': {'Producer': {'ports': {
        'clk': {'direction': 'input', 'bits': [1]},
        'reset': {'direction': 'input', 'bits': [2]},
        'token': {'direction': 'output', 'bits': [3, 4]}}}}}
    with pytest.raises(ValueError, match='typed contract'):
        check_ports(plan(), model)


def test_mining_does_not_certify_observations():
    from rvw.formal.mining import candidates
    assert candidates({'count': 3}, [{'count': 1}, {'count': 4}]) == {
        'bound_count': '(count >= 1) && (count <= 4)'}
    with pytest.raises(ValueError, match='unsigned'):
        candidates({'count': 3}, [{'count': 8}])


def test_abstraction_metadata_and_refused_assumptions(tmp_path, monkeypatch):
    from rvw.formal import cuts
    from rvw.common.capture import Capture
    def probe(*_):
        (tmp_path / 'cut-model.json').write_text(json.dumps({'modules': {'rvw_formal_top': {
            'netnames': {'dut.read_data': {'bits': [2, 3]}, 'dut.clk': {'bits': [1]}}}}}))
        return 0, 0
    monkeypatch.setattr(cuts.common, 'run', probe)
    path = tmp_path / 'abstraction.json'
    path.write_text(json.dumps({'cuts': [{'signal': 'read_data', 'width': 2, 'kind': 'memory-read'}]}))
    args = Namespace(cut=[], abstraction=path, clock='clk', timeout=1,
                     _input_snapshot=Namespace(capture=Capture(tmp_path / 'inputs')))
    _, records = cuts.commands(args, tmp_path, [])
    assert records[0]['kind'] == 'memory-read'
    assert records[0]['semantics'] == 'unconstrained_anyseq'
    path.write_text(json.dumps({'cuts': [{'signal': 'read_data', 'width': 2, 'kind': 'memory-read', 'assume': '0'}]}))
    # A new capture represents a new run.
    args._input_snapshot = Namespace(capture=Capture(tmp_path / 'other'))
    with pytest.raises(ValueError, match='assumptions need contracts'):
        cuts.commands(args, tmp_path, [])


def test_environment_assumptions_keep_source_locations():
    from rvw.formal.contracts import assumption_inventory
    model = {'modules': {'Unit': {'cells': {
        'environment': {'type': '$check', 'parameters': {'FLAVOR': 'assume'}, 'attributes': {'src': 'unit.sv:4'}},
        'guarantee': {'type': '$assert'}}}}}
    assert assumption_inventory(model) == [
        {'module': 'Unit', 'cell': 'environment', 'source': 'unit.sv:4', 'type': '$check'}]


def test_freelist_export_recipe_rejects_wrong_capacity(tmp_path):
    from pathlib import Path
    import subprocess
    import sys
    script = Path(__file__).resolve().parents[3] / 'SpinalChecks/boom/freelist-capacity.py'
    source = tmp_path / 'Wrong.v'
    source.write_text('''module RenameFreeList (
 input wire clk,
 input wire reset,
 output wire io_alloc_pregs_0_valid,
 output wire [5:0] io_alloc_pregs_0_payload,
 output wire [52:0] io_debug_freelist
);
endmodule
''')
    out = tmp_path / 'prepared'
    run = subprocess.run([sys.executable, str(script), '--verilog', str(source), '--out', str(out)],
                         capture_output=True, text=True)
    assert run.returncode != 0
    assert '52-entry' in run.stderr
    assert not out.exists()
