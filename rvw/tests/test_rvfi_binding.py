"""Core-owned wrapper generation tests."""
import json
from pathlib import Path
import tomllib

import pytest

from rvw.formal.riscv import FIELDS
from rvw.formal.rvfi_binding import generate, wrapper
from rvw.common.project import load_project


def binding(tmp_path, nret=1):
    root = tmp_path / 'upstream'
    (root / 'checks').mkdir(parents=True)
    (root / 'insns').mkdir()
    rtl = tmp_path / 'dut.sv'
    rtl.write_text('module Unit; endmodule')
    return dict(schema='rvw.rvfi-binding/1', name='example', top='Unit', clock='clk', reset='rst',
                inputs={'bus_data': 32, 'bus_ready': 1}, outputs={'bus_address': 32},
                ports={f: 'trace_' + f for f in FIELDS}, root='upstream', verilog=['dut.sv'],
                isa='rv32i', nret=nret, depth=10, solver='yices', checks=['insn_add_ch0', 'cover'])


def test_generate_project(tmp_path):
    plan = binding(tmp_path)
    manifest = tmp_path / 'binding.json'
    manifest.write_text(json.dumps(plan))
    result = generate(manifest, tmp_path / 'generated')
    cfg = load_project(result['project']).sections['riscv_formal']
    assert cfg['nret'] == 1
    assert cfg['ports'] == plan['ports']
    assert cfg['verilog'] == [tmp_path / 'dut.sv']
    text = Path(result['wrapper']).read_text()
    assert '.clk(clock)' in text and '.rst(reset)' in text
    assert '(* anyseq *) reg [31:0] bound_inputs_0;' in text
    assert '@RVFI_CONNECTIONS@' in text
    assert 'assume(' not in text
    assert result['status'] == 'generated'
    with pytest.raises(FileExistsError):
        generate(manifest, tmp_path / 'generated')


@pytest.mark.parametrize('change', [
    lambda p: p.update(clock='rst'),
    lambda p: p['inputs'].update(trace_valid=1),
    lambda p: p['outputs'].update(bus_ready=1),
    lambda p: p['inputs'].update(bus_data=0),
    lambda p: p['inputs'].update(bus_data=True),
    lambda p: p['ports'].pop('valid'),
    lambda p: p.update(top='Unit; bad'),
])
def test_reject_bad_bindings(tmp_path, change):
    plan = binding(tmp_path)
    change(plan)
    with pytest.raises(ValueError):
        wrapper(plan)


def test_multichannel_config(tmp_path):
    from rvw.formal.riscv import prepare, validate
    plan = binding(tmp_path, 2)
    plan['checks'] = ['insn_add_ch0', 'insn_add_ch1', 'cover']
    manifest = tmp_path / 'binding.json'
    manifest.write_text(json.dumps(plan))
    result = generate(manifest, tmp_path / 'generated')
    cfg = load_project(result['project']).sections['riscv_formal']
    core, _ = prepare(cfg, tmp_path / 'run')
    text = (core / 'checks.cfg').read_text()
    assert 'nret 2' in text
    assert 'channel[0].cnt_insns' in text and 'channel[1].cnt_insns' in text
    cfg['checks'] = ['insn_add_ch2', 'cover']
    with pytest.raises(ValueError, match='channel exceeds'):
        validate(cfg)


@pytest.mark.parametrize('wrong,inactive', [(False, False), (True, False), (False, True)])
def test_native_generated_dual_retirement(tmp_path, wrong, inactive):
    import os
    import shutil
    from rvw.formal.riscv import run
    root = os.environ.get('RISCV_FORMAL')
    if not root or any(not shutil.which(t) for t in ('sby', 'yosys', 'yices-smt2')):
        pytest.skip('native riscv-formal, Yosys, SBY and Yices required')
    plan = binding(tmp_path, 2)
    plan.update(root=root, inputs={}, outputs={}, depth=6, checks=['insn_add_ch0', 'insn_add_ch1', 'cover'])
    widths = dict.fromkeys(FIELDS, 32)
    widths.update(valid=1, order=64, trap=1, halt=1, intr=1, mode=2, ixl=2,
                  rs1_addr=5, rs2_addr=5, rd_addr=5, mem_rmask=4, mem_wmask=4)
    decls = ','.join(f'output [{widths[f]*2-1}:0] trace_{f}' for f in FIELDS)
    values = dict.fromkeys(FIELDS, "0")
    values.update(valid='!rst', order='count', insn="32'h002081b3", mode='3', ixl='1',
                  rs1_addr='1', rs2_addr='2', rd_addr='3', rs1_rdata='a', rs2_rdata='b',
                  rd_wdata='a + b', pc_rdata='pc', pc_wdata='pc + 4')
    lines = [f'module Unit(input clk,rst,{decls});',
             '(* anyseq *) reg [31:0] a,b;',
             'reg [63:0] count = 0; wire [31:0] pc = 4096 + count * 4;',
             'always @(posedge clk) if(rst) count <= 0; else count <= count + 2;']
    for lane in range(2):
        for field in FIELDS:
            value = values[field]
            if field == 'valid' and lane and inactive:
                value = '0'
            if field == 'order' and lane:
                value = 'count + 1'
            if field == 'rd_wdata' and lane and wrong:
                value = '(a + b) ^ 1'
            lines.append(f'assign trace_{field}[{lane * widths[field]} +: {widths[field]}] = {value};')
    (tmp_path / 'dut.sv').write_text('\n'.join(lines) + '\nendmodule\n')
    manifest = tmp_path / 'binding.json'
    manifest.write_text(json.dumps(plan))
    result = generate(manifest, tmp_path / 'generated')
    cfg = load_project(result['project']).sections['riscv_formal']
    verdict = run(cfg, tmp_path / 'proof', 10, 'independent-add-fixture')
    report = json.loads((tmp_path / 'proof' / 'results.json').read_text())
    statuses = {r['id']: r['status'] for r in report['tests']}
    assert statuses['insn_add_ch0'] == 'pass'
    assert statuses['insn_add_ch1'] == ('error' if inactive else 'fail' if wrong else 'pass')
    assert statuses['cover'] == ('error' if inactive else 'pass')
    assert verdict.tests == ('incomplete' if inactive else 'fail' if wrong else 'pass')
    assert verdict.verdict == ('reject' if wrong else 'inconclusive')


def test_cli_and_mcp_generation(tmp_path):
    from rvw.cli import main
    from rvw.formal.mcp_tools import _rvfi_generate
    plan = binding(tmp_path)
    manifest = tmp_path / 'binding.json'
    manifest.write_text(json.dumps(plan))
    assert main(['formal', 'rvfi-generate', str(manifest), '--out', str(tmp_path / 'cli')]) == 0
    class Job:
        def run(self, argv):
            assert argv[4] == 'rvfi-generate'
            assert argv[-1] == str(manifest)
            return main(argv[3:])
    assert _rvfi_generate(Job(), manifest=str(manifest), out=str(tmp_path / 'mcp'))['status'] == 'generated'
