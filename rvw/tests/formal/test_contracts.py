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
