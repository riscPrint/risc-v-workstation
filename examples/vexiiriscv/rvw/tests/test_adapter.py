"""Real Verilator controls. Run with the environment from the example README."""
import json
import os
import sys
from pathlib import Path

from rvw.common.proc import run_group

EXAMPLE = Path(__file__).resolve().parents[1]
GCC = os.environ.get('RISCV_PREFIX', 'riscv64-unknown-elf-') + 'gcc'


def invoke(arguments, timeout=900):
    result = run_group([str(EXAMPLE / 'run.sh'), *map(str, arguments)], timeout=timeout,
                       env=dict(os.environ), capture=True, text=True)
    assert not result.timed_out, result.stderr
    return result


def compile_elf(directory, name, instructions):
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
    result = run_group([GCC, '-march=rv32im_zicsr_zifencei', '-mabi=ilp32', '-nostdlib', '-nostartfiles',
                        '-T', str(EXAMPLE / 'programs/link.ld'), '-Wl,--build-id=none', str(source), '-o', str(elf)],
                       capture=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return elf


def cosim(elf, trace):
    command = [sys.executable, '-m', 'rvw', 'cosim', 'check', '--core', 'vexiiriscv',
               '--platform', str(EXAMPLE / 'platform.json'), '--elf', str(elf), '--trace', str(trace), '--json']
    result = run_group(command, capture=True, text=True, timeout=120)
    return result.returncode, json.loads(result.stdout)


def test_real_pass_fail_timeout_trap_and_cosim(tmp_path):
    programs = {
        'pass': ('la t0, tohost\nli t1, 1\nsw t1, 0(t0)', 'pass', None),
        'random': ('la t0, tohost\nli t1, 1\nsw t1, 0(t0)', 'pass', None),
        'fail': ('la t0, tohost\nli t1, 7\nsw t1, 0(t0)', 'fail', 3),
        'timeout': ('j _start', 'timeout', None),
        'branch': ('li t0, 3\n2: addi t0, t0, -1\nbnez t0, 2b\njal ra, 3f\n3: la t0, tohost\nli t1, 1\nsw t1, 0(t0)',
                   'pass', None),
        'trap': ('la t0, 4f\ncsrw mtvec, t0\nlw t1, 0(zero)\n4: csrr t2, mcause\nli t3, 5\nbne t2, t3, 5f\n'
                 'la t0, tohost\nli t1, 1\nsw t1, 0(t0)\n5: j 5b', 'pass', None),
    }
    jobs = []
    for name, (instructions, _, _) in programs.items():
        elf = compile_elf(tmp_path, name, instructions)
        jobs.append(dict(elf=str(elf), out=str(tmp_path / (name + '-run')), seed=1, max_cycles=2000,
                         rvfi_trace=True, mem_latency=None if name == 'random' else 0))
    manifest = tmp_path / 'jobs.jsonl'
    manifest.write_text(''.join(json.dumps(job) + '\n' for job in jobs))
    result = invoke(['run-many', '--manifest', manifest, '--jobs', 2, '--json'])
    assert result.returncode == 1, result.stderr
    for job, (name, (_, status, code)) in zip(jobs, programs.items()):
        out = Path(job['out'])
        run = json.loads((out / 'result.json').read_text())
        assert run['status'] == status, run
        assert run['fail_code'] == code, run
        lines = [json.loads(line) for line in (out / 'rvfi.jsonl').read_text().splitlines()]
        assert lines[0]['xlen'] == 32 and lines[0]['core'] == 'vexiiriscv'
        assert lines[-1] == {'event': 'end', 'cycle': lines[-1]['cycle'], 'status': status}
        assert all(a['cycle'] <= b['cycle'] for a, b in zip(lines[1:], lines[2:]))
        if status == 'pass':
            code_, compared = cosim(job['elf'], out / 'rvfi.jsonl')
            assert code_ == 0 and compared['status'] == 'match', compared
    traps = [json.loads(line) for line in (tmp_path / 'trap-run/rvfi.jsonl').read_text().splitlines()]
    assert [t['cause'] for t in traps if t.get('event') == 'trap'] == ['0x5']

    # A changed writeback must not match.
    trace = tmp_path / 'pass-run/rvfi.jsonl'
    lines = [json.loads(line) for line in trace.read_text().splitlines()]
    first = next(line for line in lines if line.get('rd', 0))
    first['rd_wdata'] = hex(int(first['rd_wdata'], 16) ^ 1)
    trace.write_text(''.join(json.dumps(line) + '\n' for line in lines))
    code_, compared = cosim(jobs[0]['elf'], trace)
    assert code_ != 0 and compared['status'] == 'mismatch'


def test_refuses_soc_map_and_rvfi_check(tmp_path):
    elf = compile_elf(tmp_path, 'pass', 'la t0, tohost\nli t1, 1\nsw t1, 0(t0)')
    result = invoke(['run', '--elf', elf, '--out', tmp_path / 'out', '--rvfi-check', '--json'])
    assert result.returncode == 2
    assert json.loads((tmp_path / 'out/result.json').read_text())['status'] == 'error'
