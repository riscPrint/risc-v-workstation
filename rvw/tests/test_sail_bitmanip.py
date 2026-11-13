"""Independent bitvector oracles for the generated binary instruction slice."""
import os
from pathlib import Path
import shutil
import pytest

from rvw.formal.sail_bitmanip import extract

# Encodings and reference operations are independent of the source extractor.
ORACLES = {
 'sh1add': (0x20002033, '(a << 1) + b'),
 'sh2add': (0x20004033, '(a << 2) + b'),
 'sh3add': (0x20006033, '(a << 3) + b'),
 'andn': (0x40007033, 'a & ~b'), 'orn': (0x40006033, 'a | ~b'),
 'xnor': (0x40004033, '~(a ^ b)'),
 'min': (0x0a004033, '$signed(a) < $signed(b) ? a : b'),
 'max': (0x0a006033, '$signed(a) > $signed(b) ? a : b'),
 'minu': (0x0a005033, 'a < b ? a : b'), 'maxu': (0x0a007033, 'a > b ? a : b'),
 'rol': (0x60001033, '(a << b[4:0]) | (a >> (32 - b[4:0]))'),
 'ror': (0x60005033, '(a >> b[4:0]) | (a << (32 - b[4:0]))'),
 'bclr': (0x48001033, "a & ~(32'b1 << b[4:0])"),
 'bext': (0x48005033, '(a >> b[4:0]) & 1'),
 'binv': (0x68001033, "a ^ (32'b1 << b[4:0])"),
 'bset': (0x28001033, "a | (32'b1 << b[4:0])"),
 'clmul': (0x0a001033, 'product[31:0]'),
 'clmulh': (0x0a003033, 'product[63:32]'),
 'clmulr': (0x0a002033, 'product[62:31]'),
}


def test_extract_pinned_rules(tmp_path):
    source = os.environ.get('SAIL_BITMANIP_SOURCE')
    if not source:
        pytest.skip('pinned Sail bitmanip source required')
    rules, sources = extract(Path(source))
    assert set(rules) == set(ORACLES)
    assert {name: row['match'] for name,row in rules.items()} == {name: row[0] for name,row in ORACLES.items()}
    assert sources['arithmetic']['sha256']
    for row in sources.values():
        dest = tmp_path / row['path']
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(Path(source) / row['path'], dest)
    (tmp_path / 'model/extensions/B/zbb_insts.sail').write_text('changed')
    with pytest.raises(ValueError, match='pinned'):
        extract(tmp_path)


@pytest.mark.parametrize('name', ORACLES)
@pytest.mark.parametrize('mutant', [False, True])
def test_native_independent_result(tmp_path, name, mutant):
    models = os.environ.get('SAIL_BITMANIP_MODELS')
    if not models or any(not shutil.which(tool) for tool in ('yosys', 'sby', 'yices-smt2')):
        pytest.skip('generated Sail bitmanip models and native tools required')
    from rvw.formal.apps import flow
    opcode, expected = ORACLES[name]
    text = (Path(models) / f'insn_{name}.v').read_text()
    if mutant:
        text = text.replace('spec_rd_addr ? result : 0', 'spec_rd_addr ? (result ^ 1) : 0')
    model = tmp_path / 'model.v'
    model.write_text('`define RISCV_FORMAL_XLEN 32\n`define RISCV_FORMAL_ILEN 32\n' + text)
    wrapper = tmp_path / 'oracle.sv'
    inputs = 'input [31:0] a,b,pc,insn'
    basis = ''
    if name.startswith('clmul'):
        inputs = 'input [31:0] a,pc,insn,input [4:0] basis_index,input basis_zero'
        basis = "wire [31:0] b = basis_zero ? 32'b0 : (32'b1 << basis_index);"
    wrapper.write_text(f'''module oracle(input clk,reset,{inputs});
{basis}
wire valid,trap; wire [4:0] rs1,rs2,rd;
wire [31:0] result,nextpc,addr,data; wire [3:0] rmask,wmask;
reg [63:0] product; integer i,j;
always @* begin
 product = 0;
 for(i=0;i<32;i=i+1) for(j=0;j<32;j=j+1) product[i+j] = product[i+j] ^ (a[i] & b[j]);
end
rvfi_insn_{name} model(.rvfi_valid(1'b1),.rvfi_insn(insn),.rvfi_pc_rdata(pc),
.rvfi_rs1_rdata(a),.rvfi_rs2_rdata(b),.rvfi_mem_rdata(32'b0),
.spec_valid(valid),.spec_trap(trap),.spec_rs1_addr(rs1),.spec_rs2_addr(rs2),.spec_rd_addr(rd),
.spec_rd_wdata(result),.spec_pc_wdata(nextpc),.spec_mem_addr(addr),.spec_mem_wdata(data),
.spec_mem_rmask(rmask),.spec_mem_wmask(wmask));
wire [31:0] expected = {expected};
always @(posedge clk) if(!reset) begin
 assert(valid == ((insn & 32'hfe00707f) == 32'h{opcode:08x}));
 if(valid) begin
 assert(result == (insn[11:7] == 0 ? 32'b0 : expected));
 assert(rs1 == insn[19:15] && rs2 == insn[24:20] && rd == insn[11:7]);
 assert(nextpc == pc + 32'd4);
 assert(!trap && addr == 0 && data == 0 && rmask == 0 && wmask == 0);
 end
end
endmodule
''')
    engine = 'abc:bmc3' if name.startswith('clmul') else 'smtbmc:yices'
    result = flow([model,wrapper], 'oracle','clk','reset',tmp_path/'proof',4,engine,60)
    assert result['status'] == ('fail' if mutant else 'pass'), result
