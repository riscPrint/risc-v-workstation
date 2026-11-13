import json
import sqlite3
import pytest
from lint_builder import Builder
from rvw.soc.mbist import requirements

pytestmark=pytest.mark.fast


def test_requirements(tmp_path):
    b=Builder(tmp_path/'design.db')
    b.sig('test_enable',direction='in')
    b.sig('ram',kind='mem',width=32)
    db=b.done()
    with sqlite3.connect(db) as c:
        sid=c.execute("SELECT id FROM signals WHERE path='ram'").fetchone()[0]
        c.execute("INSERT INTO memories(id,signal_id,component_id,name,path,width,depth) VALUES(1,?,1,'ram','ram',32,256)",(sid,))
    req=dict(path='ram',width=32,depth=256,test_enable='test_enable',functional_value=0,repair=[],isolation_connections=[])
    spec=dict(schema='rvw.soc-mbist/1',memories=[req])
    src=tmp_path/'requirements.json';src.write_text(json.dumps(spec))
    result=requirements(db,src,tmp_path/'out.json')
    assert result['status']=='inconclusive'
    assert result['memories'][0]['isolation_status']=='not_run'
    req['width']=64;src.write_text(json.dumps(spec))
    with pytest.raises(ValueError,match='dimensions'):requirements(db,src,tmp_path/'bad.json')
