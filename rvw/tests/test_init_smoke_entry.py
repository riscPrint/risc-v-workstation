import os
import shutil
import struct
import subprocess

import pytest

from rvw.init.mapped import mapped_scaffold

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('isa', ['rv32i', 'rv64i'])
@pytest.mark.parametrize('offset', [0, 0x100])
def test_mapped_smoke_starts_at_declared_reset_pc(tmp_path, isa, offset):
    compiler = shutil.which('riscv64-unknown-elf-gcc')
    if compiler is None:
        pytest.skip('RISC-V GCC is required for the small smoke ELF')
    (tmp_path / 'build.sbt').write_text('lazy val core = project\n')
    reset_pc = 0x80000000 + offset
    mapped_scaffold(tmp_path, isa=isa, name='core', top='Core', sbt_project='core',
                    reset_pc=hex(reset_pc), buses=[
                        'mem:req-rsp:cmd_valid=req,address=addr,rsp_valid=rsp,rdata=data'])
    script = tmp_path / 'rvw/build-smoke.sh'
    result = subprocess.run(['bash', str(script)], env={**os.environ, 'RISCV_PREFIX': compiler.removesuffix('gcc')},
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    elf = (tmp_path / 'rvw/out/programs/smoke').read_bytes()
    entry = struct.unpack_from('<I' if elf[4] == 1 else '<Q', elf, 24)[0]
    assert entry == reset_pc
