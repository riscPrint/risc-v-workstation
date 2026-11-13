"""Compile the RV32 control and absent-supervisor families through the public builder."""
import json
import shutil
import pytest

from rvw.privilege.campaign import build, scenarios

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('kind,priv', [('controls', 'msu'), ('disabled', 'mu')])
def test_exit_uses_the_campaign_xlen(kind, priv):
    for width, store in [(32, 'sw t1, 0(t0)'), (64, 'sd t1, 0(t0)')]:
        config = dict(kind=kind, priv=priv, isa=f'rv{width}im_zicsr_zifencei')
        rows = scenarios(config)
        assert rows
        for row in rows:
            assert store in row['assembly']
            assert ('sw zero, 4(t0)' in row['assembly']) == (width == 32)


@pytest.mark.parametrize('kind,priv,count', [('controls', 'msu', 30), ('disabled', 'mu', 72)])
def test_rv32_family_builds_with_real_assembler(tmp_path, kind, priv, count):
    compiler = shutil.which('riscv64-unknown-elf-gcc')
    if not compiler:
        pytest.skip('RISC-V GCC is not installed')
    source = tmp_path/'description.json'
    source.write_text(json.dumps(dict(schema='rvw.privilege/1', kind=kind, priv=priv,
                                     isa='rv32im_zicsr_zifencei')))
    result = build(source, tmp_path/'built', gcc=compiler)
    assert len(result['scenarios']) == count
    for row in result['scenarios']:
        data = (tmp_path/'built'/row['elf']).read_bytes()
        assert data[:5] == b'\x7fELF\x01'
