"""Architectural snapshot extraction and frame-effect mutations."""
import json
from pathlib import Path
import os
import shutil
import subprocess
import sys
import pytest
from rvw.formal.architectural_state import monitor,generate


@pytest.mark.parametrize('mutation', ['none', 'x0', 'frame', 'trap', 'unknown'])
def test_simulation_frame_exit_code(tmp_path, mutation):
    if not shutil.which('iverilog') or not shutil.which('vvp'):
        pytest.skip('Icarus required')
    text, widths, _ = monitor(32)
    (tmp_path/'monitor.sv').write_text(text)
    values = {name: "'0" for name in widths}
    values.update(retire="1'b1", rd="5'd1", regs_after="1024'd137438953472")
    # A write to x1 is legal. A write to x0 or x2 is not. Traps cannot write x1.
    if mutation == 'x0': values['regs_after'] = "1024'd1"
    if mutation == 'frame': values['regs_after'] = "1024'd18446744073709551616"
    if mutation == 'trap': values['trap'] = "1'b1"
    if mutation == 'unknown': values['regs_before'] = "'x"
    ports = ','.join(f'.{name}({value})' for name, value in values.items())
    (tmp_path/'tb.sv').write_text('module tb; reg clock=0; always #5 clock=~clock;\n'
        'rvw_state_monitor dut(.clock(clock),.reset(1\'b0),'+ports+');\n'
        'initial begin #12; $finish; end endmodule\n')
    subprocess.run(['iverilog','-g2012','-s','tb','-o','sim','monitor.sv','tb.sv'],
                   cwd=tmp_path,check=True,capture_output=True,timeout=10)
    result = subprocess.run(['vvp','sim'],cwd=tmp_path,capture_output=True,text=True,timeout=10)
    assert (result.returncode == 0) == (mutation == 'none'), result.stdout


@pytest.mark.parametrize('valid,retire', [(0,0), (0,1), (1,0), (1,"1'bx")])
def test_pico_simulation_validity_exit_code(tmp_path, valid, retire):
    if not shutil.which('iverilog') or not shutil.which('vvp'):
        pytest.skip('Icarus required')
    _, widths, outputs = monitor(32, halt=True)
    declarations = [f'wire [{w-1}:0] rvfi_{name} = {valid if name == "valid" else 0};'
                    for name,w in outputs.items()]
    declarations += [f'wire [{w-1}:0] state_{name} = {retire if name == "retire" else 0};'
                     for name,w in widths.items()]
    (tmp_path/'picorv32-observed.sv').write_text(
        'module picorv32(input clk,resetn);\n'+'\n'.join(declarations)+'\nendmodule\n')
    script = Path(__file__).resolve().parents[2]/'examples/picorv32/formal/compare.py'
    subprocess.run([sys.executable,str(script),'--capture',str(tmp_path)],check=True,
                   capture_output=True,timeout=10)
    (tmp_path/'validity.sv').write_text('module tb; reg clk=0; always #5 clk=~clk;\n'
        'picorv32 dut(.clk(clk),.resetn(1\'b1)); initial begin #12; $finish; end endmodule\n')
    subprocess.run(['iverilog','-g2012','-s','tb','-o','sim','miter.sv','monitor.sv','validity.sv'],
                   cwd=tmp_path,check=True,capture_output=True,timeout=10)
    result = subprocess.run(['vvp','sim'],cwd=tmp_path,capture_output=True,text=True,timeout=10)
    assert (result.returncode == 0) == (valid == retire), result.stdout
    if valid != retire:
        assert 'RVFI mismatch: valid' in result.stdout


def test_monitor_has_frame_and_memory_checks():
    text,widths,rvfi = monitor(32,['mstatus'])
    assert widths['regs_before'] == 1024 and rvfi['order'] == 64
    assert widths['csr_mstatus_before'] == 32
    assert 'index != rd' in text
    assert 'regs_before[rs1*32 +: 32]' in text
    assert 'assign rvfi_mem_rdata = mem_rdata;' in text
    assert 'assume' not in text


@pytest.mark.parametrize('mutant',[False,True])
def test_native_snapshot_frame(tmp_path,mutant):
    if any(not shutil.which(t) for t in ('sby','yosys','yices-smt2')):
        pytest.skip('Yosys, SBY and Yices required')
    from rvw.formal.apps import flow
    source,_,_ = monitor(32)
    model=tmp_path/'monitor.sv';model.write_text(source)
    wrapper=tmp_path/'oracle.sv'
    wrapper.write_text(f'''module oracle(input clk,reset,input [31:0] a,b);
wire [1023:0] before_state,after_state;
assign before_state = {{928'b0,b,a,32'b0}};
assign after_state = {{832'b0,32'd{1 if mutant else 0},32'b0,(a+b),b,a,32'b0}};
wire [31:0] result;
rvw_state_monitor mon(.clock(clk),.reset(reset),.retire(1'b1),.insn(32'h002081b3),
.pc_before(32'h1000),.pc_after(32'h1004),.regs_before(before_state),.regs_after(after_state),
.rs1(5'd1),.rs2(5'd2),.rd(5'd3),.trap(1'b0),.intr(1'b0),.mode(2'd3),
.mem_addr(32'b0),.mem_rmask(4'b0),.mem_wmask(4'b0),.mem_rdata(32'b0),.mem_wdata(32'b0),
.rvfi_rd_wdata(result));
always @(posedge clk) if(!reset) assert(result == a+b);
endmodule
''')
    result=flow([model,wrapper],'oracle','clk','reset',tmp_path/'proof',4,'smtbmc:yices',20)
    assert result['status'] == ('fail' if mutant else 'pass')


