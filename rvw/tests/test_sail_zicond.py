"""Independent Zicond equations and deliberate shell faults."""
import os
from pathlib import Path
import shutil

import pytest

from rvw.formal.sail_zicond import extract, generate


def test_pinned_rules():
    source = os.environ.get('SAIL_ZICOND_SOURCE')
    if not source:
        pytest.skip('pinned Sail source required')
    rules = extract(source)
    assert rules['czero_eqz']['match'] == 0x0e005033
    assert rules['czero_nez']['match'] == 0x0e007033
    assert rules['czero_eqz']['expression'] == 'if (b == 0x00000000) then 0x00000000 else a'


def test_wrong_source_refused(tmp_path):
    path = tmp_path / 'model/extensions/Zicond/zicond_insts.sail'
    path.parent.mkdir(parents=True)
    path.write_text('mutated semantics')
    with pytest.raises(ValueError, match='pinned'):
        extract(tmp_path)


@pytest.mark.parametrize('name,opcode,eq', [('czero_eqz',0x0e005033,'b == 0'),
                                           ('czero_nez',0x0e007033,'b != 0')])
@pytest.mark.parametrize('mutation', ['none', 'result', 'decode', 'pc'])
def test_native_independent_oracle(tmp_path, name, opcode, eq, mutation):
    models = os.environ.get('SAIL_ZICOND_MODELS')
    if not models or any(not shutil.which(t) for t in ('yosys','sby','yices-smt2')):
        pytest.skip('generated Sail Zicond models and native tools required')
    from rvw.formal.apps import flow
    source = (Path(models) / f'insn_{name}.v').read_text()
    if mutation == 'result':
        source = source.replace('spec_rd_addr ? result : 0', 'spec_rd_addr ? (result ^ 1) : 0')
    elif mutation == 'decode':
        source = source.replace(f"32'h{opcode:08x}", f"32'h{opcode ^ 0x1000:08x}")
    elif mutation == 'pc':
        source = source.replace('rvfi_pc_rdata + 4', 'rvfi_pc_rdata + 8')
    model = tmp_path / 'model.v'
    model.write_text('`define RISCV_FORMAL_XLEN 32\n`define RISCV_FORMAL_ILEN 32\n' + source)
    wrapper = tmp_path / 'oracle.sv'
    wrapper.write_text(f'''module oracle(input clk, reset, input [31:0] a,b,pc,insn);
wire valid,trap; wire [4:0] rs1,rs2,rd;
wire [31:0] result,nextpc,addr,data; wire [3:0] rmask,wmask;
rvfi_insn_{name} model(.rvfi_valid(1'b1),.rvfi_insn(insn),.rvfi_pc_rdata(pc),
.rvfi_rs1_rdata(a),.rvfi_rs2_rdata(b),.rvfi_mem_rdata(32'b0),
.spec_valid(valid),.spec_trap(trap),.spec_rs1_addr(rs1),.spec_rs2_addr(rs2),.spec_rd_addr(rd),
.spec_rd_wdata(result),.spec_pc_wdata(nextpc),.spec_mem_addr(addr),.spec_mem_wdata(data),
.spec_mem_rmask(rmask),.spec_mem_wmask(wmask));
always @(posedge clk) if (!reset) begin
 assert(valid == ((insn & 32'hfe00707f) == 32'h{opcode:08x}));
 if(valid) begin
 assert(rs1 == insn[19:15] && rs2 == insn[24:20] && rd == insn[11:7]);
 assert(result == (insn[11:7] == 0 ? 0 : ({eq}) ? 0 : a));
 assert(nextpc == pc + 32'd4);
 assert(!trap && addr == 0 && data == 0 && rmask == 0 && wmask == 0);
 end
end
endmodule
''')
    result = flow([model, wrapper], 'oracle', 'clk', 'reset', tmp_path / 'proof', 4, 'smtbmc:yices', 10)
    assert result['status'] == ('pass' if mutation == 'none' else 'fail')


