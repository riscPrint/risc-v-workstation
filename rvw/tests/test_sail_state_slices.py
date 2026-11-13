"""Independent bit and control oracles for source-derived Sail state slices."""
import os
from pathlib import Path
import shutil

import pytest

from rvw.formal.sail_state_slices import HASHES, extract, shell

FP = {f'{op}_{suffix}': (width, op) for suffix, width in [('h',16),('s',32),('d',64)]
      for op in ('fsgnj','fsgnjn','fsgnjx')}
KINDS = list(FP) + [f'{op}_{kind}' for op in ('csrrw','csrrs','csrrc') for kind in ('write','access')] + ['mret_entry','sret_entry','wfi_entry']


@pytest.mark.fast
def test_named_instances_keep_typed_port_order():
    from rvw.formal.sail_zicond import named_instances
    text = '''module child(
input control_t mode,
input logic a,
output logic b
);
endmodule
module parent(
input logic x,
output logic y
);
child instance(CSRRW, (x | 1'b0), y);
endmodule'''
    result = named_instances(text)
    assert ".mode(CSRRW), .a((x | 1'b0)), .b(y)" in result
    assert named_instances(result) == result
    with pytest.raises(ValueError,match='port layout'):
        named_instances(text.replace("CSRRW, (x | 1'b0), y", 'x, y'))


@pytest.mark.fast
def test_shell_keeps_fp_zero_register_and_privilege_scope():
    fp = shell('example', dict(kind='fp_result',input_width=64,output_width=64,match=0x22000053,mask=0xfe00707f), 'sail_return_0')
    assert '[63:0]' in fp and 'rd_addr ?' not in fp
    assert "32'hfe00707f" in fp
    privilege = shell('mret_entry', dict(kind='privileged_entry',output_width=2), 'sail_return_1')
    assert 'a[2:0] == 5' in privilege and 'observed == expected' in privilege


@pytest.mark.fast
def test_command_and_mcp_registration():
    from rvw.cli import build_parser
    args = build_parser().parse_args(['formal','sail-state','--model','m','--compiler','c','--out','o'])
    assert args.model == 'm' and args.func.__module__.endswith('sail_state_slices')
    from rvw.formal.commands.sail_state import mcp_tools
    assert mcp_tools()[0].name == 'formal_sail_state'


def test_pinned_extraction_and_hash_drift(tmp_path):
    root = os.environ.get('SAIL_STATE_SOURCE')
    if not root:
        pytest.skip('pinned Sail state sources required')
    rules, sources = extract(root)
    assert set(rules) == set(KINDS)
    for name in FP:
        assert rules[name]['match'] & 0x7f == 0x53
    for path in sources:
        target = tmp_path / path
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(Path(root)/path,target)
    (tmp_path / next(iter(HASHES))).write_text('changed')
    with pytest.raises(ValueError,match='pinned'):
        extract(tmp_path)


def test_native_combined_type_namespaces(tmp_path):
    models = os.environ.get('SAIL_STATE_MODELS')
    if not models or not shutil.which('yosys'):
        pytest.skip('generated Sail state models and Yosys required')
    from rvw.common.proc import run_group
    files = []
    for name in KINDS:
        path = tmp_path / (name+'.v')
        path.write_text((Path(models)/f'insn_{name}.v').read_text())
        files.append(path.name)
    script = 'read_verilog -formal -sv '+' '.join(files)+'; hierarchy -check -top sail_check_fsgnj_d'
    with (tmp_path/'combined.log').open('w') as log:
        result = run_group(['yosys','-p',script],cwd=tmp_path,stdout=log,stderr=log,timeout=60)
    assert result.returncode == 0, (tmp_path/'combined.log').read_text()[-3000:]


def oracle(name):
    if name in FP:
        width, op = FP[name]
        sign = {'fsgnj':f'b[{width-1}]','fsgnjn':f'~b[{width-1}]','fsgnjx':f'a[{width-1}] ^ b[{width-1}]'}[op]
        return width, width, '{'+sign+f', a[{width-2}:0]'+'}'
    if name.endswith('_write'):
        return 32, 32, {'csrrw_write':'b','csrrs_write':'a | b','csrrc_write':'a & ~b'}[name]
    if name.endswith('_access'):
        expression = "{a[4:0] != 0, 1'b1}" if name.startswith('csrrw') else "{1'b1, b[4:0] != 0}"
        return 32, 2, expression
    if name == 'mret_entry':
        return 32,2,"a[2:0] != 3 ? 2'd1 : !b[0] ? 2'd3 : 2'd0"
    if name == 'sret_entry':
        return 32,2,"(a[2:0] == 0 || (a[2:0] == 1 && (!b[1] || a[3])) || (a[2:0] == 3 && !b[1])) ? 2'd1 : (a[2:0] == 4 || (a[2:0] == 5 && a[4])) ? 2'd2 : !b[0] ? 2'd3 : 2'd0"
    return 32,2,"a[2:0] == 0 ? (a[6] ? 2'd0 : 2'd1) : a[2:0] == 4 ? (a[5] ? 2'd1 : 2'd2) : a[2:0] == 5 && a[5] ? 2'd1 : 2'd0"


@pytest.mark.parametrize('name',KINDS)
@pytest.mark.parametrize('mutant',[False,True])
def test_native_independent_state_oracle(tmp_path,name,mutant):
    models = os.environ.get('SAIL_STATE_MODELS')
    if not models or any(not shutil.which(tool) for tool in ('yosys','sby','yices-smt2')):
        pytest.skip('generated Sail state models and native formal tools required')
    from rvw.formal.apps import flow
    width, output, expression = oracle(name)
    # Copy the compiled model; the oracle has no dependency on extraction rules.
    model = tmp_path/'model.v'
    model.write_text((Path(models)/f'insn_{name}.v').read_text())
    insn = 'insn'
    if name in FP:
        _, op = FP[name]
        fmt = {'h':2,'s':0,'d':1}[name[-1]]
        funct3 = {'fsgnj':0,'fsgnjn':1,'fsgnjx':2}[op]
        opcode = ((0x10 | fmt)<<25) | (funct3<<12) | 0x53
        insn = f"((insn & 32'h01ff8f80) | 32'h{opcode:08x})"
    wrapper = tmp_path/'oracle.sv'
    wrapper.write_text(f'''module oracle(input clk,reset,input [{width-1}:0] a,b,input [31:0] insn);
wire [{output-1}:0] observed = ({expression}) {'^ 1' if mutant else ''};
wire selected; wire [{output-1}:0] expected;
sail_check_{name} check(.clk(clk),.valid(!reset),.insn({insn}),.a(a),.b(b),
 .observed(observed),.check_valid(selected),.expected(expected));
endmodule
''')
    result = flow([model,wrapper],'oracle','clk','reset',tmp_path/'proof',4,'smtbmc:yices',60)
    assert result['status'] == ('fail' if mutant else 'pass'), result