def test_native_expose_and_project(tmp_path):
    root=os.environ.get('RISCV_FORMAL')
    if not root or not shutil.which('yosys'):
        pytest.skip('Yosys and riscv-formal source required')
    _,widths,_=monitor(32)
    decl=', '.join(f'output [{w-1}:0] state_{key}' for key,w in widths.items())
    rtl=tmp_path/'unit.sv'
    rtl.write_text(f'module Unit(input clk,rst,{decl});\n'+
                   '\n'.join(f'assign state_{key} = 0;' for key in widths)+'\nendmodule\n')
    plan=dict(schema='rvw.architectural-state/1',xlen=32,top='Unit',clock='clk',reset='rst',
              verilog=['unit.sv'],signals={key:'state_'+key for key in widths},
              riscv_formal=dict(root=root,isa='rv32i',nret=1,checks=['insn_add_ch0','cover'],depth=6,solver='yices'))
    path=tmp_path/'state.json';path.write_text(json.dumps(plan))
    result=generate(path,tmp_path/'generated')
    from rvw.common.project import load_project
    cfg=load_project(result['project']).sections['riscv_formal']
    assert cfg['ports']['rd_wdata'] == 'rvfi_rd_wdata'
    assert len(cfg['verilog'])==2
    observed=(tmp_path/'generated/observed.v').read_text()
    assert 'rvw_state_regs_after' in observed
    assert 'setundef' not in (tmp_path/'generated/observe.ys').read_text()
    assert ' -cut' not in (tmp_path/'generated/observe.ys').read_text()
    assert result['status']=='generated'


@pytest.mark.parametrize('wrong',[False,True])
def test_native_no_rvfi_add(tmp_path,wrong):
    root=os.environ.get('RISCV_FORMAL')
    if not root or any(not shutil.which(t) for t in ('yosys','sby','yices-smt2')):
        pytest.skip('native riscv-formal tools required')
    _,widths,_=monitor(32)
    decl=', '.join(f'output [{w-1}:0] state_{key}' for key,w in widths.items())
    values={key:'0' for key in widths}
    values.update(retire='!rst',insn="32'h002081b3",pc_before="32'h1000",pc_after="32'h1004",
                  regs_before="{928'b0,b,a,32'b0}",regs_after="{896'b0,(a+b"+(' + 32\'d1' if wrong else '')+"),b,a,32'b0}",
                  rs1='1',rs2='2',rd='3',mode='3')
    (tmp_path/'unit.sv').write_text(f'module Unit(input clk,rst,input [31:0] a,b,{decl});\n'+
                  '\n'.join(f'assign state_{key} = {value};' for key,value in values.items())+'\nendmodule\n')
    plan=dict(schema='rvw.architectural-state/1',xlen=32,top='Unit',clock='clk',reset='rst',
              verilog=['unit.sv'],signals={key:'state_'+key for key in widths},
              riscv_formal=dict(root=root,isa='rv32i',nret=1,checks=['insn_add_ch0','cover'],depth=6,solver='yices'))
    path=tmp_path/'state.json';path.write_text(json.dumps(plan))
    generated=generate(path,tmp_path/'generated')
    from rvw.common.project import load_project
    from rvw.formal.riscv import run
    verdict=run(load_project(generated['project']).sections['riscv_formal'],tmp_path/'proof',20,'no-rvfi-add-fixture')
    rows={row['id']:row['status'] for row in json.loads((tmp_path/'proof/results.json').read_text())['tests']}
    assert rows['insn_add_ch0']==('fail' if wrong else 'pass')
    assert rows['cover']=='pass'
    assert verdict.verdict==('reject' if wrong else 'inconclusive')


def test_uncaptured_include_refused(tmp_path):
    _,widths,_=monitor(32)
    (tmp_path/'unit.sv').write_text('`include "outside.sv"\n')
    plan=dict(schema='rvw.architectural-state/1',xlen=32,top='Unit',clock='clk',reset='rst',
              verilog=['unit.sv'],signals={key:'state_'+key for key in widths})
    path=tmp_path/'state.json';path.write_text(json.dumps(plan))
    with pytest.raises(ValueError,match='includes are not captured'):
        generate(path,tmp_path/'generated')
