"""Database profiles select existing support and refuse unbound success."""
import asyncio
import json
import sqlite3
from pathlib import Path
import pytest
from rvw.uvm.profiles import generate, classify
from test_uvm_scaffold import fixture

pytestmark = pytest.mark.fast

CLASSES = {'cpu':'spinal.lib.Rvfi','apb':'spinal.lib.bus.amba3.apb.Apb3',
 'axi':'spinal.lib.bus.amba4.axi.Axi4','axi-lite':'spinal.lib.bus.amba4.axilite.AxiLite4',
 'tilelink':'spinal.lib.bus.tilelink.Bus','axis':'spinal.lib.bus.amba4.axis.Axi4Stream',
 'uart':'spinal.lib.com.uart.Uart','spi':'spinal.lib.com.spi.SpiMaster','i2c':'spinal.lib.com.i2c.I2c'}

@pytest.mark.parametrize('profile', CLASSES)
@pytest.mark.parametrize('language', ['pyuvm','sv'])
def test_database_profile_outputs(tmp_path, profile, language):
    from rvw.sim.cocotb import load as load_python
    from rvw.uvm.flow import load as load_sv
    db,soc=fixture(tmp_path)
    conn=sqlite3.connect(db)
    conn.execute('UPDATE bundles SET class_name=?',(CLASSES[profile],));conn.commit();conn.close()
    assert classify(CLASSES[profile])==profile
    report=generate(db,soc,tmp_path/'out',language=language)
    assert report['profile']==profile and report['scenario_required']
    config=json.loads((tmp_path/'out/bindings.json').read_text())
    assert config['ports'] and config['clock_domains']
    manifest=Path(report['manifest'])
    (load_python if language=='pyuvm' else load_sv)(manifest)
    if language=='pyuvm':
        compile((tmp_path/'out/test_generated.py').read_text(),'generated','exec')
        scope={};exec((tmp_path/'out/scenario.py').read_text(),scope)
        with pytest.raises(RuntimeError,match='PROJECT_SCENARIO_REQUIRED'):
            asyncio.run(scope['run'](None))
    else:
        assert 'PROJECT_SCENARIO_REQUIRED' in (tmp_path/'out/project_scenario.svh').read_text()
    with pytest.raises(FileExistsError): generate(db,soc,tmp_path/'out',language=language)


def test_multiple_buses_need_explicit_selection(tmp_path):
    db,soc=fixture(tmp_path)
    conn=sqlite3.connect(db)
    conn.execute('INSERT INTO bundles VALUES (1,?,?)',('top.serial',CLASSES['uart']));conn.commit();conn.close()
    with pytest.raises(ValueError,match='select one database bus'):
        generate(db,soc,tmp_path/'ambiguous')
    assert not (tmp_path/'ambiguous').exists()
    assert generate(db,soc,tmp_path/'selected',profile='uart')['profile']=='uart'


def test_cli_accepts_profile_options(tmp_path):
    from rvw.cli import main
    db,soc=fixture(tmp_path)
    assert main(['uvm','new','--db',str(db),'--soc',str(soc),'--out',str(tmp_path/'bench'),
                 '--language','sv','--profile','apb'])==0
