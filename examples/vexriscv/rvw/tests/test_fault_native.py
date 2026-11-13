"""Real RTL fault injection through the generic RiscvSim `--fault` hook (needs VEXRISCV and native tools)."""
import json
import os

import pytest

from test_adapter import compile_elf, invoke

pytestmark = pytest.mark.skipif(not os.environ.get('VEXRISCV'), reason='VEXRISCV checkout not set')


def test_flip_is_confirmed_and_a_missing_site_is_not_injected(tmp_path):
    elf = compile_elf(tmp_path, 'loop', 'li t0, 50\n2: addi t0, t0, -1\nbnez t0, 2b\nla t1, tohost\nli t2, 1\nsw t2, 0(t1)')
    faults = tmp_path / 'faults.json'
    faults.write_text(json.dumps({'schema': 'rvw.fault/1', 'faults': [
        {'id': 'a', 'kind': 'flip', 'site': 'CsrPlugin_mscratch', 'bit': 4, 'cycle': 30},
        {'id': 'b', 'kind': 'stuck1', 'site': 'no_such_register', 'bit': 0, 'cycle': 30}]}))
    out = tmp_path / 'run'
    invoke(['run', '--elf', elf, '--out', out, '--seed', 1, '--mem-latency', 0, '--rvfi-trace', '--fault', faults])
    fault = json.loads((out / 'result.json').read_text())['details']['fault']
    first, missing = fault['faults']
    assert first['applied'] is True and int(first['after'], 16) ^ int(first['before'], 16) == 1 << 4
    assert missing['applied'] is False and 'not a public register' in missing['reason']
    assert fault['applied'] is False
