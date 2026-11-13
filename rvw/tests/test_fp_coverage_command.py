"""FP reports require bound DUT execution and share CLI/MCP calculations."""
import argparse
import json
from pathlib import Path
import pytest
from rvw.cosim.trace import record
from rvw.cov.commands.fp import execute_json,run

pytestmark=pytest.mark.fast


def trace(tmp_path,config='dut',schema='rvw.rvfi/2'):
    header=dict(schema=schema,xlen=32,isa='rv32imafc',core='fixture',config=config,elf='program.elf')
    if schema.endswith('/2'):header['capabilities']=['state']
    base=dict(pc=0,pc_next=4,insn=0x2087,mode=3,rd=0,rd_wdata=0,before=[0]*32,
              mem_addr=0,mem_rmask=0,mem_wmask=0,mem_rdata=0,mem_wdata=0,trap=False,mem_fault=False)
    rows=[]
    for order,insn,fd,value in [(0,0x13,None,0),(1,0x2087,1,0xffffffff3f800000),
                              (2,(1<<15)|(1<<20)|0x53,0,0xffffffff40000000)]:
        row=record(dict(base,insn=insn,pc=order*4,pc_next=(order+1)*4),order,xlen=32)
        if schema.endswith('/2'):row.update(fd_valid=fd is not None,fd=fd or 0,fd_wdata=hex(value),fflags='0x0',fcsr='0x0')
        rows.append(row)
    rows.append(dict(event='end',cycle=3,status='pass'))
    path=tmp_path/'rvfi.jsonl'
    path.write_text('\n'.join(json.dumps(row) for row in [header,*rows])+'\n')
    return path


def test_missing_c1_gets_no_bins(tmp_path):
    with pytest.raises(ValueError,match='conclusive C1 pass'):
        execute_json([str(trace(tmp_path))],32)


@pytest.mark.parametrize('config,schema,error',[('reference','rvw.rvfi/2','reference-only'),
                                               ('dut','rvw.rvfi/1','C2/2 state')])
def test_reference_or_v1_gets_no_bins(tmp_path,config,schema,error):
    with pytest.raises(ValueError,match=error):
        execute_json([str(trace(tmp_path,config,schema))],32)


def test_command_and_mcp_use_the_same_qualified_calculation(monkeypatch,tmp_path,capsys):
    from rvw.cov import functional
    monkeypatch.setattr(functional,'qualification',lambda item:{'qualified':True})
    path=trace(tmp_path)
    result=execute_json([str(path)],32)
    output=tmp_path/'coverage.json'
    assert run(argparse.Namespace(traces=[str(path)],width=32,out=output,json=True))==0
    cli=json.loads(capsys.readouterr().out)
    assert json.loads(output.read_text())==cli
    for key in ('hits','holes','observed','hit_operand_class_bins','qualification_policy'):
        assert cli[key]==result[key]
    assert result['hit_operand_class_bins']==3
    assert result['unknown_operands_or_rm']==0
    with pytest.raises(ValueError,match='overwrite'):
        execute_json([str(path)],32,path)
