"""Native FTQ regression. Opt in to serialize gem5 under the machine lock."""
import json
import os
from pathlib import Path
import re
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


def check_fallthrough(log):
    expected = {}
    checked = 0
    for line in log.splitlines():
        branch = re.search(r'ftn:(\d+)\] Branch found at PC (0x[0-9a-f]+) taken\?:0, target:(0x[0-9a-f]+)', line)
        if branch:
            expected[branch[1]] = int(branch[3], 16)
        target = re.search(r'\[fn:(\d+)\].*Continue with PC:\((0x[0-9a-f]+)=>', line)
        if target and target[1] in expected:
            assert int(target[2], 16) == expected.pop(target[1]), line
            checked += 1
    assert checked > 0, 'No trained not-taken branches were checked'
    assert not expected, 'Missing fetch target completion records'


def first_stats(path):
    text = path.read_text().split('---------- End Simulation Statistics')[0]
    return {m[1]: float(m[2]) for m in re.finditer(r'^(\S+)\s+([0-9.]+)\s', text, re.M)}


def test_fallthrough_checker_rejects_half_instruction():
    log = ('[ftn:1] Branch found at PC 0x100 taken?:0, target:0x104\n'
           '[fn:1] Continue with PC:(0x102=>0x106)\n')
    with pytest.raises(AssertionError):
        check_fallthrough(log)
    check_fallthrough(log.replace('0x102=>', '0x104=>'))


@pytest.mark.skipif(os.environ.get('RVW_TEST_GEM5_FTQ') != '1', reason='opt-in native gem5 FTQ test')
def test_native_mixed_width_ftq(tmp_path):
    from rvw.common.lock import held
    from rvw.common.proc import run_group
    from rvw.arch.core import gem5_binary, tool_identity, validate_gem5

    binary = gem5_binary()
    with held('gem5'):
        validate_gem5(tool_identity(binary, '--build-info'))
    sources = os.environ['RVW_TEST_RISCV_TESTS']
    cc = os.environ.get('RVW_RISCV_CC', 'riscv64-unknown-elf-gcc')
    subprocess.run(['make', '-s', '-C', str(ROOT / 'Arch/bench'), f'SRC={sources}',
                    f'BARE_CC={cc}', 'BENCHES=ftq-branches', f'BUILD={tmp_path}/bench'], check=True)
    elf = tmp_path / 'bench/ftq-branches.riscv'
    # Reuse a shipped description as test input, not a claim about that core.
    d = json.loads((ROOT / 'examples/boom/arch/large.json').read_text())
    d['config'] = 'ftq-test'
    results = {}
    stats = {}
    for enabled in (False, True):
        name = 'decoupled' if enabled else 'coupled'
        d['cpu'].update(decoupledFrontEnd=enabled, minInstSize=2,
                        numFTQEntries=16, fetchTargetWidth=64)
        desc = tmp_path / f'{name}.json'
        desc.write_text(json.dumps(d))
        out = tmp_path / name
        with held('gem5'):
            result = run_group(['nice', '-n', '10', binary, f'--outdir={out}',
                                '--debug-flags=BAC', '--debug-file=bac.log',
                                str(ROOT / 'Arch/model.py'), '--description', str(desc), str(elf)], timeout=120, capture=True)
        assert result.returncode == 0, result.stderr
        results[name] = json.loads((out / 'bare.json').read_text())
        assert results[name]['exit_code'] == 0
        assert results[name]['tohost'] == 1
        assert results[name]['bench_stats']['cycles'] > 0
        stats[name] = first_stats(out / 'stats.txt')
        if enabled:
            check_fallthrough((out / 'bac.log').read_text())
    assert results['coupled']['bench_stats']['instret'] == results['decoupled']['bench_stats']['instret']
    assert stats['coupled']['system.cpu.ftq.inserts'] == 0
    assert stats['decoupled']['system.cpu.ftq.inserts'] > 0
    assert stats['decoupled']['system.cpu.ftq.removals'] > 0
