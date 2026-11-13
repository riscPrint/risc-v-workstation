"""Configured Zacas checks. Native results cover instruction effects only."""
import importlib.util
import json
from pathlib import Path
import shutil
import pytest
from rvw.common.proc import run_group

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location('zacas_suite', ROOT / 'RiscvSim/tests/ordering/suite.py')
suite = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(suite)


@pytest.mark.parametrize('xlen', [32, 64])
def test_configured_generator(tmp_path, xlen):
    jobs = suite.generate(tmp_path, xlen, 7, ['zacas'])
    text = Path(jobs[0]['source']).read_text()
    for funct3 in ([2, 3] if xlen == 32 else [2, 3, 4]):
        for flags in range(4):
            assert f'.insn r 0x2f, {funct3}, {20 + flags}, a2, a0, a4' in text
    assert 'bne ra, t1, fail' in text
    assert 'x0, a0, x14' in text and 'x12, a0, x0' in text
    assert suite.DEFAULT_SUITES == ('lrsc', 'amo', 'fence', 'fence-i')


@pytest.mark.parametrize('xlen', [32, 64])
@pytest.mark.parametrize('name', ['zacas', 'zacas-fault', 'zacas-align'])
def test_native_spike(tmp_path, xlen, name):
    if not shutil.which('spike') or not shutil.which('riscv64-unknown-elf-gcc'):
        pytest.skip('native Spike and RISC-V GCC required')
    result = run_group([str(ROOT/'rvw/.venv/bin/python'), str(ROOT/'RiscvSim/tests/ordering/run.py'),
                        '--suite', name, '--xlen', str(xlen), '--seeds', '7',
                        '--out', str(tmp_path), '--timeout', '30'], timeout=60, capture=True)
    assert result.returncode == 0, (result.stdout, result.stderr)
    report = json.loads((tmp_path/'summary.json').read_text())
    assert report['reference'][0]['status'] == 'pass'
    assert report['ordering'] == 'inconclusive' and report['dut'] == 'not_run'


@pytest.mark.parametrize('fault', ['missing_cas', 'wrong_return', 'failed_cas_writes'])
def test_native_checker_faults(tmp_path, fault):
    if not shutil.which('spike') or not shutil.which('riscv64-unknown-elf-gcc'):
        pytest.skip('native Spike and RISC-V GCC required')
    text = suite.zacas(64, 7)
    instruction = '.insn r 0x2f, 2, 20, a2, a0, a4'
    if fault == 'missing_cas':
        text = text.replace(instruction, 'nop', 1)
    elif fault == 'wrong_return':
        text = text.replace(instruction, instruction+'\n li a2, 99', 1)
    else:
        # The second vector is an unsuccessful comparison. Inject an illegal write.
        first, rest = text.split(instruction, 1)
        text = first+instruction+rest.replace(instruction, instruction+'\n sw a4, 0(a0)', 1)
    source = tmp_path/'fault.S'; source.write_text(text)
    linker = tmp_path/'link.ld'; linker.write_text(suite.LINK)
    elf = tmp_path/'fault.elf'
    result = run_group(['riscv64-unknown-elf-gcc', '-march=rv64ima_zicsr_zifencei_zacas', '-mabi=lp64',
                        '-nostdlib', '-Wl,--no-relax', '-T', str(linker), str(source), '-o', str(elf)], timeout=30, capture=True)
    assert result.returncode == 0, result.stderr
    result = run_group(['spike', '--isa=rv64ima_zicsr_zifencei_zacas', str(elf)], timeout=10, capture=True)
    assert not result.timed_out and result.returncode != 0


@pytest.mark.parametrize('protection', [True, False])
@pytest.mark.parametrize('value,passes', [(0, True), (0x77, False)])
def test_platform_trap_values(tmp_path, protection, value, passes):
    """Inject permitted zero and bad nonzero values into the checker observation.

    Spike still executes every real fault. This does not claim its mtval is zero.
    """
    if not shutil.which('spike') or not shutil.which('riscv64-unknown-elf-gcc'):
        pytest.skip('native Spike and RISC-V GCC required')
    text = suite.zacas_traps(64, 7, protection).replace('csrr t4, mtval', f'li t4, {value}')
    source = tmp_path/'trap.S'; source.write_text(text)
    linker = tmp_path/'link.ld'; linker.write_text(suite.LINK)
    elf = tmp_path/'trap.elf'
    isa = 'rv64ima_zicsr_zifencei_zacas'
    result = run_group(['riscv64-unknown-elf-gcc', '-march='+isa, '-mabi=lp64', '-nostdlib',
                        '-Wl,--no-relax', '-T', str(linker), str(source), '-o', str(elf)], timeout=30, capture=True)
    assert result.returncode == 0, result.stderr
    result = run_group(['spike', '--isa='+isa, str(elf)], timeout=10, capture=True)
    assert not result.timed_out and (result.returncode == 0) == passes
