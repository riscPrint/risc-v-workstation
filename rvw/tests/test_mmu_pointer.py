import shutil
from pathlib import Path

import pytest

from rvw.regress import mmu

DESCRIPTION = Path(__file__).resolve().parents[2] / 'examples/mmu/pointer.json'


def test_tag_is_only_on_the_tested_pointer():
    cases = mmu.load(DESCRIPTION)
    assert len(cases) == 9
    for s in cases:
        code = mmu.assembly(s)
        assert 'li t3, 9223372037928517632' in code
        assert 'csrr t1, menvcfg' in code
        assert 'bne t0, t1, fail' in code
        assert 'csrr t0, mtval' in code


def test_spike_pointer_masking(tmp_path):
    gcc = shutil.which('riscv64-unknown-elf-gcc')
    spike = shutil.which('spike')
    if not gcc or not spike:
        pytest.skip('native Spike and RISC-V GCC required')
    mmu.build(DESCRIPTION, tmp_path, gcc)
    result = mmu.reference(tmp_path, spike, 2)
    assert result['status'] == 'pass', [(r['id'], r['status'], r['stderr']) for r in result['scenarios'] if r['status'] != 'pass']


def test_disabled_mask_does_not_pass_an_enabled_case(tmp_path, monkeypatch):
    import json
    gcc = shutil.which('riscv64-unknown-elf-gcc')
    spike = shutil.which('spike')
    if not gcc or not spike:
        pytest.skip('native Spike and RISC-V GCC required')
    case = mmu.load(DESCRIPTION)[1]
    desc = tmp_path / 'case.json'
    desc.write_text(json.dumps(dict(schema='rvw.mmu/1', scenarios=[case])))
    original = mmu.assembly
    monkeypatch.setattr(mmu, 'assembly', lambda s: original(s).replace('li t0, 8589934592', 'li t0, 0'))
    mmu.build(desc, tmp_path / 'build', gcc)
    assert mmu.reference(tmp_path / 'build', spike, 2)['status'] == 'fail'
