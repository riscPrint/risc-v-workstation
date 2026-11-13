"""Optional native SDK locations that package managers do not add to PATH."""
import os
from pathlib import Path
import shutil


def systemc_home():
    if 'SYSTEMC_HOME' in os.environ:
        return os.environ['SYSTEMC_HOME']
    for prefix in ('/opt/homebrew/opt/systemc', '/usr/local/opt/systemc'):
        if (Path(prefix) / 'include/systemc').is_file():
            return prefix
    return None


def llvm_tablegen():
    for candidate in ('llvm-tblgen', '/opt/homebrew/opt/llvm/bin/llvm-tblgen',
                      '/usr/local/opt/llvm/bin/llvm-tblgen'):
        tool = shutil.which(candidate)
        if tool:
            include = Path(tool).resolve().parents[1] / 'include'
            if (include / 'llvm/Target/Target.td').is_file():
                return tool, include
    return None, None


def require_core(core):
    """Require an explicitly selected source checkout before any native work."""
    import pytest
    variable, member = {
        'boom': ('SPINAL_BOOM', 'src/main/scala/boom'),
        'vexriscv': ('VEXRISCV', 'src/main/scala/vexriscv'),
    }[core]
    selected = os.environ.get(variable)
    if not selected or not (Path(selected) / member).is_dir():
        pytest.skip(f'{core} source checkout is unavailable; set {variable}')
    for tool in ('sbt', 'verilator', 'spike', os.environ.get('RISCV_GCC', 'riscv64-unknown-elf-gcc')):
        if not shutil.which(tool):
            pytest.skip('native core test needs ' + tool)
