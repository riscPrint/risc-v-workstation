import importlib.util
from pathlib import Path
import shutil
import pytest
from rvw.runs.elf import Elf

pytestmark=pytest.mark.slow
spec=importlib.util.spec_from_file_location('smp_common_program',Path(__file__).parents[1]/'cosim_program.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_initialized_shared_mailbox_is_loadable(tmp_path):
    gcc=shutil.which('riscv64-unknown-elf-gcc')
    if not gcc:
        pytest.skip('RISC-V GCC required')
    source='''.text
.globl _start
_start: j _start
.section .tohost,"aw",@progbits
.globl tohost
tohost: .zero 16
.section .shared,"aw",@progbits
.dword 1
'''
    module.build(tmp_path/'program',gcc=gcc,source=source)
    elf=Elf(str(tmp_path/'program/shared.elf'))
    offset=elf.file_offset(0x81000000)
    assert offset is not None, 'shared initializer was discarded by NOLOAD'
    assert int.from_bytes(elf.data[offset:offset+8],'little')==1
