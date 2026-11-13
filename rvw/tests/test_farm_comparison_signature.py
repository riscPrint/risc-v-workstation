import hashlib
import json
import pytest
from rvw.farm.triage import triage
from rvw.results import SuiteResults, TestEntry, save_results

pytestmark = pytest.mark.fast


def setup_run(root, good=False):
    digest = hashlib.sha256(b'elf').hexdigest()
    test = TestEntry('xor', 'pass' if good else 'fail', seed=1, run='cell', signature=None if good else 'fail:2',
                     extra={'elf_sha256': digest, 'options': {'max_cycles': 100}})
    save_results(SuiteResults('run', 'isa', 'generic', 'small', '2026-11-13',
        source={'core_rev_full': ('a' if good else 'b')*40, 'core_dirty': False, 'core_repo': '/work/core'}, tests=[test]), root)
    cell = root/'cell';cell.mkdir()
    trace = b'recorded trace';(cell/'rvfi.jsonl').write_bytes(trace)
    (cell/'result.json').write_text(json.dumps(dict(schema='rvw.run/1',core='generic',config='small',seed=1,
        status=test.status,elf_sha256=digest,artifacts={'rvfi_trace':'rvfi.jsonl'})))
    comparison = dict(schema='rvw.cosim/1', status='mismatch', model='spike', synchronized=1,
        recent_synchronizations=[{'reason':'csr_reset_unknown'}],
        mismatch={'pc':'0x80000198','actual':{'insn':'0xf0f6c713'}},
        reproduction={'capture':{'files':[{'sha256':digest},{'sha256':hashlib.sha256(trace).hexdigest()}]}})
    return cell, comparison


def test_bound_comparison_signature_and_bisect_range(tmp_path):
    cell, comparison = setup_run(tmp_path/'bad')
    setup_run(tmp_path/'good', True)
    (cell/'cosim.json').write_text(json.dumps(comparison))
    report = triage(tmp_path/'bad', baseline=tmp_path/'good', core_env='CORE_SOURCE')
    cluster = report['clusters'][0]
    assert cluster['signature'] == 'mismatch:["0x80000198", "0xf0f6c713"]'
    assert cluster['members'][0]['comparison']['synchronized'] == 1
    assert cluster['commit_ranges'] == ['a'*40+'..'+'b'*40]
    assert cluster['bisect'][0]['command'][-2:] == ['--core-env','CORE_SOURCE']
    assert cluster['bisect'][0]['execution'] == 'not_run'
    assert report['diff']['verdict'] == 'reject'


@pytest.mark.parametrize('mutation', ['trace', 'seed', 'instruction'])
def test_unbound_or_incomplete_comparison_does_not_replace_c1_failure(tmp_path, mutation):
    cell, comparison = setup_run(tmp_path/'bad')
    if mutation == 'trace':
        (cell/'rvfi.jsonl').write_bytes(b'changed trace')
    elif mutation == 'seed':
        path=cell/'result.json';d=json.loads(path.read_text());d['seed']=2;path.write_text(json.dumps(d))
    else:
        comparison['mismatch']['actual']={}
    (cell/'cosim.json').write_text(json.dumps(comparison))
    report = triage(tmp_path/'bad')
    assert report['clusters'][0]['signature'] == 'fail:2'
    assert len(report['issues']) == 1
    assert not report['failures_waived']
