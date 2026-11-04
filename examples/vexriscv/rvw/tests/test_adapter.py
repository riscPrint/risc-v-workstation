"""Real Verilator controls. Run with the environment from the example README."""
import json
import os
import sys
from pathlib import Path

from rvw.common.proc import run_group

EXAMPLE = Path(__file__).resolve().parents[1]
GCC = os.environ.get('RISCV_PREFIX', 'riscv64-unknown-elf-') + 'gcc'


def invoke(arguments, timeout=600):
    result = run_group([str(EXAMPLE / 'run.sh'), *map(str, arguments)], timeout=timeout,
                       env=dict(os.environ), capture=True, text=True)
    assert not result.timed_out, result.stderr
    return result


def compile_elf(directory, name, instructions, xlen=32):
    source = directory / (name + '.S')
    source.write_text('''.section .text
.globl _start
_start:
''' + instructions + '''
1: j 1b
.section .data
.balign 8
.globl tohost
tohost: .dword 0
''')
    elf = directory / name
    result = run_group([GCC, f'-march=rv{xlen}im_zicsr_zifencei', f'-mabi={"ilp32" if xlen == 32 else "lp64"}',
                        '-nostdlib', '-nostartfiles', '-T', str(EXAMPLE / 'programs/link.ld'),
                        '-Wl,--build-id=none', str(source), '-o', str(elf)],
                       capture=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return elf


def test_real_pass_fail_timeout_and_upper_store(tmp_path):
    programs = {
        'pass': ('la t0, tohost\nli t1, 1\nsw t1, 0(t0)', 'pass', None),
        'delayed': ('la t0, tohost\nli t1, 1\nsw t1, 0(t0)', 'pass', None),
        'random': ('la t0, tohost\nli t1, 1\nsw t1, 0(t0)', 'pass', None),
        'fail': ('la t0, tohost\nli t1, 7\nsw t1, 0(t0)', 'fail', 3),
        'upper': ('la t0, tohost\nli t1, 1\nsw t1, 4(t0)', 'fail', 1 << 31),
        'timeout': ('j _start', 'timeout', None),
    }
    manifest = tmp_path / 'jobs.jsonl'
    jobs = []
    for name, (instructions, _, _) in programs.items():
        elf = compile_elf(tmp_path, name, instructions)
        jobs.append(dict(elf=str(elf), out=str(tmp_path / (name + '-run')),
                         seed=1, max_cycles=1000, rvfi_trace=True,
                         mem_latency=5 if name == 'delayed' else None if name == 'random' else 0))
    manifest.write_text(''.join(json.dumps(job) + '\n' for job in jobs))
    result = invoke(['run-many', '--manifest', manifest, '--jobs', 2, '--json'])
    assert result.returncode == 1, result.stderr
    summary = json.loads(result.stdout)
    assert summary['counts'].get('pass') == 3
    for name, (_, status, code) in programs.items():
        run = json.loads((tmp_path / (name + '-run') / 'result.json').read_text())
        assert run['status'] == status, run
        assert run['fail_code'] == code, run
        assert not run.get('inconclusive'), run
        lines = [json.loads(line) for line in (tmp_path / (name + '-run') / 'rvfi.jsonl').read_text().splitlines()]
        assert lines[0]['xlen'] == 32
        assert lines[-1]['event'] == 'end' and lines[-1]['status'] == status
        assert all(a['cycle'] <= b['cycle'] for a, b in zip(lines[1:], lines[2:]))

    # A complete real RV32 trace must match. A changed writeback must not match.
    trace = tmp_path / 'pass-run' / 'rvfi.jsonl'
    command = [sys.executable, '-m', 'rvw', 'cosim', 'check', '--core', 'vexriscv',
               '--platform', str(EXAMPLE / 'platform.json'), '--elf', jobs[0]['elf'],
               '--trace', str(trace), '--json']
    comparison = run_group(command, capture=True, timeout=60)
    assert comparison.returncode == 0, comparison.stderr
    compared = json.loads(comparison.stdout)
    assert compared['status'] == 'match' and compared['trace_complete']
    assert compared['end_status'] == 'pass'
    lines = [json.loads(line) for line in trace.read_text().splitlines()]
    first_write = next(line for line in lines if line.get('rd', 0))
    first_write['rd_wdata'] = hex(int(first_write['rd_wdata'], 16) ^ 1)
    trace.write_text(''.join(json.dumps(line) + '\n' for line in lines))
    comparison = run_group(command, capture=True, timeout=60)
    assert comparison.returncode != 0
    assert json.loads(comparison.stdout)['status'] == 'mismatch'


def test_rejects_rv64_elf(tmp_path):
    elf = compile_elf(tmp_path, 'wrong-xlen', 'j _start', xlen=64)
    result = invoke(['run', '--elf', elf, '--out', tmp_path / 'run', '--rvfi-trace', '--json'])
    assert result.returncode != 0
    run = json.loads(result.stdout)
    assert run['status'] == 'error' and 'ELF XLEN 64 does not match adapter XLEN 32' in run['message']
    assert run['instret'] == 0


def test_refuses_unavailable_konata():
    result = invoke(['build', '--konata', '--json'])
    assert result.returncode == 2
    report = json.loads(result.stdout)
    assert report['status'] == 'error'
    assert 'does not support Konata' in report['models'][0]['message']


def test_ecall_keeps_actual_tval(tmp_path):
    instructions = (EXAMPLE / 'programs/trap.S').read_text().split('_start:\n', 1)[1].split('.section .data', 1)[0]
    elf = compile_elf(tmp_path, 'ecall', instructions)
    result = invoke(['run', '--elf', elf, '--out', tmp_path / 'run', '--rvfi-trace',
                     '--mem-latency', 0, '--seed', 1, '--json'])
    assert result.returncode == 0, result.stderr
    trace = tmp_path / 'run' / 'rvfi.jsonl'
    events = [json.loads(line) for line in trace.read_text().splitlines()]
    trap = next(line for line in events if line.get('event') == 'trap')
    assert int(trap['cause'], 16) == 11
    assert int(trap['tval'], 16) == 0x73
    comparison = run_group([sys.executable, '-m', 'rvw', 'cosim', 'check', '--core', 'vexriscv',
                            '--platform', str(EXAMPLE / 'platform.json'), '--elf', str(elf),
                            '--trace', str(trace), '--json'], capture=True, timeout=60)
    assert comparison.returncode != 0
    compared = json.loads(comparison.stdout)
    assert compared['status'] == 'mismatch'
    assert compared['mismatch']['differences']['tval'] == {'expected': '0x0', 'actual': '0x73'}


def test_live_arch_roi_events(tmp_path):
    """Check adapter counts against the saved retirement trace, not gem5."""
    source = tmp_path / 'roi.S'
    source.write_text('''
.section .text
.globl _start, setStats
_start:
  la s0, bench_stats
  li s1, 42
  jal ra, setStats
  sw s1, 0(s0)
  lw s2, 0(s0)
  bne s1, s2, bad
  sw zero, 4(s0)
  li s1, 10
  sw s1, 8(s0)
  sw zero, 12(s0)
  jal ra, setStats
  la t0, tohost
  li t1, 1
  sw t1, 0(t0)
1: j 1b
bad:
  la t0, tohost
  li t1, 3
  sw t1, 0(t0)
  j 1b
setStats:
  ret
.section .data
.balign 8
.globl tohost, bench_stats
tohost: .dword 0
bench_stats: .dword 0,0
''')
    elf = tmp_path / 'roi'
    built = run_group([GCC, '-march=rv32im_zicsr', '-mabi=ilp32', '-nostdlib', '-nostartfiles',
                       '-T', str(EXAMPLE / 'programs/link.ld'), str(source), '-o', str(elf)],
                      capture=True, text=True, timeout=30)
    assert built.returncode == 0, built.stderr
    out = tmp_path / 'run'
    result = invoke(['run', '--elf', elf, '--out', out, '--seed', 1,
                     '--mem-latency', 1, '--rvfi-trace', '--json'])
    assert result.returncode == 0, result.stderr
    raw = json.loads((out / 'result.json').read_text())
    assert raw['status'] == 'pass'
    metrics = raw['metrics']
    assert metrics['roi_cycles'] == 42 and metrics['roi_instret'] == 10
    # Locate the entry symbol from the ELF's symbol table via the native nm tool.
    nm = run_group([GCC.removesuffix('gcc') + 'nm', str(elf)], capture=True, text=True, timeout=10)
    assert nm.returncode == 0
    marker = int(next(line.split()[0] for line in nm.stdout.splitlines()
                      if line.split()[-1] == 'setStats'), 16)
    records = [json.loads(line) for line in (out / 'rvfi.jsonl').read_text().splitlines()]
    records = [r for r in records if 'pc' in r]
    boundaries = [i for i, r in enumerate(records) if int(r['pc'], 16) == marker]
    assert len(boundaries) == 2
    roi = records[boundaries[0] + 1:boundaries[1] + 1]
    opcodes = [int(r['insn'], 16) & 127 for r in roi]
    assert metrics['roi_retired'] == len(roi)
    assert metrics['roi_loads'] == opcodes.count(3) == 1
    assert metrics['roi_stores'] == opcodes.count(35) == 4
    assert metrics['roi_branches'] == sum(op in (99, 103, 111) for op in opcodes)
