"""Portable ordering source tests and real native reference runs."""
import importlib.util
import json
import os
from pathlib import Path
import shutil

import pytest
from rvw.common.proc import run_group

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location('ordering_suite', ROOT / 'RiscvSim/tests/ordering/suite.py')
suite = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(suite)


def test_manifest_uses_random_timing(tmp_path):
    jobs = suite.generate(tmp_path)
    text = (tmp_path / 'manifest-1.jsonl').read_text()
    assert 'mem_latency' not in text and 'mem-latency' not in text
    assert jobs[0]['seed'] == 1 and jobs[0]['rvfi_trace']
    assert {j['name'] for j in jobs} == set(suite.DEFAULT_SUITES)


@pytest.mark.parametrize('xlen', [32, 64])
@pytest.mark.parametrize('seed', [1, 7, 23])
def test_spike_assertions(tmp_path, xlen, seed):
    if not shutil.which('spike') or not shutil.which('riscv64-unknown-elf-gcc'):
        pytest.skip('native Spike and RISC-V GCC required')
    r = run_group([str(ROOT / 'rvw/.venv/bin/python'), str(ROOT / 'RiscvSim/tests/ordering/run.py'),
                   '--out', str(tmp_path), '--xlen', str(xlen), '--seeds', str(seed)],
                  timeout=120, capture=True)
    assert r.returncode == 0, (r.stdout, r.stderr)
    summary = json.loads((tmp_path / 'summary.json').read_text())
    assert len(summary['reference']) == len(suite.DEFAULT_SUITES)
    assert all(r['status'] == 'pass' for r in summary['reference'])


def test_spike_rejects_bad_assertion(tmp_path):
    if not shutil.which('spike') or not shutil.which('riscv64-unknown-elf-gcc'):
        pytest.skip('native Spike and RISC-V GCC required')
    source = tmp_path / 'bad.S'
    source.write_text(suite.program('j fail'))
    (tmp_path / 'link.ld').write_text(suite.LINK)
    r = run_group(['riscv64-unknown-elf-gcc', '-march=rv64ima_zicsr_zifencei', '-mabi=lp64',
                   '-nostdlib', '-T', str(tmp_path / 'link.ld'), str(source), '-o', str(tmp_path / 'bad')],
                  timeout=30, capture=True)
    assert r.returncode == 0, r.stderr
    r = run_group(['spike', '--isa=rv64ima_zicsr_zifencei', str(tmp_path / 'bad')], timeout=10, capture=True)
    assert r.returncode != 0 and not r.timed_out


def test_runner_refuses_stale_dut_results(tmp_path):
    # This must fail before any compiler or reference command can run.
    old = tmp_path / 'lrsc-1-run'
    old.mkdir()
    (old / 'result.json').write_text('{"status":"pass"}')
    result = run_group([str(ROOT / 'rvw/.venv/bin/python'), str(ROOT / 'RiscvSim/tests/ordering/run.py'),
                        '--out', str(tmp_path), '--seeds', '1', '--gcc', '/missing/compiler',
                        '--adapter', '/missing/adapter'], timeout=10, capture=True)
    assert result.returncode == 2
    assert 'DUT output directories exist' in result.stderr


