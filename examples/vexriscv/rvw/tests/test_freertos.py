"""Pinned FreeRTOS boot and fresh-process live restore on VexRiscv RTL."""
import json
import os
from pathlib import Path
import sys

import pytest
from rvw.common.proc import run_group
from test_adapter import EXAMPLE, GCC


def test_freertos_boot_and_live_restore(tmp_path):
    kernel = os.environ.get('FREERTOS_KERNEL')
    if not kernel:
        pytest.skip('set FREERTOS_KERNEL to the pinned external V11.2.0 checkout')
    elf = tmp_path / 'freertos.elf'
    build = run_group([sys.executable, str(EXAMPLE / 'freertos/build.py'),
                       '--kernel', kernel, '--out', str(elf), '--gcc', GCC],
                      capture=True, text=True, timeout=30)
    assert build.returncode == 0, build.stderr
    checkpoint = tmp_path / 'checkpoint.json'
    for mode in ('save', 'restore'):
        result = run_group([str(EXAMPLE / 'checkpoint-probe.sh'), str(elf),
                            str(tmp_path / mode), str(checkpoint), mode, '5000', '-',
                            str(EXAMPLE.parent / 'live-devices.json')],
                           env=dict(os.environ, RVW_BOOT_MAX_CYCLES='500000'),
                           capture=True, text=True, timeout=600)
        assert result.returncode == 0, result.stdout + result.stderr
        output = json.loads((tmp_path / mode / 'devices.json').read_text())['uart']
        assert output.startswith('FreeRTOS boot\n')
        assert output.endswith('FreeRTOS PASS\n')
        assert output.splitlines().count('A') == 3
        assert output.splitlines().count('B') == 3
    state = json.loads(checkpoint.read_text())['state']
    assert state['retired'] == '5000'
    assert state['devices']['schema'] == 'rvw.live-devices/1'
    assert (tmp_path / 'save/rvfi.jsonl').read_bytes() == (tmp_path / 'restore/rvfi.jsonl').read_bytes()
    assert (tmp_path / 'save/devices.json').read_bytes() == (tmp_path / 'restore/devices.json').read_bytes()
