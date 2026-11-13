import pytest
from rvw.checks.declarations import scaffold,template
from rvw.init.native_bindings import files
from test_init_native_bindings import core
pytestmark=pytest.mark.fast


def test_stubs_cover_families_without_claiming_binding():
    rows=scaffold()['rules']
    assert any(r['kind']=='fifo_order' for r in rows)
    assert len(rows)>5
    for r in rows:
        assert r['ports']
        assert all(v.startswith('REPLACE_') for v in r['ports'].values())
    assert 'rvw/templates/checks.micro.json' in files(core())