@pytest.mark.parametrize('xlen', [32, 64])
@pytest.mark.parametrize('granule', [4, 64])
@pytest.mark.parametrize('effect', ['legal', 'success_without_write', 'failure_with_write', 'source_write', 'reuse'])
def test_lrsc_reservation_shapes_and_effects(tmp_path, xlen, granule, effect):
    """Synthetic SC outcomes executed on Spike; not a DUT reservation model.

    At an operand-sized reservation, `other` is outside the set. At 64 bytes it is
    inside. Inject the allowed outcomes and broken memory effects into the
    generated checker. Keep the other SC instructions native.
    """
    if not shutil.which('spike') or not shutil.which('riscv64-unknown-elf-gcc'):
        pytest.skip('native Spike and RISC-V GCC required')
    text = suite.lrsc(xlen, 7)
    for width in (['w', 'd'] if xlen == 64 else ['w']):
        # Consume the real reservation without changing cell. Then supply a
        # synthetic result for SC to other. Cover spurious failure in both sets.
        outcomes = [False] if granule == 4 else [True, False]
        for index in range(4):
            success = outcomes[index % len(outcomes)]
            if effect == 'success_without_write':
                status, write = 0, False
            elif effect == 'failure_with_write':
                status, write = 1, True
            else:
                status, write = int(not success), success
            injection = f'sc.{width} t2, t5, (t0)\n'
            if effect == 'reuse':
                injection = ''  # Leave the real reservation live.
            if write:
                injection += f' s{width} t1, 0(t4)\n'
            if effect == 'source_write':
                injection += f' li t3, 99\n s{width} t3, 0(t0)\n'
            injection += f' li t2, {status}'
            text = text.replace(f'sc.{width} t2, t1, (t4)', injection, 1)
    source = tmp_path / 'effects.S'
    source.write_text(text)
    (tmp_path / 'link.ld').write_text(suite.LINK)
    isa = f'rv{xlen}ima_zicsr_zifencei'
    build = run_group(['riscv64-unknown-elf-gcc', f'-march={isa}',
                       '-mabi=' + ('lp64' if xlen == 64 else 'ilp32'), '-nostdlib',
                       '-Wl,--no-relax', '-T', str(tmp_path / 'link.ld'), str(source),
                       '-o', str(tmp_path / 'effects')], timeout=30, capture=True)
    assert build.returncode == 0, build.stderr
    result = run_group(['spike', '--isa=' + isa, str(tmp_path / 'effects')], timeout=10, capture=True)
    assert not result.timed_out
    assert (result.returncode == 0) == (effect == 'legal'), result.stderr


@pytest.mark.parametrize('xlen', [32, 64])
def test_native_amo_access_faults(tmp_path, xlen):
    if not shutil.which('spike') or not shutil.which('riscv64-unknown-elf-gcc'):
        pytest.skip('native Spike and RISC-V GCC required')
    r = run_group([str(ROOT / 'rvw/.venv/bin/python'), str(ROOT / 'RiscvSim/tests/ordering/run.py'),
                   '--out', str(tmp_path), '--xlen', str(xlen), '--seeds', '7', '--suite', 'amo-fault'],
                  timeout=120, capture=True)
    assert r.returncode == 0, (r.stdout, r.stderr)
    assert json.loads((tmp_path / 'summary.json').read_text())['reference'][0]['status'] == 'pass'


@pytest.mark.parametrize('mutation', ['no_trap', 'wrong_cause', 'wrong_pc', 'changed_rd'])
def test_amo_fault_checker_rejects_wrong_effect(tmp_path, mutation):
    if not shutil.which('spike') or not shutil.which('riscv64-unknown-elf-gcc'):
        pytest.skip('native Spike and RISC-V GCC required')
    text = suite.amo_fault(64, 7)
    if mutation == 'no_trap':
        text = text.replace(' amoadd.w t2, t1, (t0)', ' nop')
    elif mutation == 'wrong_cause':
        text = text.replace(' li t5, 7', ' li t5, 6')
    elif mutation == 'wrong_pc':
        text = text.replace(' bne t4, s0, fail', ' addi t4, t4, 4\n bne t4, s0, fail')
    else:
        text = text.replace(' addi s1, s1, 1', ' li t2, 0\n addi s1, s1, 1')
    source = tmp_path / 'fault.S'; source.write_text(text)
    (tmp_path / 'link.ld').write_text(suite.LINK)
    build = run_group(['riscv64-unknown-elf-gcc', '-march=rv64ima_zicsr_zifencei', '-mabi=lp64',
                       '-nostdlib', '-T', str(tmp_path / 'link.ld'), str(source), '-o', str(tmp_path / 'fault')],
                      timeout=30, capture=True)
    assert build.returncode == 0, build.stderr
    run = run_group(['spike', '--isa=rv64ima_zicsr_zifencei', str(tmp_path / 'fault')], timeout=10, capture=True)
    assert run.returncode != 0 and not run.timed_out
