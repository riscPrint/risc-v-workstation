import json
from pathlib import Path
from rvw.formal.bus_bindings import generate
from lint_builder import Builder


def database(path, domain=True, multiselect=False):
    db = Builder(path)
    db.c.execute("UPDATE components SET module='Top'")
    db.domain(1, reset='reset', kind='SYNC')
    db.c.execute("INSERT INTO bundles(id,component_id,path,class_name) VALUES(1,1,'io.bus','Apb3')")
    widths = dict(PSEL=2 if multiselect else 1,PENABLE=1,PREADY=1,PADDR=8,PWRITE=1,PWDATA=8,PRDATA=8)
    for field,width in widths.items():
        db.sig('io_bus_'+field,width=width,domain=1 if domain else None)
        db.c.execute('UPDATE signals SET spinal_path=? WHERE name=?',('io.bus.'+field,'io_bus_'+field))
    db.c.commit()
    db.c.close()


def test_typed_apb_binds_without_port_map(tmp_path):
    path = tmp_path/'design.db'
    database(path)
    result = generate(path,tmp_path/'out')
    assert result['status'] == 'generated'
    assert result['buses'][0]['width'] == 17
    text = (tmp_path/'out/binds.sv').read_text()
    assert 'bind Top rvw_bus_1' in text
    assert '.select(io_bus_PSEL)' in text
    assert '.clk(clk)' in text
    assert '.reset(reset)' in text
    assert '.request({io_bus_PADDR, io_bus_PWDATA, io_bus_PWRITE})' in text
    assert json.loads((tmp_path/'out/result.json').read_text())['buses'] == result['buses']


def test_missing_clock_is_no_checks(tmp_path):
    path = tmp_path/'design.db'
    database(path,domain=False)
    result = generate(path,tmp_path/'out')
    assert result['status'] == 'no_checks'
    assert 'clock domain' in result['buses'][0]['reason']


def test_multiselect_refused(tmp_path):
    path = tmp_path/'design.db'
    database(path,multiselect=True)
    result = generate(path,tmp_path/'out')
    assert result['status'] == 'no_checks'
    assert 'width for PSEL' in result['buses'][0]['reason']


def test_child_and_clock_enable_are_refused(tmp_path):
    path = tmp_path/'design.db'
    database(path)
    import sqlite3
    c = sqlite3.connect(path)
    c.execute("UPDATE clock_domains SET clock_enable='enable'")
    c.commit(); c.close()
    result = generate(path,tmp_path/'out')
    assert result['status'] == 'no_checks'
    assert 'clock-enable' in result['buses'][0]['reason']


def test_empty_database_has_no_checks(tmp_path):
    path = tmp_path/'design.db'
    db = Builder(path)
    db.c.commit(); db.c.close()
    result = generate(path,tmp_path/'out')
    assert result['status'] == 'no_checks'
    assert result['complete'] is False


def test_recorded_stream_payload_type_and_parent(tmp_path):
    path=tmp_path/'axis.db'
    db=Builder(path)
    db.domain(1,reset='reset',kind='SYNC')
    db.c.execute("INSERT INTO bundles(id,component_id,path,class_name) VALUES(10,1,'io.tx','Stream')")
    db.c.execute("INSERT INTO bundles(id,component_id,parent_id,path,class_name) VALUES(11,1,10,'io.tx.payload','Axi4StreamBundle')")
    for field,width in [('valid',1),('ready',1),('payload.data',8),('payload.last',1)]:
        name='io_tx_'+field.replace('.','_')
        db.sig(name,width=width,domain=1)
        db.c.execute('UPDATE signals SET spinal_path=? WHERE name=?',('io.tx.'+field,name))
    db.c.commit();db.c.close()
    result=generate(path,tmp_path/'out')
    assert result['status']=='generated'
    assert len(result['buses'])==1
    row=result['buses'][0]
    assert row['path']=='io.tx'
    assert row['width']==9
    assert row['ports']['payload']=='{io_tx_payload_data, io_tx_payload_last}'
    assert row['ports']['valid']=='io_tx_valid'
