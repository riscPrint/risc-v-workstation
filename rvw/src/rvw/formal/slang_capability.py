"""Probe the clocked SVA lowering required by the pinned frontend."""
from functools import lru_cache
from pathlib import Path
import shutil
import tempfile

from rvw.common.proc import run_group

INSTALL = 'scripts/install.sh --with-formal'


@lru_cache(maxsize=16)
def sva_unavailable(plugin: str) -> str | None:
    """Return an explicit capability gap; keep unrelated tool errors as errors."""
    yosys = shutil.which('yosys')
    if not yosys or not Path(plugin).is_file():
        return f'Clocked SVA requires Yosys and the pinned yosys-slang plugin; install with {INSTALL}'
    with tempfile.TemporaryDirectory(prefix='rvw-slang-probe-') as directory:
        source = Path(directory) / 'probe.sv'
        source.write_text('module top(input clk,a); assert property (@(posedge clk) a); endmodule\n')
        result = run_group([yosys, '-Q', '-T', '-m', plugin, '-p',
                            f'read_slang --top top {source}'], capture=True, timeout=15)
    output = (result.stdout or '') + (result.stderr or '')
    if result.returncode and 'SVA unsupported' in output:
        return ('Installed yosys-slang lacks clocked SVA lowering (SVA unsupported); '
                f'install the pinned source build with {INSTALL}')
    if result.returncode:
        raise RuntimeError('yosys-slang capability probe failed: ' + output)
    return None
