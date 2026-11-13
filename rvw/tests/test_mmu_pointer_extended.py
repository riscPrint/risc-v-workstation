import json
import shutil
import pytest
from rvw.regress import mmu


from rvw.regress.mmu_pointer import matrix


def test_configuration():
    for row in matrix():
        mmu.validate(row)
        code = mmu.assembly(row)
        assert ({'ssnpm': 'senvcfg', 'smmpm': 'mseccfg', 'smnpm': 'menvcfg', 'sspm': 'menvcfg', 'supm': 'senvcfg'}[row['pointer_extension']]) in code


def test_spike(tmp_path):
    gcc, spike = shutil.which('riscv64-unknown-elf-gcc'), shutil.which('spike')
    if not gcc or not spike:
        pytest.skip('native Spike and RISC-V GCC required')
    path = tmp_path / 'cases.json'
    path.write_text(json.dumps(dict(schema='rvw.mmu/1', scenarios=matrix())))
    mmu.build(path, tmp_path / 'build', gcc)
    result = mmu.reference(tmp_path / 'build', spike, 2)
    assert result['status'] == 'pass', [(r['id'], r['status'], r['stderr']) for r in result['scenarios'] if r['status'] != 'pass']


def test_environment_controller_required():
    row = matrix()[18]
    del row['pointer_controller']
    with pytest.raises(ValueError, match='explicit project'):
        mmu.validate(row)
