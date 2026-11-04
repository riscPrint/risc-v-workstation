"""Host checks for benchmark return checks and ROI pairing, not RISC-V timing."""
from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.parametrize('name', ['pointer-chase', 'branch-loop', 'dependent-chain', 'independent-misses', 'sequential-bandwidth'])
def test_micro_work_and_roi(name, tmp_path):
    cc = shutil.which('cc')
    if not cc:
        pytest.skip('host C compiler unavailable')
    source = Path(__file__).resolve().parents[2] / 'Arch/bench/micro' / (name + '.c')
    (tmp_path / 'util.h').write_text('void setStats(int enable);\n')
    runtime = tmp_path / 'runtime.c'
    runtime.write_text('''#include <stdlib.h>
static int state;
void setStats(int enable) {
  if (enable != (state == 0) || state > 1) abort();
  ++state;
}
__attribute__((destructor)) static void check(void) { if (state != 2) abort(); }
''')
    binary = tmp_path / name
    subprocess.run([cc, '-O2', '-I', str(tmp_path), str(source), str(runtime), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True, timeout=10)