def test_new_instruction_models_extend_private_isa_only(tmp_path):
    from rvw.formal.riscv import FIELDS, prepare
    upstream = tmp_path / 'upstream'
    (upstream / 'checks').mkdir(parents=True)
    (upstream / 'insns').mkdir()
    instruction_list = upstream / 'insns/isa_rv32i.txt'
    instruction_list.write_text('add\n')
    model = tmp_path / 'insn_czero_eqz.v'
    model.write_text('module rvfi_insn_czero_eqz; endmodule\n')
    wrapper = tmp_path / 'wrapper.in'
    wrapper.write_text('@RVFI_CONNECTIONS@')
    rtl = tmp_path / 'core.v'
    rtl.write_text('module core; endmodule\n')
    cfg = dict(root=str(upstream),wrapper=str(wrapper),verilog=[str(rtl)],isa='rv32i',nret=1,
               checks=['insn_czero_eqz_ch0','cover'],depth=6,solver='yices',
               ports={f:'rvfi_'+f for f in FIELDS},instruction_models={'czero_eqz':str(model)})
    core, identity = prepare(cfg, tmp_path / 'run')
    assert (core.parents[1] / 'insns/isa_rv32i.txt').read_text() == 'add\nczero_eqz\n'
    assert instruction_list.read_text() == 'add\n'
    assert identity['instruction_set_additions'] == ['czero_eqz']
    cfg['checks'] = ['insn_add_ch0','cover']
    with pytest.raises(ValueError, match='requested check'):
        prepare(cfg, tmp_path / 'unselected')


@pytest.mark.parametrize('wrong', [False, True])
def test_native_new_instruction_campaign(tmp_path, wrong):
    from rvw.formal.riscv import FIELDS, run
    root, models = os.environ.get('RISCV_FORMAL'), os.environ.get('SAIL_ZICOND_MODELS')
    if not root or not models or any(not shutil.which(t) for t in ('yosys','sby','yices-smt2')):
        pytest.skip('native riscv-formal and generated Zicond models required')
    widths = dict.fromkeys(FIELDS, 32)
    widths.update(valid=1, order=64, trap=1, halt=1, intr=1, mode=2, ixl=2,
                  rs1_addr=5, rs2_addr=5, rd_addr=5, mem_rmask=4, mem_wmask=4)
    declarations = ','.join(f'output [{widths[f]-1}:0] io_{f}' for f in FIELDS)
    values = dict.fromkeys(FIELDS, '0')
    values.update(valid='!reset',order='count',insn="nez ? 32'h0e20f1b3 : 32'h0e20d1b3",
                  mode='3',ixl='1',rs1_addr='1',rs2_addr='2',rd_addr='3',rs1_rdata='a',rs2_rdata='b',
                  rd_wdata='(nez ? (b == 0 ? a : 0) : (b == 0 ? 0 : a))' + (' ^ 1' if wrong else ''),
                  pc_rdata='4096 + count * 4',pc_wdata='4100 + count * 4')
    rtl = tmp_path / 'core.sv'
    rtl.write_text(f'module unit(input clock,reset,{declarations});\n'
                   '(* anyseq *) reg [31:0] a,b; (* anyseq *) reg nez;\n'
                   'reg [63:0] count = 0; always @(posedge clock) if(reset) count <= 0; else count <= count + 1;\n' +
                   '\n'.join(f'assign io_{f} = {values[f]};' for f in FIELDS) + '\nendmodule\n')
    wrapper = tmp_path / 'wrapper.in'
    wrapper.write_text('module rvfi_wrapper(input clock,reset,`RVFI_OUTPUTS);\n'
                       'unit dut(.clock(clock),.reset(reset),@RVFI_CONNECTIONS@);\nendmodule\n')
    cfg = dict(root=root, wrapper=str(wrapper), verilog=[str(rtl)], isa='rv32i', nret=1,
               checks=['insn_czero_eqz_ch0','insn_czero_nez_ch0','cover'], depth=6, solver='yices',
               ports={f:'io_'+f for f in FIELDS},
               instruction_models={n:str(Path(models) / f'insn_{n}.v') for n in ('czero_eqz','czero_nez')})
    verdict = run(cfg, tmp_path / 'campaign', 10, 'independent-zicond-fixture')
    assert verdict.tests == ('fail' if wrong else 'pass')
    assert verdict.verdict == ('reject' if wrong else 'inconclusive')
