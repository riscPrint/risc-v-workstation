import json
import shutil
import pytest
from rvw.regress import mmu
from rvw.regress.mmu_random import matrix, plan


def test_seeded_tables_and_accesses():
    rows = matrix(dict(modes=['sv32', 'sv39', 'sv48', 'sv57'], seeds=[7, 19], pages=8, accesses=32))
    for row in rows:
        assert plan(row) == plan(row)
        assert len(plan(row)['accesses']) == 32
        assert any(a['fault'] for a in plan(row)['accesses'])
        mmu.validate(row)
        assert 'access_31:' in mmu.assembly(row)
    assert plan(rows[0]) != plan(rows[1])


def test_spike_random(tmp_path, monkeypatch):
    gcc, spike = shutil.which('riscv64-unknown-elf-gcc'), shutil.which('spike')
    if not gcc or not spike:
        pytest.skip('native Spike and RISC-V GCC required')
    path = tmp_path / 'random.json'
    path.write_text(json.dumps(dict(schema='rvw.mmu/1', random=dict(modes=['sv32', 'sv39', 'sv48', 'sv57'], seeds=[7, 19], pages=8, accesses=32))))
    cases = mmu.load(path) + matrix(dict(modes=['sv57'], seeds=[31], pages=64, accesses=128))
    path.write_text(json.dumps(dict(schema='rvw.mmu/1', scenarios=cases)))
    mmu.build(path, tmp_path / 'build', gcc)
    result = mmu.reference(tmp_path / 'build', spike, 2)
    assert result['status'] == 'pass', [(r['id'], r['stderr']) for r in result['scenarios'] if r['status'] != 'pass']


def test_spike_mpp_mutation(tmp_path, monkeypatch):
    from rvw.regress import mmu_random
    gcc, spike = shutil.which('riscv64-unknown-elf-gcc'), shutil.which('spike')
    if not gcc or not spike:
        pytest.skip('native Spike and RISC-V GCC required')
    path = tmp_path / 'random.json'
    path.write_text(json.dumps(dict(schema='rvw.mmu/1', random=dict(modes=['sv39'], seeds=[7], pages=8, accesses=32))))
    original = mmu_random.assembly
    monkeypatch.setattr(mmu_random, 'assembly', lambda s: original(s).replace(' li t0, 0x21800\n csrc mstatus, t0\n', ''))
    mmu.build(path, tmp_path / 'mutated', gcc)
    assert mmu.reference(tmp_path / 'mutated', spike, 2)['status'] == 'fail'
