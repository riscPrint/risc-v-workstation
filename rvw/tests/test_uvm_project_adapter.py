import json
import sqlite3
import pytest
from test_uvm_scaffold import fixture
from rvw.uvm.scaffold import generate
pytestmark = pytest.mark.fast


def test_custom_bus_uses_project_scenario(tmp_path):
    db, soc = fixture(tmp_path)
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE bundles SET class_name='example.SimpleBus'")
        bus = conn.execute('SELECT path FROM bundles').fetchone()[0]
    (tmp_path / 'scenario.py').write_text('async def run(services):\n    raise RuntimeError("not qualified")\n')
    adapter = tmp_path / 'adapter.json'
    adapter.write_text(json.dumps(dict(schema='rvw.uvm-adapter/1', profile='cpu', bus=bus,
                                      scenario='scenario.py', bindings={'address':'io_address'})))
    report = generate(db, soc, tmp_path / 'bench', adapter=adapter)
    assert report['profile'] == 'cpu' and report['scenario_required']
    assert (tmp_path / 'bench/scenario.py').read_text() == (tmp_path / 'scenario.py').read_text()
    config = json.loads((tmp_path / 'bench/bindings.json').read_text())
    assert config['project_adapter']['bindings']['address'] == 'io_address'


def test_unknown_project_bus_refuses(tmp_path):
    db, soc = fixture(tmp_path)
    (tmp_path / 'scenario.py').write_text('')
    adapter = tmp_path / 'adapter.json'
    adapter.write_text(json.dumps(dict(schema='rvw.uvm-adapter/1', profile='cpu', bus='missing',
                                      scenario='scenario.py', bindings={})))
    with pytest.raises(ValueError, match='not in the top-level database'):
        generate(db, soc, tmp_path / 'bench', adapter=adapter)
    assert not (tmp_path / 'bench').exists()
