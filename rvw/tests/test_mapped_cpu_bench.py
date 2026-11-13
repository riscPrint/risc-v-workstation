import json
import sqlite3
import pytest
from test_init_native_bindings import core
from test_uvm_scaffold import fixture
from rvw.vip.mapped import discover,generate
pytestmark=pytest.mark.fast


def setup(tmp_path):
    db,soc=fixture(tmp_path)
    c=sqlite3.connect(db)
    c.execute("UPDATE components SET module='Example'")
    c.execute('DELETE FROM bundles');c.commit();c.close()
    (tmp_path/'rvw').mkdir()
    (tmp_path/'rvw/core-map.json').write_text(json.dumps(core()))
    return db,soc


def test_plain_ports_use_adapter_declaration(tmp_path):
    db,soc=setup(tmp_path)
    from rvw.uvm.scaffold import generate as uvm
    from rvw.vip.catalog import skeleton
    report=uvm(db,soc,tmp_path/'uvm')
    assert report['profile']=='mapped_cpu'
    spec=json.loads((tmp_path/'uvm/bench.json').read_text())
    assert spec['top']=='Example'
    assert '@pyuvm.test()' in (tmp_path/'uvm/test_mapped.py').read_text()
    assert skeleton(db,tmp_path/'vip.py')['profile']=='mapped_cpu'
    compile((tmp_path/'vip.py').read_text(),'generated','exec')


def test_map_must_match_selected_database(tmp_path):
    db,_=setup(tmp_path)
    c=sqlite3.connect(db);c.execute("UPDATE components SET module='Other'");c.commit();c.close()
    with pytest.raises(ValueError,match='differs'):
        discover(db)
