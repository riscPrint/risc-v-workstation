import json
from pathlib import Path
from rvw.formal.bus_bindings import generate
from lint_builder import Builder


def database(path, domain=True, multiselect=False):
    db = Builder(path)
    db.c.execute("UPDATE components SET module='Top'")
    db.domain(1, reset='reset', kind='SYNC')
    db.sig('clk',direction='in'); db.sig('reset',direction='in')
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
    db.sig('clk',direction='in'); db.sig('reset',direction='in')
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


def test_axi4_five_channels_bind(tmp_path):
    from test_typed_bus_checks import fields
    path=tmp_path/'axi.db'
    db=Builder(path)
    db.domain(1, reset='reset', kind='SYNC')
    db.sig('clk',direction='in');db.sig('reset',direction='in')
    db.c.execute("INSERT INTO bundles(id,component_id,path,class_name) VALUES(1,1,'io.bus','Axi4')")
    for key,row in fields('axi4').items():
        name='io_bus_'+row[0]
        db.sig(name,width=row[3],domain=1)
        db.c.execute('UPDATE signals SET spinal_path=? WHERE name=?',('io.bus.'+key,name))
    db.done()
    report=generate(path,tmp_path/'out')
    assert report['buses'][0]['status']=='generated'
    assert report['buses'][0]['coverage']=='channel_safety'
    assert report['complete'] is False
    assert len([k for k in report['buses'][0]['ports'] if k.endswith('_valid')])==5
    assert 'LAST' in report['buses'][0]['unbound_checks'][0]['reason']


def test_nested_bus_uses_its_own_controls(tmp_path):
    path=tmp_path/'nested.db'
    db=Builder(path)
    cid=db.component('child','Child')
    db.c.execute("UPDATE components SET module='Child' WHERE id=?",(cid,))
    db.domain(1,clock='child.clk',reset='child.reset',kind='SYNC')
    db.sig('child.clk',direction='in',comp='child');db.sig('child.reset',direction='in',comp='child')
    db.c.execute("INSERT INTO bundles(id,component_id,path,class_name) VALUES(1,?,'io.bus','Apb3')",(cid,))
    for key,width in dict(PSEL=1,PENABLE=1,PREADY=1,PADDR=8,PWRITE=1,PWDATA=8,PRDATA=8).items():
        name='io_bus_'+key
        db.sig('child.'+name,name=name,width=width,domain=1,comp='child')
        db.c.execute('UPDATE signals SET spinal_path=? WHERE name=?',('io.bus.'+key,name))
    db.done()
    report=generate(path,tmp_path/'out')
    assert report['buses'][0]['status']=='generated'
    assert report['buses'][0]['target']=='Child'
    assert report['buses'][0]['target_instance']=='Top.child'
    assert report['buses'][0]['bind_scope']=='unique_module'
    assert report['buses'][0]['ports']['clk']=='clk'


def test_full_axi_scoreboard_is_bound(tmp_path):
    from test_axi_transactions import fields
    path=tmp_path/'full.db';db=Builder(path)
    db.domain(1,reset='reset',kind='SYNC');db.sig('clk',direction='in');db.sig('reset',direction='in')
    db.c.execute("INSERT INTO bundles(id,component_id,path,class_name) VALUES(1,1,'io.bus','Axi4')")
    for key,row in fields().items():
        name='io_bus_'+row[0];db.sig(name,width=row[3],domain=1)
        db.c.execute('UPDATE signals SET spinal_path=? WHERE name=?',('io.bus.'+key,name))
    db.done()
    report=generate(path,tmp_path/'out',depth=2,max_beats=4)
    row=report['buses'][0]
    assert row['coverage']=='transaction_safety' and row['tracker_depth']==2
    assert 'rvw_rpresent' in (tmp_path/'out/monitors.sv').read_text()
    assert 'response_lock' in row['check_groups']
    assert 'write_strobes' in row['check_groups']
    assert row['write_history_beats']==4
    assert report['complete'] is True


def test_tracker_bounds_are_explicit(tmp_path):
    import pytest
    for kwargs in ({'depth':0},{'max_beats':0},{'max_beats':257}):
        with pytest.raises(ValueError,match=r'1\.\.'):
            generate(tmp_path/'unused.db',tmp_path/'out',**kwargs)


def test_explicit_clock_for_combinational_bus_ports(tmp_path):
    path=tmp_path/'design.db';database(path,domain=False)
    clocks=tmp_path/'clocks.json';clocks.write_text(json.dumps(dict(schema='rvw.bus-clocks/1',
        instances={'io.bus':dict(clock='clk',reset='reset')})))
    result=generate(path,tmp_path/'out',clocks=clocks)
    assert result['complete'] is True
    assert result['buses'][0]['clock_source']=='project'
    assert '.clk(clk)' in (tmp_path/'out/binds.sv').read_text()


def test_clock_declaration_cannot_override_recorded_domains(tmp_path):
    import sqlite3
    path=tmp_path/'design.db';database(path)
    c=sqlite3.connect(path)
    c.execute("INSERT INTO clock_domains(id,clock,reset,reset_kind,reset_active_high,clock_edge) VALUES(2,'other_clk','other_reset','SYNC','true','RISING')")
    c.commit();c.close()
    clocks=tmp_path/'clocks.json';clocks.write_text(json.dumps(dict(schema='rvw.bus-clocks/1',
        instances={'io.bus':dict(clock='other_clk',reset='other_reset')})))
    result=generate(path,tmp_path/'out',clocks=clocks)
    assert result['status']=='no_checks'
    assert 'contradicts' in result['buses'][0]['reason']


def test_unknown_clock_instance_stays_incomplete(tmp_path):
    path=tmp_path/'design.db';database(path)
    clocks=tmp_path/'clocks.json';clocks.write_text(json.dumps(dict(schema='rvw.bus-clocks/1',
        instances={'typo':dict(clock='clk',reset='reset')})))
    result=generate(path,tmp_path/'out',clocks=clocks)
    assert result['status']=='generated' and not result['complete']
    assert result['buses'][1]['kind']=='clock_binding'
    assert 'no matching bus instance' in result['buses'][1]['reason']
