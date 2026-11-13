import json
from pathlib import Path
import shutil
import sqlite3
import sys
import pytest
from rvw.sec.security_fault import run
pytestmark=pytest.mark.slow


@pytest.mark.parametrize('protected',[True,False])
def test_critical_register_upset(tmp_path,protected):
    if not shutil.which('verilator'):pytest.skip('Verilator required')
    db=tmp_path/'design.db'
    with sqlite3.connect(db) as c:
        c.executescript("create table meta(key,value);insert into meta values('schema','rvw.designdb/20');create table signals(path,width,kind);insert into signals values('unit.key',8,'reg');")
    (tmp_path/'mode').write_text('protected' if protected else 'leaky')
    plan=dict(db='design.db',elf='mode',critical_registers=['unit.key'],observations=['debug_bus'],samples=1,
              window=[0,1],adapter_command=[sys.executable,str(Path(__file__).parent/'fixtures/sec/fault_adapter.py')],
              detections={'mechanisms':['key_parity']})
    (tmp_path/'plan.json').write_text(json.dumps(plan))
    result=run(tmp_path/'plan.json',tmp_path/'out')
    assert result['status']==('no_leak_observed' if protected else 'violation'),result
