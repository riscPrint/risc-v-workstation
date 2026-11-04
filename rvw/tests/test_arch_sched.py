"""Scheduling fragments and fail-closed retirement-span reports."""
import copy
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from rvw.arch import sched

ROOT = Path(__file__).resolve().parents[2]


def desc():
    return json.loads((ROOT / 'examples/vexriscv/sched/rv32im.json').read_text())


def test_generation(tmp_path):
    d = desc(); d['issue_width'] = 2; d['resources']['MUL'] = 2
    d['classes'][1]['occupancy'] = 4
    td, md = sched.render(d)
    assert 'IssueWidth = 2' in td
    assert 'Latency = 3' in td
    assert 'ReleaseAtCycles = [4]' in td
    assert 'CompleteModel = 0' in td
    assert 'Vexriscv_MUL0*4' in md and 'Vexriscv_MUL1*4' in md
    assert '(Vexriscv_issue0|Vexriscv_issue1)+' in md
    assert '^ADD$' in td


@pytest.mark.parametrize('field,value', [('issue_width', True), ('issue_width', 0),
    ('buffer_size', -1), ('entry', 3), ('isa', 'rv32gc'), ('mca_cpu', 'bad"'),
    ('resources', {}), ('classes', [])])
def test_invalid_description(tmp_path, field, value):
    d = desc(); d[field] = value
    path = tmp_path / 'd.json'; path.write_text(json.dumps(d))
    with pytest.raises(ValueError):
        sched.description(path)


@pytest.mark.parametrize('change', ['unknown', 'duplicate', 'overlap', 'resource', 'encoding', 'occupancy'])
def test_invalid_class(tmp_path, change):
    d = desc(); c = d['classes'][1]
    if change == 'unknown': c['unknown'] = 1
    if change == 'duplicate': c['name'] = 'IntALU'
    if change == 'overlap': c['llvm_opcodes'] = ['ADD']
    if change == 'resource': c['resource'] = 'missing'
    if change == 'encoding': c['encoding'] = 0x33
    if change == 'occupancy': c['occupancy'] = 0
    path = tmp_path / 'd.json'; path.write_text(json.dumps(d))
    with pytest.raises(ValueError): sched.description(path)


def fixture_trace():
    d = desc(); words = sched.kernel(d['classes'][0], 16, 'dependent')[1]
    raw = dict(schema='rvw.run/1', core='test', config='rv32im', elf='/test', elf_sha256='a'*64,
               rtl_sha256='b'*64, seed=1, max_cycles=100000, mem_latency=0, status='pass',
               fail_code=None, message=None, cycles=100, instret=16, wall_s=0.1,
               source={}, tools={}, artifacts={})
    header = dict(schema='rvw.rvfi/1', core='test', config='rv32im')
    records = [dict(order=i, cycle=10+i*2, pc=hex(4096+i*4), insn=hex(word), trap=False)
               for i, word in enumerate(words)]
    records.append(dict(event='end', cycle=100, status='pass'))
    return raw, header, records, words


def test_trace_span():
    raw, header, records, words = fixture_trace()
    assert sched.trace_span(raw, header, records, 4096, words, 'rv32im', 'a'*64) == 30


@pytest.mark.parametrize('change', ['missing_end', 'end_fail', 'trap', 'missing_roi', 'word',
    'cycle', 'order', 'hash', 'config', 'seed', 'latency', 'status', 'header', 'inconclusive'])
def test_trace_refuses(change):
    raw, header, records, words = fixture_trace()
    if change == 'missing_end': records.pop()
    if change == 'end_fail': records[-1]['status'] = 'timeout'
    if change == 'trap': records[2]['trap'] = True
    if change == 'missing_roi': records[2]['pc'] = '0x0'
    if change == 'word': records[2]['insn'] = '0x0'
    if change == 'cycle': records[2]['cycle'] = 0
    if change == 'order': records[2]['order'] = 7
    if change == 'hash': raw['elf_sha256'] = 'c'*64
    if change == 'config': raw['config'] = 'wrong'
    if change == 'seed': raw['seed'] = 2
    if change == 'latency': raw['mem_latency'] = None
    if change == 'status': raw['status'] = 'timeout'
    if change == 'header': header['core'] = 'wrong'
    if change == 'inconclusive': raw['inconclusive'] = 'unknown'
    with pytest.raises(ValueError):
        sched.trace_span(raw, header, records, 4096, words, 'rv32im', 'a'*64)


def test_kernel_dependencies():
    c = desc()['classes'][0]
    lines, words = sched.kernel(c, 16, 'independent')
    assert len(set(lines)) == 8
    assert all((w >> 7 & 31) == (w >> 15 & 31) for w in words)
    assert len(set(sched.kernel(c, 16, 'dependent')[1])) == 1


def test_known_slope_error():
    report = sched.slope_report([dict(rtl_cycles=20, mca_cycles=15),
                                 dict(rtl_cycles=84, mca_cycles=47)], 32)
    assert report['error_percent'] == -50
    assert report['rtl_cycles_per_instruction'] == 2


def test_nonpositive_slope():
    with pytest.raises(ValueError):
        sched.slope_report([dict(rtl_cycles=2, mca_cycles=2)]*2, 16)


def test_native_tablegen(tmp_path):
    tool = shutil.which('llvm-tblgen')
    include = Path('/opt/homebrew/opt/llvm/include')
    if not tool or not include.exists(): pytest.skip('native LLVM headers and tblgen absent')
    td, _ = sched.render(desc())
    path = tmp_path / 'model.td'; path.write_text(td)
    result = subprocess.run([tool, '-I', str(include), str(path), '-o', str(tmp_path/'out')],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr


def test_cli_json(tmp_path, capsys):
    from rvw.cli import main
    assert main(['arch', 'sched-generate', str(ROOT / 'examples/vexriscv/sched/rv32im.json'),
                 '--out', str(tmp_path/'generated'), '--json']) == 0
    assert json.loads(capsys.readouterr().out)['status'] == 'reported'
    assert main(['arch', 'sched-generate', '/missing', '--out', str(tmp_path/'other'), '--json']) == 2
    assert 'error' in json.loads(capsys.readouterr().out)


def test_native_elf_entry(tmp_path):
    tool = shutil.which('riscv64-unknown-elf-gcc')
    if not tool: pytest.skip('native RISC-V GCC absent')
    source, _ = sched.assembly(desc()['classes'][0], 16, 'dependent')
    (tmp_path/'test.S').write_text(source)
    (tmp_path/'link.ld').write_text('ENTRY(_start)\nSECTIONS { . = 0x80000000; '
        '.text : { *(.text.init) *(.text*) } . = ALIGN(8); .tohost : { *(.tohost) } }\n')
    r = subprocess.run([tool, '-nostdlib', '-nostartfiles', '-march=rv32im', '-mabi=ilp32',
        '-Wl,--no-relax', '-Wl,-T,'+str(tmp_path/'link.ld'), '-o', str(tmp_path/'test.elf'),
        str(tmp_path/'test.S')], capture_output=True, timeout=30)
    assert r.returncode == 0, r.stderr
    data = (tmp_path/'test.elf').read_bytes()
    assert int.from_bytes(data[24:28], 'little') == 0x80000000
