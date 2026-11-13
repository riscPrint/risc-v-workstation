import hashlib
import json

import pytest
from rvw.farm.triage import triage
from rvw.results import SuiteResults, TestEntry, save_results

pytestmark = pytest.mark.fast


def setup(root, status='fail', cause='0xb'):
    source={'core_rev_full':'a'*40}
    digest=hashlib.sha256(b'elf').hexdigest()
    test=TestEntry('ecall',status,seed=1,run='cell',signature='fail:2' if status=='fail' else None,
                   extra=dict(elf_sha256=digest,details={'traps':1}))
    save_results(SuiteResults('native','isa','generic','small','2026-11-13',source=source,tests=[test]),root)
    cell=root/'cell';cell.mkdir()
    run=dict(schema='rvw.run/1',core='generic',config='small',seed=1,status=status,source=source,
             elf_sha256=digest,rtl_sha256='b'*64,details={'traps':1},artifacts={'rvfi_trace':'rvfi.jsonl'})
    (cell/'result.json').write_text(json.dumps(run))
    records=[dict(schema='rvw.rvfi/2',xlen=32,isa='rv32im',core='generic',config='small',elf='/input',
                  elf_sha256=digest,rtl_sha256='b'*64,seed=1,source=source),
             dict(event='trap',cycle=10,cause=cause,tval='0x73',intr=False),
             dict(event='end',cycle=20,status=status)]
    (cell/'rvfi.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
    return cell,records


def test_native_trap_fingerprint_is_observation_not_root_cause(tmp_path):
    setup(tmp_path)
    cluster=triage(tmp_path)['clusters'][0]
    assert cluster['signature']=='trap:0xb'
    assert cluster['members'][0]['signature']=='fail:2'
    trap=cluster['members'][0]['trap_observation']
    assert trap['root_cause']=='not_established'
    assert trap['traps']==1
    assert len(trap['trace_sha256'])==64


@pytest.mark.parametrize('change',['header','end','invalid_cause','count','seed','inconclusive'])
def test_unbound_trap_retains_failure_and_reports_issue(tmp_path,change):
    cell,records=setup(tmp_path)
    if change=='header':records[0]['elf_sha256']='c'*64
    elif change=='end':records.pop()
    elif change=='invalid_cause':records[1]['cause']='not-a-cause'
    else:
        path=cell/'result.json';raw=json.loads(path.read_text())
        if change=='count':raw['details']['traps']=2
        elif change=='seed':raw['seed']=2
        else:raw['synthesized']=True
        path.write_text(json.dumps(raw))
    (cell/'rvfi.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in records))
    result=triage(tmp_path)
    assert result['clusters'][0]['signature']=='fail:2'
    assert len(result['issues'])==1


def test_passing_trap_is_not_a_failure_cluster(tmp_path):
    setup(tmp_path,status='pass')
    assert triage(tmp_path)['clusters']==[]


def test_different_native_trap_causes_stay_separate(tmp_path):
    setup(tmp_path/'ecall', cause='0xb')
    setup(tmp_path/'breakpoint', cause='0x3')
    assert {c['signature'] for c in triage(tmp_path)['clusters']} == {'trap:0xb', 'trap:0x3'}
