import copy
import json
from pathlib import Path
import shutil
import sys

import pytest
from rvw.formal import proof_cache
from rvw.common.proc import run_group


def test_cache_checks_dependencies_artifacts_and_admission(tmp_path):
    root = tmp_path / 'cache'
    out = tmp_path / 'out'
    (out / 'sby/model').mkdir(parents=True)
    (out / 'sby/model/design_prep.il').write_text('model')
    (out / 'sby/logfile.txt').write_text('DONE (PASS, rc=0)')
    identity = {'property': 'a', 'model': 'x', 'assumptions': ['reset'], 'tools': 'tool'}
    good = {'status': 'pass', 'assertions': 1, 'reachability': {'status': 'reachable'}}
    for bad in [{'status': 'unknown'}, {**good, 'assertions': 0},
                {**good, 'reachability': {'status': 'unknown'}}, {**good, 'cause': 'changed'}]:
        proof_cache.publish(root, identity, out, bad)
        assert not root.exists()
    proof_cache.publish(root, identity, out, good)
    target = tmp_path / 'hit'
    target.mkdir()
    assert proof_cache.restore(root, identity, target)
    assert (target / 'sby/model/design_prep.il').read_text() == 'model'
    for field in identity:
        changed = copy.deepcopy(identity)
        changed[field] = 'changed'
        assert not proof_cache.restore(root, changed, tmp_path / 'miss')
    entry = root / proof_cache.key_for(identity)
    (entry / 'sby/model/design_prep.il').write_text('corrupt')
    assert not proof_cache.restore(root, identity, tmp_path / 'corrupt')


@pytest.mark.parametrize('mode,engine', [('bmc', 'smtbmc:yices'), ('prove', 'abc:pdr')])
def test_native_cache_reuses_and_invalidates(tmp_path, mode, engine):
    if not all(shutil.which(t) for t in ('sby', 'yosys', 'yices-smt2')):
        pytest.skip('optional native formal tools missing')
    source = tmp_path / 'top.sv'
    source.write_text('module top(input clk); reg [3:0] count=0; '
                      'always @(posedge clk) begin count<=count+1; assert(count<16); end endmodule')
    def check(index):
        out = tmp_path / f'out-{index}'
        proc = run_group([sys.executable, '-m', 'rvw', 'formal', mode, '--engine', engine, '--verilog', str(source),
                          '--top', 'top', '--depth', '4', '--out', str(out), '--timeout', '15',
                          '--proof-cache', str(tmp_path / 'cache')], capture=True, timeout=30)
        assert proc.returncode == 0, (proc.stdout, proc.stderr)
        return json.loads((out / 'result.json').read_text())
    first, second = check(1), check(2)
    assert first['proof_cache']['hit'] is False
    assert second['proof_cache']['hit'] is True, (first['proof_cache'], second['proof_cache'])
    assert first['proof_cache']['key'] == second['proof_cache']['key']
    assert second['reachability']['status'] == 'reachable'
    source.write_text(source.read_text().replace('count<16', 'count<=15'))
    third = check(3)
    assert third['proof_cache']['hit'] is False
    assert third['proof_cache']['key'] != first['proof_cache']['key']


@pytest.mark.parametrize('record', [None, [], {'identity': {}, 'files': None}])
def test_malformed_cache_record_is_a_miss(tmp_path, record):
    identity = {'test': 'key'}
    entry = tmp_path / proof_cache.key_for(identity)
    entry.mkdir()
    (entry / 'entry.json').write_text(json.dumps(record))
    assert proof_cache.restore(tmp_path, identity, tmp_path / 'out') is False
