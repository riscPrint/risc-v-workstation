"""Platform mistakes fail before reference execution; masks remain auditable."""
import copy
import json
from pathlib import Path

import pytest
from rvw.cosim.platform import Platform
from rvw.cosim.checker import check
from test_state import fixture, Model
from cosim_build import _build
from model_fixtures import Spike


@pytest.mark.parametrize('key,value', [('priviledge_modes', 'M'), ('ecall_mtval', 'insn'),
                                       ('schema', 'unknown/1')])
def test_unknown_settings(tmp_path, key, value):
    settings = json.loads(Path('examples/vexriscv/rvw/platform.json').read_text())
    settings[key] = value
    path = tmp_path / 'platform.json'
    path.write_text(json.dumps(settings))
    with pytest.raises(ValueError, match='unknown|schema'):
        Platform.load('test', path)


def test_applied_mask_survives_history_eviction(tmp_path):
    h, row = fixture()
    row.update(insn='0x30102573', rd=10, fd_valid=False, rd_wdata='0x2')
    p = Platform.load('boom')
    model = Model(row)
    model.effect['rd_wdata'] = 0
    model.set_reg = lambda *args: None
    path = tmp_path / 'trace.jsonl'
    path.write_text('\n'.join(map(json.dumps, [h, row])))
    result = check(path, model, p, history=0)
    assert result['status'] == 'match'
    assert result['recent_synchronizations'] == []
    assert result['applied_masks'] == [{'reason': 'csr', 'csr': '0x301', 'mask': '0x6'}]
    assert result['platform_policy']['privilege_modes'] == 'MSU'
    assert check(path, Model(row), p, sync=())['applied_masks'] == []


def test_rv32_m_only_without_pmp(tmp_path, tmp_path_factory):
    # This is an independent reference program, not a VexRiscv DUT run.
    source = tmp_path / 'm_only.S'
    source.write_text('''.section .text
.globl _start
_start:
  la t0, handler
  csrw mtvec, t0
  csrr a0, misa
  li t0, -1
  csrw pmpaddr0, t0
  csrr a1, pmpaddr0
  ecall
handler:
  csrr a2, mtval
1: j 1b
''')
    elf = _build(tmp_path_factory, source, march='rv32im_zicsr', mabi='ilp32')
    p = Platform.load('test', 'examples/vexriscv/rvw/platform.json')
    p.privilege_modes = 'M'
    reference = Spike(p, elf)
    effects = []
    try:
        for _ in range(16):
            effects.append(reference.step())
            if effects[-1]['rd'] == 12:
                break
    finally:
        reference.close()
    reads = {e['rd']: e['rd_wdata'] for e in effects if e['rd'] in (10, 11, 12)}
    assert reads[10] & ((1 << 18) | (1 << 20)) == 0
    assert reads[11] == 0
    assert reads[12] == 0x73
    assert next(e for e in effects if e['trap'])['cause'] == 11
