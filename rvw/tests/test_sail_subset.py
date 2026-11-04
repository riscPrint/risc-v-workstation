from pathlib import Path
import os
import pytest
from rvw.formal.sail_subset import slice_source, generate, INSTRUCTIONS, property_trace, MODEL_COMMIT, RULE_HASH


def test_refuse_changed_rules(tmp_path):
    rule=tmp_path/'model/extensions/I/base_insts.sail'
    rule.parent.mkdir(parents=True)
    rule.write_text('ADD => a - b')
    with pytest.raises(ValueError,match='hash'):
        slice_source(tmp_path,'add')


def test_pinned_slice():
    model=os.environ.get('SAIL_RISCV_SOURCE')
    if not model: pytest.skip('pinned Sail model source required')
    assert 'a + b' in slice_source(model,'add')
    assert 'a - b' in slice_source(model,'sub')
    assert 'a + immext' in slice_source(model,'addi')
    assert 'sign_extend(imm)' in slice_source(model,'addi')


def test_native_generation(tmp_path):
    model=os.environ.get('SAIL_RISCV_SOURCE')
    compiler=os.environ.get('SAIL_COMPILER')
    upstream=os.environ.get('RISCV_FORMAL')
    if not all((model,compiler,upstream)):
        pytest.skip('native Sail compiler, pinned source and riscv-formal required')
    result=generate(model,compiler,upstream,tmp_path/'generated')
    assert result['subset']==list(INSTRUCTIONS)
    assert result['implementation_options']['xlen'] == 32
    assert result['implementation_options']['nret'] == 1
    for insn in INSTRUCTIONS:
        text=(tmp_path/'generated'/f'insn_{insn}.v').read_text()
        assert 'module sail_'+insn in text
        assert 'sail_model' in text
        trace = result['files'][insn]['property_trace']
        assert trace == property_trace(model, insn)
        assert trace['id'] == f'sail.rv32i.{insn}.result'

@pytest.mark.parametrize('insn',INSTRUCTIONS)
@pytest.mark.parametrize('wrong',[False,True])
def test_native_independent_model(tmp_path,insn,wrong):
    """Compare Sail output against upstream arithmetic for all operands and encodings."""
    import shutil
    from rvw.common.proc import run_group
    root=os.environ.get('RISCV_FORMAL')
    models=os.environ.get('SAIL_MODELS')
    if not root or not models or not shutil.which('sby') or not shutil.which('bitwuzla'):
        pytest.skip('native tools and generated models required')
    gold=(Path(root)/'insns'/f'insn_{insn}.v').read_text().replace(f'module rvfi_insn_{insn}', 'module gold')
    gate=(Path(models)/f'insn_{insn}.v').read_text().replace(f'module rvfi_insn_{insn}', 'module gate')
    if wrong:
        # Change the generated arithmetic, not its oracle or assertion.
        needle='a_0 - b_0' if insn=='sub' else 'a_0 + '
        assert needle in gate
        gate=gate.replace(needle,'a_0 + b_0' if insn=='sub' else 'a_0 - ',1)
    (tmp_path/'models.sv').write_text('`define RISCV_FORMAL_XLEN 32\n`define RISCV_FORMAL_ILEN 32\n'+gold+'\n'+gate)
    inputs={'valid':1,'insn':32,'pc_rdata':32,'rs1_rdata':32,'rs2_rdata':32,'mem_rdata':32}
    outputs={'valid':1,'trap':1,'rs1_addr':5,'rs2_addr':5,'rd_addr':5,'rd_wdata':32,'pc_wdata':32,'mem_addr':32,'mem_rmask':4,'mem_wmask':4,'mem_wdata':32}
    top='module top;\n'+''.join(f'(* anyconst *) reg [{w-1}:0] {n};\n' for n,w in inputs.items())
    for side in ('gold','gate'):
        top+=''.join(f'wire [{w-1}:0] {side}_{n};\n' for n,w in outputs.items())
        connections=[f'.rvfi_{n}({n})' for n in inputs]+[f'.spec_{n}({side}_{n})' for n in outputs]
        top+=f'{side} {side}_inst('+','.join(connections)+');\n'
    top+='always @* begin\n'+''.join(f'assert(gold_{n} == gate_{n});\n' for n in outputs)+'end\nendmodule\n'
    (tmp_path/'top.sv').write_text(top)
    (tmp_path/'test.sby').write_text('[options]\nmode bmc\ndepth 1\n[engines]\nsmtbmc bitwuzla\n[script]\nread -sv models.sv top.sv\nprep -top top\n[files]\nmodels.sv\ntop.sv\n')
    with (tmp_path/'run.log').open('w') as log:
        result=run_group(['sby','-f','test.sby'],cwd=tmp_path,timeout=30,stdout=log,stderr=log)
    assert not result.timed_out
    assert (tmp_path/'test/status').read_text().split()[0]==('FAIL' if wrong else 'PASS')


@pytest.mark.parametrize('xlen,nret', [(64, 1), (32, 2), (True, 1), (32, True)])
def test_refuse_unsupported_options(tmp_path, xlen, nret):
    with pytest.raises(ValueError, match='XLEN=32 and NRET=1'):
        generate(tmp_path, 'missing', tmp_path, tmp_path/'out', xlen=xlen, nret=nret)
    assert not (tmp_path/'out').exists()


@pytest.mark.parametrize('instruction,line', [('add', 239), ('sub', 247), ('addi', 161)])
def test_trace_rule(instruction, line):
    model = os.environ.get('SAIL_RISCV_SOURCE')
    if not model:
        pytest.skip('pinned Sail model source required')
    trace = property_trace(model, instruction)
    assert trace['sail']['line'] == line
    assert trace['sail']['commit'] == MODEL_COMMIT
    assert trace['sail']['sha256'] == RULE_HASH
    assert trace['scope'] == 'arithmetic expression'
    assert 'decode' in trace['upstream_shell']
    assert 'full architectural transition' in trace['excluded']


def test_trace_rejects_changed_rules(tmp_path):
    rule = tmp_path/'model/extensions/I/base_insts.sail'
    rule.parent.mkdir(parents=True)
    rule.write_text('    ADD  => X(rs1) - X(rs2),')
    with pytest.raises(ValueError, match='hash'):
        property_trace(tmp_path, 'add')
