import json
import shutil
import pytest
from rvw.regress import mmu


def cases():
    return [dict(id=f'{mode}-napot-range-{fence}', mode=mode, napot=True, napot_remap=True, level=0, flags='VRWAD',
                 access='load', expect='success', fence=fence, bins=[f'{mode}.napot-range.{fence}'])
            for mode in ('sv39','sv48','sv57') for fence in ('all','va')]


def test_range_checks():
    for s in cases():
        mmu.validate(s)
        code = mmu.assembly(s)
        assert code.count(' ld a0, 0(t3)') == 32
        if s['fence'] == 'va':
            assert code.count(' sfence.vma t3, x0') == 16


def test_spike(tmp_path):
    gcc, spike = shutil.which('riscv64-unknown-elf-gcc'), shutil.which('spike')
    if not gcc or not spike:
        pytest.skip('native Spike and RISC-V GCC required')
    path = tmp_path / 'cases.json'
    path.write_text(json.dumps(dict(schema='rvw.mmu/1', scenarios=cases())))
    mmu.build(path, tmp_path / 'build', gcc)
    report = mmu.reference(tmp_path / 'build', spike, 2)
    assert report['status'] == 'pass', [(r['id'], r['stderr']) for r in report['scenarios'] if r['status'] != 'pass']
