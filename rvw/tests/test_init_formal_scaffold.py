import pytest
from test_init_native_bindings import core
pytestmark = pytest.mark.fast

def test_formal_scaffold_has_memory_and_all_rvfi_fields():
    from rvw.init.formal_scaffold import formal
    from rvw.formal.riscv import FIELDS
    import tomllib
    result, text = formal(core())
    cfg=tomllib.loads(text)['riscv_formal']
    assert set(cfg['ports']) == set(FIELDS)
    assert cfg['memory']['initial'] == 'symbolic-stable'
    wrapper=result['rvw/formal/wrapper.sv']
    assert wrapper.count('@RVFI_CONNECTIONS@') == 1
    assert wrapper.count('@MEMORY_ENVIRONMENT@') == 1
    assert '.ready(1\'b1)' in wrapper
    assert 'response_valid <= req && !write_enable' in wrapper
    assert cfg['build'] == ['./rvw/export-rtl.sh']
