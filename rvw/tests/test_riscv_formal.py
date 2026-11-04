from pathlib import Path
import shutil
import pytest
from rvw.formal.riscv import FIELDS, validate, prepare, map_check, run
from rvw.common.proc import Result
from rvw.results.schema import load_results, load_verdict


@pytest.fixture
def cfg(tmp_path):
    root = tmp_path / 'source'
    for name in ('checks', 'insns'):
        (root / name).mkdir(parents=True)
        (root / name / 'a').write_text('checker')
    wrapper = tmp_path / 'wrapper.sv.in'
    wrapper.write_text('@RVFI_CONNECTIONS@')
    rtl = tmp_path / 'design.v'
    rtl.write_text('module dut; endmodule')
    return dict(root=str(root), wrapper=str(wrapper), verilog=[str(rtl)], isa='rv32i', nret=1,
                depth=20, solver='bitwuzla', checks=['insn_add_ch0', 'cover'],
                ports={f:'io_'+f for f in FIELDS})


@pytest.mark.parametrize('key,value', [('isa','rv64gc'), ('nret',2), ('nret',True), ('depth',0),
    ('solver','unknown'), ('checks',[]), ('checks',['insn_add_ch0']),
    ('checks',['cover_ch1']), ('checks',['cover','../../escape']),
    ('checks',['cover','cover']), ('ports',{}), ('defines',['x\ny'])])
def test_refuse(cfg,key,value):
    cfg[key]=value
    with pytest.raises(ValueError): validate(cfg)


def test_private_inputs(cfg,tmp_path):
    out=tmp_path/'out'
    core, identity=prepare(cfg,out)
    assert '.io_valid (rvfi_valid)' in (core/'wrapper.sv').read_text()
    assert (Path(cfg['wrapper'])).read_text() == '@RVFI_CONNECTIONS@'
    assert identity['checker_sha256']
    with pytest.raises(ValueError): prepare(cfg,out)


@pytest.mark.parametrize('name,token,rc,timeout,status',[
    ('insn_add_ch0','PASS',0,False,'pass'), ('insn_add_ch0','PASS',1,False,'error'),
    ('insn_add_ch0','FAIL',1,False,'fail'), ('insn_add_ch0','FAIL',0,False,'fail'), ('insn_add_ch0','',0,False,'error'),
    ('cover','FAIL',1,False,'error'), ('insn_add_ch0','PASS',0,True,'timeout')])
def test_mapping(name,token,rc,timeout,status):
    entry=map_check(name,token,rc,timeout)
    assert entry.status==status
    assert entry.conclusive == (status in ('pass','fail'))


def test_no_vacuous_accept(cfg,tmp_path,monkeypatch):
    def fake(argv,cwd,**kwargs):
        if argv[0]=='sby':
            name=Path(argv[-1]).stem
            dest=Path(cwd)/name
            dest.mkdir()
            (dest/'status').write_text('PASS' if name!='cover' else 'FAIL')
            return Result(0 if name!='cover' else 1)
        work=Path(cwd)/'checks';work.mkdir()
        for name in cfg['checks']: (work/f'{name}.sby').touch()
        return Result(0)
    monkeypatch.setattr('rvw.formal.riscv.run_group',fake)
    out=tmp_path/'out'
    verdict=run(cfg,out,1,'fixture')
    assert verdict.verdict=='inconclusive'
    assert verdict.tests=='incomplete'
    assert not load_results(out).tests[0].conclusive
    assert load_verdict(out).exit_code==3


def test_success_stays_bounded(cfg,tmp_path,monkeypatch):
    def fake(argv,cwd,**kwargs):
        if argv[0]=='sby':
            dest=Path(cwd)/Path(argv[-1]).stem;dest.mkdir()
            (dest/'status').write_text('PASS')
        else:
            work=Path(cwd)/'checks';work.mkdir()
            for name in cfg['checks']: (work/f'{name}.sby').touch()
        return Result(0)
    monkeypatch.setattr('rvw.formal.riscv.run_group',fake)
    verdict=run(cfg,tmp_path/'out',1,'fixture')
    assert verdict.tests=='pass'
    assert verdict.verdict=='inconclusive'


@pytest.mark.parametrize('wrong', [False, True])
def test_native_add_oracle(tmp_path, wrong):
    """Independent ADD equation, arbitrary operands, and a deliberately wrong unit."""
    import os
    root=os.environ.get('RISCV_FORMAL')
    if not root or not shutil.which('sby') or not shutil.which('bitwuzla'):
        pytest.skip('native riscv-formal checkout and solver required')
    widths={f:32 for f in FIELDS}
    widths.update(valid=1,order=64,trap=1,halt=1,intr=1,mode=2,ixl=2,
                  rs1_addr=5,rs2_addr=5,rd_addr=5,mem_rmask=4,mem_wmask=4)
    declarations=',\n'.join(f'output wire [{widths[f]-1}:0] io_{f}' for f in FIELDS)
    rtl=tmp_path/'unit.sv'
    values={f:"0" for f in FIELDS}
    values.update(valid='!reset',order='order_counter',insn="32'h002081b3",mode='3',ixl='1',
                  rs1_addr='1',rs2_addr='2',rd_addr='3',rs1_rdata='a',rs2_rdata='b',
                  rd_wdata='a + b' + (' + 1' if wrong else ''),
                  pc_rdata='32\'h80000000 + 4*order_counter',
                  pc_wdata='32\'h80000004 + 4*order_counter')
    rtl.write_text('module unit(input clock, reset,\n'+declarations+');\n'
        '(* anyseq *) reg [31:0] a,b;\nreg [63:0] order_counter = 0;\n'
        'always @(posedge clock) if(reset) order_counter <= 0; else order_counter <= order_counter+1;\n'+
        '\n'.join(f'assign io_{f} = {values[f]};' for f in FIELDS)+'\nendmodule\n')
    wrapper=tmp_path/'wrapper.in'
    wrapper.write_text('module rvfi_wrapper(input clock, reset, `RVFI_OUTPUTS);\n'
                       'unit uut(.clock(clock), .reset(reset), @RVFI_CONNECTIONS@);\nendmodule\n')
    cfg=dict(root=root,wrapper=str(wrapper),verilog=[str(rtl)],isa='rv32i',nret=1,depth=6,
             solver='bitwuzla',checks=['insn_add_ch0','cover'],ports={f:'io_'+f for f in FIELDS})
    verdict=run(cfg,tmp_path/'out',30,'add-fixture')
    assert verdict.tests == ('fail' if wrong else 'pass')
    assert verdict.verdict == ('reject' if wrong else 'inconclusive')


def test_missing_tool_is_inconclusive(cfg,tmp_path,monkeypatch):
    def missing(*args,**kwargs): raise FileNotFoundError('missing tool')
    monkeypatch.setattr('rvw.formal.riscv.run_group',missing)
    verdict=run(cfg,tmp_path/'out',1,'fixture')
    assert verdict.tests=='incomplete'
    assert all(not entry.conclusive for entry in load_results(tmp_path/'out').tests)


def test_project_paths_serialize(cfg,tmp_path,monkeypatch):
    cfg['root']=Path(cfg['root'])
    cfg['wrapper']=Path(cfg['wrapper'])
    cfg['verilog']=[Path(p) for p in cfg['verilog']]
    def missing(*args,**kwargs): raise FileNotFoundError('missing tool')
    monkeypatch.setattr('rvw.formal.riscv.run_group',missing)
    assert run(cfg,tmp_path/'out',1,'fixture').verdict=='inconclusive'
