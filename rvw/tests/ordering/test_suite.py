"""Portable ordering source tests and real native reference runs."""
import importlib.util
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


@pytest.mark.parametrize('xlen', [32, 64])
@pytest.mark.parametrize('seed', [1, 7, 23])
def test_spike_assertions(tmp_path, xlen, seed):
    if not shutil.which('spike') or not shutil.which('riscv64-unknown-elf-gcc'):
        pytest.skip('native Spike and RISC-V GCC required')
    r = run_group([str(ROOT / 'rvw/.venv/bin/python'), str(ROOT / 'RiscvSim/tests/ordering/run.py'),
                   '--out', str(tmp_path), '--xlen', str(xlen), '--seeds', str(seed)],
                  timeout=120, capture=True)
    assert r.returncode == 0, (r.stdout, r.stderr)


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
