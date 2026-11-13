"""Execute generated project CSR assembly on the native Spike reference."""
import shutil
from pathlib import Path

import pytest

from rvw.common.proc import run_group
from rvw.formal.csr import generate

pytestmark = pytest.mark.slow


@pytest.mark.parametrize('name', ['mscratch', 'sscratch'])
def test_vex_csr_reference(tmp_path, name):
    gcc = shutil.which('riscv64-unknown-elf-gcc')
    if not gcc:
        candidate = Path('/opt/homebrew/opt/riscv-gnu-toolchain/bin/riscv64-unknown-elf-gcc')
        gcc = str(candidate) if candidate.is_file() else None
    spike = shutil.which('spike')
    if not gcc or not spike:
        pytest.skip('RISC-V GCC and Spike required')
    root = Path(__file__).resolve().parents[3]
    out = tmp_path/'generated'
    generate(root/'examples/vexriscv/csr.json', out)
    elf = tmp_path/name
    build = run_group([gcc, '-march=rv32im_zicsr', '-mabi=ilp32', '-nostdlib',
        '-nostartfiles', '-T', str(root/'examples/vexriscv/rvw/programs/link.ld'), str(out/(name+'.S')), '-o', str(elf)],
        capture=True, timeout=20)
    assert build.returncode == 0, build.stdout + build.stderr
    run = run_group(['nice', '-n', '10', spike, '--isa=rv32im_zicsr_zifencei',
        '--priv=m', str(elf)], capture=True, timeout=20)
    assert run.returncode == 0, run.stdout + run.stderr
