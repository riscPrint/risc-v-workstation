import ast
import json
import shutil
import sqlite3
import pytest
from rvw.common.hdl_ports import load,checks
from rvw.vip.catalog import buses,skeleton
from rvw.vip.ready_valid import Monitor

pytestmark=pytest.mark.fast


@pytest.fixture
def declared(gcd_db,tmp_path):
    db=tmp_path/'plain.db';shutil.copyfile(gcd_db,db)
    with sqlite3.connect(db) as c:
        top=c.execute('SELECT module FROM components WHERE parent_id IS NULL').fetchone()[0]
        c.execute('DELETE FROM bundles')
        for i,(name,width) in enumerate([('clock',1),('rst_n',1),('req_valid',1),('req_ready',1),('request',32)]):
            c.execute('INSERT INTO signals(id,component_id,name,path,kind,width,direction,pruned) VALUES(?,1,?,?,?,?,?,0)',
                      (10000+i,name,name,'Bits',width,'in'))
    spec=dict(schema='rvw.hdl-ports/1',top=top,clock='clock',reset=dict(signal='rst_n',active=0),
              buses=[dict(name='request_bus',protocol='ready_valid',ports=dict(valid='req_valid',ready='req_ready',payload=['request']))])
    path=tmp_path/'ports.json';path.write_text(json.dumps(spec))
    return db,path


def test_declared_channel_has_no_spinal_types(declared,tmp_path):
    db,path=declared
    assert load(db,path)['buses'][0]['payload_width']==32
    assert buses(db,port_map=path)['buses'][0]['protocol']=='ready_valid'
    result=checks(db,path,tmp_path/'checks')
    assert result['status']=='generated'
    assert '.reset(~rst_n)' in (tmp_path/'checks/binds.sv').read_text()
    assert 'assert(payload == previous_payload)' in (tmp_path/'checks/monitors.sv').read_text()
    target=tmp_path/'bench.py';result=skeleton(db,target,port_map=path)
    assert result['status']=='skeleton'
    ast.parse(target.read_text())
    assert 'checks > 0' in target.read_text()


def test_bad_declared_port_is_refused(declared):
    db,path=declared
    spec=json.loads(path.read_text());spec['buses'][0]['ports']['ready']='absent';path.write_text(json.dumps(spec))
    with pytest.raises(ValueError,match='absent'):load(db,path)


def test_monitor_refuses_stall_change():
    monitor=Monitor();monitor.sample(1,0,(0x1234,))
    with pytest.raises(AssertionError):monitor.sample(1,1,(0x1235,))
    monitor.sample(0,0,(),reset=True);monitor.sample(1,1,(42,))
    assert monitor.transfers==1


def test_declared_uvm_skeleton(declared,tmp_path):
    from rvw.uvm.scaffold import generate
    from rvw.sim.cocotb import load as load_bench
    db,path=declared
    source=tmp_path/'top.v';source.write_text('module top; endmodule')
    from pathlib import Path
    soc=Path(__file__).resolve().parents[2]/'Uvm/examples/soc/map.json'
    result=generate(db,soc,tmp_path/'uvm',rtl=[source],port_map=path)
    assert result['status']=='skeleton' and result['scenario_required']
    assert load_bench(Path(result['manifest']))['test_module']=='test_generated'
    ast.parse((tmp_path/'uvm/test_generated.py').read_text())
    assert 'NotImplementedError' in (tmp_path/'uvm/scenario.py').read_text()


def test_declared_request_response(declared,tmp_path):
    db,path=declared
    spec=json.loads(path.read_text())
    bus=spec['buses'][0];bus['protocol']='req_rsp'
    bus['ports']=dict(request='req_valid',response='req_ready',payload=['request'])
    path.write_text(json.dumps(spec))
    result=checks(db,path,tmp_path/'checks')
    assert result['buses'][0]['kind']=='req_rsp'
    source=(tmp_path/'checks/monitors.sv').read_text()
    assert 'if(response) assert(pending || request)' in source
    assert 'if(request) assert(!pending || response)' in source
    assert '.response(req_ready)' in (tmp_path/'checks/binds.sv').read_text()
    # Existing ready/valid agents must not silently reinterpret pulse protocols.
    with pytest.raises(ValueError,match='unsupported declared protocol'):
        skeleton(db,tmp_path/'bench.py',port_map=path)


def test_declared_request_ack_uses_stability(declared,tmp_path):
    db,path=declared
    spec=json.loads(path.read_text());bus=spec['buses'][0]
    bus.update(protocol='req_ack',ports=dict(request='req_valid',response='req_ready',payload=['request']))
    path.write_text(json.dumps(spec))
    checks(db,path,tmp_path/'checks')
    assert '.ready(req_ready)' in (tmp_path/'checks/binds.sv').read_text()
    assert 'assert(payload == previous_payload)' in (tmp_path/'checks/monitors.sv').read_text()


def test_explicit_emitted_module_name(declared,tmp_path):
    db,path=declared
    spec=json.loads(path.read_text());spec['rtl_top']='EmittedTop';path.write_text(json.dumps(spec))
    checks(db,path,tmp_path/'checks')
    assert (tmp_path/'checks/binds.sv').read_text().startswith('bind EmittedTop ')
    spec['rtl_top']='bad; module';path.write_text(json.dumps(spec))
    with pytest.raises(ValueError,match='rtl_top'):load(db,path)
