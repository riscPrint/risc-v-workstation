"""CMO byte assertions. No cache/device completion evidence is inferred."""
import importlib.util
import json
from pathlib import Path
import shutil
import pytest
from rvw.common.proc import run_group

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location('cbo_suite', ROOT/'RiscvSim/tests/ordering/suite.py')
suite = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(suite)


@pytest.mark.parametrize('size', [None, 0, 15, 48, 8192])
def test_requires_block_profile(tmp_path, size):
    with pytest.raises(ValueError, match='cache block size'):
        suite.generate(tmp_path, suites=['cbo'], cache_block_size=size)


@pytest.mark.parametrize('xlen', [32, 64])
@pytest.mark.parametrize('size', [32, 64])
def test_native_bytes(tmp_path, xlen, size):
    if not shutil.which('spike') or not shutil.which('riscv64-unknown-elf-gcc'):
        pytest.skip('native Spike and RISC-V GCC required')
    result = run_group([str(ROOT/'rvw/.venv/bin/python'), str(ROOT/'RiscvSim/tests/ordering/run.py'),
                        '--suite', 'cbo', '--cache-block-size', str(size), '--xlen', str(xlen),
                        '--seeds', '7', '--out', str(tmp_path), '--timeout', '30'], timeout=60, capture=True)
    assert result.returncode == 0, (result.stdout, result.stderr)
    report = json.loads((tmp_path/'summary.json').read_text())
    assert report['reference'][0]['status'] == 'pass'
    assert report['dut'] == 'not_run'


@pytest.mark.parametrize('fault', ['no_zero', 'partial_zero', 'guard_corruption'])
def test_native_faults(tmp_path, fault):
    if not shutil.which('spike') or not shutil.which('riscv64-unknown-elf-gcc'):
        pytest.skip('native Spike and RISC-V GCC required')
    text = suite.cache_blocks(64, 7, 64)
    replacement = {'no_zero': 'nop', 'partial_zero': 'sw zero, 0(t0)',
                   'guard_corruption': 'cbo.zero 0(t0)\n sb zero, -1(t0)'}[fault]
    text = text.replace('cbo.zero 0(t0)', replacement, 1)
    source = tmp_path/'fault.S'; source.write_text(text)
    linker = tmp_path/'link.ld'; linker.write_text(suite.LINK)
    elf = tmp_path/'fault.elf'
    isa = 'rv64ima_zicsr_zifencei_zicbom_zicboz_zicbop'
    result = run_group(['riscv64-unknown-elf-gcc', '-march='+isa, '-mabi=lp64', '-nostdlib',
                        '-Wl,--no-relax', '-T', str(linker), str(source), '-o', str(elf)], timeout=30, capture=True)
    assert result.returncode == 0, result.stderr
    result = run_group(['spike', '--isa='+isa, '--blocksz=64', str(elf)], timeout=10, capture=True)
    assert not result.timed_out and result.returncode != 0
