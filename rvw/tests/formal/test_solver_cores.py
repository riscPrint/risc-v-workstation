import json
import shutil
from argparse import Namespace
import pytest
from rvw.formal.cores import prepare, extract, expressions, run


def test_split_comments_strings_and_quoted_symbols():
    assert expressions('; ignored\n(declare-const |a b| Bool) (echo "(;)")')[1] == ['echo', '"(;)"']


def test_prepare_requires_all_names():
    with pytest.raises(ValueError, match='each assertion'):
        prepare('(assert false)')
    with pytest.raises(ValueError, match='unsupported'):
        prepare('(push 1)')


def test_deletion_core_keeps_unknown_and_drops_redundant():
    def solve(base, selected):
        if 'a' not in selected:
            return 'unknown', []
        if 'b' not in selected:
            return 'sat', []
        return 'unsat', list(selected)
    result = extract([], dict(a='a', b='b', c='c'), solve)
    assert result['labels'] == ['a', 'b']
    assert not result['minimal']


def test_sat_is_inconclusive():
    assert extract([], {'a': 'a'}, lambda *_: ('sat', []))['status'] == 'inconclusive'


def test_invalid_solver_core_is_refused():
    with pytest.raises(ValueError, match='unknown core'):
        extract([], {'a': 'a'}, lambda *_: ('unsat', ['missing']))


def test_native_z3(tmp_path):
    if not shutil.which('z3'):
        pytest.skip('z3 required')
    query = tmp_path / 'query.smt2'
    query.write_text('(declare-const x Bool)\n(assert (! x :named a))\n'
                     '(assert (! (not x) :named b))\n(assert (! true :named unused))\n')
    mapping = tmp_path / 'map.json'
    mapping.write_text(json.dumps({'schema': 'rvw.smt-bindings/1', 'property_id': 'p',
                                  'constraints': {n: {'signals': ['x']} for n in ('a', 'b', 'unused')}}))
    args = Namespace(smt2=str(query), mapping=str(mapping), out=str(tmp_path / 'out'),
                     solver='z3', timeout=10, db=None, json=False)
    assert run(args) == 0
    result = json.loads((tmp_path / 'out/result.json').read_text())
    assert result['labels'] == ['a', 'b'] and result['minimal']
    assert result['property_id'] == 'p'
