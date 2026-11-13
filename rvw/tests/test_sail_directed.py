"""Fixture oracle tests. No native Sail or DUT evidence is claimed."""
from contextlib import nullcontext
from pathlib import Path
import pytest
from rvw.regress import sail_tests as s
from rvw.cosim.dii import Retirement


def fixture_oracle(monkeypatch):
    monkeypatch.setattr(s,'property_trace',lambda model,name:{'id':'sail.rv32i.'+name+'.result','sail':{'sha256':'a'*64}})
    monkeypatch.setattr(s.socket,'create_connection',lambda *a:nullcontext(object()))
    def exchange(connection,tokens,**kwargs):
        regs=[0]*32;rows=[]
        for i,token in enumerate(tokens):
            w=token.insn;rd=w>>7&31;a=w>>15&31;b=w>>20&31
            if w&127==0x37: result=w&0xfffff000
            elif w&127==0x13:
                imm=w>>20;imm=imm-4096 if imm&2048 else imm
                result=regs[a]+imm
            elif w>>25&32: result=regs[a]-regs[b]
            else: result=regs[a]+regs[b]
            if rd: regs[rd]=result&0xffffffff
            rows.append(Retirement(order=i,insn=w,rd_addr=rd,rd_wdata=regs[rd],pc_rdata=0x80000000+4*i))
        return rows
    monkeypatch.setattr(s,'exchange',exchange)


def test_rule_named_tests_have_reference_expectations_and_mutants(tmp_path,monkeypatch):
    fixture_oracle(monkeypatch)
    result=s.generate('model',tmp_path/'out','localhost:1234',[5,6,7,8],cases=6)
    assert result['status']=='reference_generated' and result['reference_identity_verified'] is False
    assert len(result['cases'])==6
    for case in result['cases']:
        assert case['obligation']['id'].startswith('sail.rv32i.')
        assert len(case['mutants'])==2 and 'rvw_test_fail' in Path(case['source']).read_text()
    assert any(m['detected'] for case in result['cases'] for m in case['mutants'])


def test_short_reference_stream_earns_no_expected_result(tmp_path,monkeypatch):
    fixture_oracle(monkeypatch);monkeypatch.setattr(s,'exchange',lambda *a,**kw:[])
    result=s.generate('model',tmp_path/'out','localhost:1234',[5,6,7,8])
    assert result['status']=='inconclusive' and 'expected' not in result['cases'][0]
    assert not list((tmp_path/'out').glob('*.S'))


def test_unsupported_rules_and_bad_resources_refuse_before_oracle(tmp_path):
    with pytest.raises(ValueError,match='only'):
        s.generate('unused',tmp_path/'out','localhost:1234',[5,6,7,8],instructions=['mul'])
    with pytest.raises(ValueError,match='four distinct'):
        s.generate('unused',tmp_path/'out','localhost:1234',[5,6,7,7])
    assert not (tmp_path/'out').exists()


def test_changed_rule_fails_pin_before_network(tmp_path):
    rule=tmp_path/'model/extensions/I/base_insts.sail';rule.parent.mkdir(parents=True);rule.write_text('changed')
    with pytest.raises(ValueError,match='pinned model'):
        s.generate(tmp_path,tmp_path/'out','localhost:1234',[5,6,7,8])
    assert not (tmp_path/'out').exists()


def test_cli_and_mcp_api_reject_same_changed_source(tmp_path):
    import subprocess,sys,json
    rule=tmp_path/'model/extensions/I/base_insts.sail';rule.parent.mkdir(parents=True);rule.write_text('changed')
    ran=subprocess.run([sys.executable,'-m','rvw','regress','sail-tests','--model',str(tmp_path),
        '--work-dir',str(tmp_path/'out'),'--sail-endpoint','localhost:1234','--registers','5,6,7,8','--json'],
        capture_output=True,text=True)
    assert ran.returncode==2
    with pytest.raises(ValueError) as error:
        s.execute_json(model=tmp_path,work_dir=tmp_path/'out',sail_endpoint='localhost:1234',registers=[5,6,7,8])
    assert json.loads(ran.stdout)['message']==str(error.value)
