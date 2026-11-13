"""Native smoke: RV32 machine-only interrupt campaigns build and pass on Spike."""
import shutil
import subprocess
from pathlib import Path
import pytest
from rvw.privilege import campaign

ROOT = Path(__file__).resolve().parents[2]
GCC = shutil.which('riscv64-unknown-elf-gcc') or '/opt/homebrew/opt/riscv-gnu-toolchain/bin/riscv64-unknown-elf-gcc'


@pytest.mark.skipif(not Path(GCC).exists() or not shutil.which('spike'), reason='needs RISC-V GCC and Spike')
def test_rv32_wfi_clint_builds_and_passes_on_spike(tmp_path):
    campaign.build(ROOT / 'examples/privilege/spike-wfi-rv32.json', tmp_path / 'wfi', gcc=GCC)
    campaign.build(ROOT / 'examples/privilege/scheduled-wfi-rv32.json', tmp_path / 'sched', gcc=GCC)
    for elf in sorted((tmp_path / 'wfi').glob('*.elf')):
        result = subprocess.run(['spike', '--isa=rv32i_zicsr', '--priv=m', '-m128', str(elf)],
                                capture_output=True, text=True, timeout=20)
        assert result.returncode == 0, (elf.name, result.stderr)
