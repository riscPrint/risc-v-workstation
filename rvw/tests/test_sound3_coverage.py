import json
from types import SimpleNamespace
import pytest
from rvw.cov.functional import functional

pytestmark = pytest.mark.fast

@pytest.mark.parametrize('status,complete,expected', [('pass', True, 1), ('fail', True, 0), ('pass', False, 0)])
def test_only_complete_c1_pass_earns_bins(tmp_path, monkeypatch, status, complete, expected):
    trace = tmp_path/'trace.jsonl'
    header = dict(schema='rvw.rvfi/1', xlen=64, isa='rv64im', elf_sha256='abc')
    rows = [dict(order=0, insn='0x13', mode=3)]
    if complete:
        rows.append(dict(event='end', status='pass'))
    trace.write_text('\n'.join(json.dumps(r) for r in [header, *rows]))
    (tmp_path/'result.json').write_text('{}')
    run = SimpleNamespace(status=status, why_inconclusive=None, instret=1, elf_sha256='abc', artifact=lambda _: trace)
    monkeypatch.setattr('rvw.results.load_run', lambda _: run)
    class Reader:
        def __init__(self, _): self.header=header
        def __iter__(self): return iter(rows)
        def close(self): pass
    monkeypatch.setattr('rvw.cosim.trace.Trace', Reader)
    result = functional([trace])
    assert result['groups']['class_mode']['expected_hit'] == expected
    assert bool(result['unqualified']['class_mode']) == (not expected)
    saved = tmp_path/'saved.json'
    saved.write_text(json.dumps(result))
    assert functional([saved])['groups'] == result['groups']


def test_closure_refuses_legacy_unqualified_report(tmp_path):
    from rvw.cov.closure import closure
    report, candidates = tmp_path/'coverage.json', tmp_path/'candidates.json'
    report.write_text(json.dumps({'schema': 'rvw.functional-coverage/1', 'groups': {}}))
    candidates.write_text(json.dumps({'schema': 'rvw.coverage-candidates/1', 'tests': []}))
    with pytest.raises(ValueError, match='no run qualification'):
        closure(report, candidates)

@pytest.mark.parametrize('status,ended,qualified', [('pass',True,True),('fail',True,False),('pass',False,False)])
def test_real_c1_and_c2_readers(tmp_path, status, ended, qualified):
    header=dict(schema='rvw.rvfi/1',xlen=64,isa='rv64im',core='fixture',config='small',elf='fixture',elf_sha256='a'*64)
    row=dict(order=0,cycle=0,mode=3,rs1=0,rs2=0,rd=0,mem_rmask=0,mem_wmask=0,
             trap=False,intr=False,halt=False,mem_fault=False)
    row.update({k:'0x0' for k in 'pc pc_next insn rs1_rdata rs2_rdata rd_wdata mem_addr mem_rdata mem_wdata'.split()})
    row['insn']='0x13'
    rows=[header,row]
    if ended: rows.append(dict(event='end',cycle=1,status='pass'))
    trace=tmp_path/'trace.jsonl';trace.write_text('\n'.join(map(json.dumps,rows)))
    (tmp_path/'result.json').write_text(json.dumps(dict(schema='rvw.run/1',core='fixture',config='small',status=status,
        elf_sha256='a'*64,instret=1,artifacts={'rvfi_trace':'trace.jsonl'})))
    report=functional([trace])
    assert bool(report['groups']['class_mode']['hits'])==qualified
