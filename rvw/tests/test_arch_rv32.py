"""RV32 construction rules and runtime assembly. Native checks are separate."""
import copy
import os
import json
from pathlib import Path
import subprocess

import pytest
from test_arch_model import model

ROOT = Path(__file__).resolve().parents[2]

@pytest.mark.parametrize('kind', ['minor', 'timing'])
def test_rv32_description(kind):
    desc = json.loads((ROOT / f'examples/vexriscv/rvw/arch/{kind}.json').read_text())
    assert model.validate_description(desc) == desc
    for key, value in [('isa', 'rv64gc'), ('predictor', {}), ('queues', [{}]),
                       ('dcache', {'size': '1KiB'}), ('cpu', {'numThreads': 2})]:
        bad = copy.deepcopy(desc)
        bad[key] = value
        with pytest.raises(ValueError): model.validate_description(bad)


def test_runtime_keeps_rv64_and_reads_rv32_high_halves(tmp_path):
    # A compiler-independent check of the emitted runtime, not rollover validation.
    from rvw.common.dependencies import resolve
    try:
        source = Path(resolve('riscv-tests')['path']) / 'benchmarks/common/syscalls.c'
    except (ValueError, RuntimeError, OSError):
        pytest.skip('managed riscv-tests source unavailable')
    if not source.exists(): pytest.skip('riscv-tests source unavailable')
    result = subprocess.run(['sh', str(ROOT / 'Arch/bench/rt/patch_syscalls.sh'), str(source)],
                            capture_output=True, text=True, check=True).stdout
    for csr in ('mcycleh', 'minstreth'):
        assert result.count(csr) == 2
    assert result.count('while (hi != again)') == 2
    assert 'uint64_t start_cycles, start_instret' in result
    assert '#else\n  setStats_rt(enable);' in result


@pytest.mark.parametrize('kind', ['minor', 'timing'])
@pytest.mark.parametrize('size', [0, True, 1, 536875008])
def test_bad_model_ram(kind, size):
    desc = json.loads((ROOT / f'examples/vexriscv/rvw/arch/{kind}.json').read_text())
    desc['ram_bytes'] = size
    with pytest.raises(ValueError): model.validate_description(desc)


def test_rv32_runtime_retries_rollover(tmp_path):
    import re
    import shutil
    cc = shutil.which('cc')
    if not cc: pytest.skip('host C compiler unavailable')
    patch = (ROOT / 'Arch/bench/rt/patch_syscalls.sh').read_text()
    helper = patch.split('static uint64_t read_cycle64(void) {', 1)[1].split('static uint64_t read_instret64', 1)[0]
    helper = 'static uint64_t read_cycle64(void) {' + helper
    helper = re.sub(r'__asm__ volatile \("csrr %0, (mcycleh|mcycle)" : "=r"\((\w+)\)\);',
                    lambda m: m[2] + ' = next();', helper)
    assert '__asm__' not in helper
    # First high/low/high crosses rollover. The second read must be used.
    source = tmp_path / 'rollover.c'
    source.write_text('#include <stdint.h>\n#include <assert.h>\n'
                      'static unsigned i; static uint32_t values[]={4,0xffffffff,5,5,7,5};\n'
                      'static uint32_t next(void) { assert(i<6); return values[i++]; }\n'
                      + helper + '\nint main(void) { assert(read_cycle64()==((5ULL<<32)|7)); assert(i==6); }\n')
    binary = tmp_path / 'rollover'
    subprocess.run([cc, str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True, timeout=10)
