"""Opt-in BOOM benchmark execution and independent Spike comparison."""
import json
import os
from pathlib import Path
import sys

import pytest

from rvw.common.proc import run_group


def test_benchmark_cosim(tmp_path):
    elf = os.environ.get('RVW_TEST_BENCHMARK_ELF')
    if not elf:
        pytest.skip('set RVW_TEST_BENCHMARK_ELF to a built integer benchmark')
    assert Path(elf).is_file(), 'configured benchmark ELF is missing'
    root = Path(__file__).resolve().parents[3]
    out = tmp_path / 'benchmark'
    config = os.environ.get('RVW_TEST_BENCHMARK_CONFIG', 'small')
    run = run_group([
        str(root / 'scripts/with-lock.sh'), 'boom', 'nice', '-n', '10',
        str(root / 'RiscvSim/boom/run.sh'), 'run', '--elf', elf, '--out', str(out),
        '--config', config, '--seed', '1', '--mem-latency', '20',
        '--max-cycles', '2000000', '--wall-timeout', '60', '--rvfi-trace', '--json',
    ], cwd=root, timeout=900, capture=True)
    assert run.returncode == 0, (run.stdout, run.stderr)
    result = json.loads((out / 'result.json').read_text())
    assert result['status'] == 'pass' and result['config'] == config
    assert not result.get('inconclusive'), result
    check = run_group([
        sys.executable, '-m', 'rvw', 'cosim', 'check', '--core', 'boom',
        '--elf', elf, '--trace', str(out / 'rvfi.jsonl'), '--json',
    ], cwd=root, timeout=120, capture=True)
    assert check.returncode == 0, (check.stdout, check.stderr)
    comparison = json.loads(check.stdout)
    assert comparison['status'] == 'match', comparison
    assert comparison['trace_complete'] is True and comparison['end_status'] == 'pass'
    assert comparison['instructions'] > 0
