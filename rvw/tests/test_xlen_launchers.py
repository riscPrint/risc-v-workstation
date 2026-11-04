"""Opt-in BOOM launcher parity with a tiny ELF32 input; no model may build."""
import json
import os
import struct
from pathlib import Path

import pytest

from rvw.common.proc import run_group

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(not os.environ.get('RVW_EXTERNAL_BOOM_LAUNCHER'),
                    reason='set RVW_EXTERNAL_BOOM_LAUNCHER for BOOM launcher parity')
@pytest.mark.parametrize('external', [False, True])
@pytest.mark.parametrize('batch', [False, True])
def test_wrong_xlen_before_model(tmp_path, external, batch):
    # Minimal RV32 ELF header, the same width as the VexRiscv smoke program.
    header = bytearray(64)
    header[:6] = b'\x7fELF\x01\x01'
    struct.pack_into('<H', header, 18, 243)
    elf = tmp_path / 'rv32.elf'
    elf.write_bytes(header)
    out = tmp_path / 'out'
    launcher = (os.environ['RVW_EXTERNAL_BOOM_LAUNCHER'] if external
                else str(ROOT / 'RiscvSim/boom/run.sh'))
    if batch:
        manifest = tmp_path / 'jobs.jsonl'
        manifest.write_text(json.dumps(dict(elf=str(elf), out=str(out), seed=1)) + '\n')
        args = ['run-many', '--manifest', str(manifest)]
    else:
        args = ['run', '--elf', str(elf), '--out', str(out), '--seed', '1']
    env = dict(os.environ, RVW_HOME=str(ROOT))
    result = run_group([launcher, *args, '--json'], env=env, capture=True,
                       text=True, timeout=180)
    assert not result.timed_out, result.stderr
    assert result.returncode == 2, result.stderr
    run = json.loads((out / 'result.json').read_text())
    assert run['status'] == 'error'
    assert 'ELF XLEN 32 does not match adapter XLEN 64' in run['message']
    assert run['cycles'] == run['instret'] == 0
    assert run['rtl_sha256'] is None
    assert not any(word in result.stderr for word in ('[build]', '[Progress]'))
