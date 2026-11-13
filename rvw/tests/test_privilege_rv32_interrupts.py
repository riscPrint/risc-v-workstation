"""RV32 machine-only interrupt campaigns: generation, build and Spike smoke."""
import json
import shutil
import subprocess
from pathlib import Path
import pytest
from rvw.privilege import campaign
from rvw.privilege.scheduled import programs as scheduled
from rvw.privilege.wake import programs as wake
from rvw.regress.commands.applicability import plan

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]
TIMER = {'mtime': 0x200bff8, 'mtimecmp': 0x2004000, 'msip': 0x2000000, 'delta': 100}
RV32M = {'isa': 'rv32i_zicsr', 'priv': 'm'}


def test_rv32_programs_use_word_stores_and_bit_31_causes():
    rows = wake(dict(RV32M, timer=TIMER)) + scheduled(dict(RV32M, wake={'assert_cycle': 1000, 'clear_cycle': 20000}))
    for row in rows:
        text = row['assembly']
        assert ' sd ' not in text and ' ld ' not in text
        assert 'pmpaddr0' not in text and 'satp' not in text and 'medeleg' not in text
        assert f'li t1, {(1 << 31) | 7}' in text or f'li t1, {(1 << 31) | 3}' in text or f'li t1, {(1 << 31) | 11}' in text
    timer = next(r for r in rows if r['id'] == 'wfi-timer-mie-1')['assembly']
    assert 'bne t2, t3, read_mtime' in timer and 'sltu t4, t1, t4' in timer
    # The RV64 default is unchanged.
    assert f'li t1, {(1 << 63) | 7}' in next(r for r in wake({'timer': TIMER}) if r['id'] == 'wfi-timer-mie-1')['assembly']


def test_machine_only_priv_is_limited_to_interrupt_kinds(tmp_path):
    for name in ('scheduled-wfi-rv32.json', 'spike-wfi-rv32.json'):
        assert campaign.load(ROOT / 'examples/privilege' / name)['priv'] == 'm'
    bad = tmp_path / 'c.json'
    bad.write_text(json.dumps({'schema': 'rvw.privilege/1', 'kind': 'controls', 'priv': 'm'}))
    with pytest.raises(ValueError, match='supervisor'):
        campaign.load(bad)


def test_rv32_core_with_interrupts_gets_rv32_suites(tmp_path):
    features = tmp_path / 'f.json'
    features.write_text(json.dumps(dict(schema='rvw.regress-features/1', isa='rv32im_zicsr',
        privilege_modes='M', pmp_regions=0, irq_inputs=[3, 7, 11], capabilities=['device:clint'])))
    applicable = {x['name'] for x in plan(features)['suites'] if x['applicable']}
    assert {'scheduled-wfi-rv32', 'wfi-clint-rv32'} <= applicable
    assert not {'scheduled-wfi', 'wfi-clint'} & applicable
