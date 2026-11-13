import json
import shutil
import pytest
from rvw.regress import mmu
from rvw.regress.mmu_guest_pointer import matrix


def test_configuration_and_masking_exemption():
    for s in matrix(dict(modes=['sv39','sv48','sv57'])):
        mmu.validate(s)
        code = mmu.assembly(s)
        assert ('hstatus' if s['guest_pointer'].get('context') == 'U' else 'henvcfg' if s['guest_pointer']['privilege'] == 'S' else 'senvcfg') in code
        if s['guest_op'] == 'hlvx.wu':
            assert s['expect'] == 'page-fault'


def test_spike(tmp_path):
    gcc, spike = shutil.which('riscv64-unknown-elf-gcc'), shutil.which('spike')
    if not gcc or not spike:
        pytest.skip('native Spike and RISC-V GCC required')
    path = tmp_path / 'description.json'
    path.write_text(json.dumps(dict(schema='rvw.mmu/1', guest_pointer_matrix=dict(modes=['sv39','sv48','sv57']))))
    mmu.build(path, tmp_path / 'build', gcc)
    result = mmu.reference(tmp_path / 'build', spike, 2)
    assert result['status'] == 'pass', [(r['id'],r['stderr']) for r in result['scenarios'] if r['status'] != 'pass']
