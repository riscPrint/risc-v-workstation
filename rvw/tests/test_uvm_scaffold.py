import json
from pathlib import Path
import sqlite3
import importlib.util
import shutil
import pytest
from rvw.uvm.scaffold import generate, bus_type


def fixture(tmp_path):
    source=tmp_path/'top.sv'
    source.write_text('''module apb_regs(input clk,reset,input PSEL,PENABLE,PWRITE,
 input [31:0] PADDR,PWDATA,output PREADY,output [31:0] PRDATA,output PSLVERROR);
 assign PREADY=!reset; assign PRDATA=32'h42; assign PSLVERROR=PADDR!=32'h10000000;
 endmodule
'''.replace('PSLVERROR','PSLVERR'))
    db=tmp_path/'design.db'
    conn=sqlite3.connect(db)
    conn.executescript('''CREATE TABLE meta(key,value);
 INSERT INTO meta VALUES ('schema','rvw.designdb/20');
 CREATE TABLE components(id,parent_id,module);
 INSERT INTO components VALUES (1,NULL,'apb_regs');
 CREATE TABLE bundles(component_id,path,class_name);
 INSERT INTO bundles VALUES (1,'apb_regs.bus','spinal.lib.bus.amba3.apb.Apb3');
 CREATE TABLE signals(component_id,name,direction);
 CREATE TABLE clock_domains(clock,reset,reset_active_high);
 INSERT INTO clock_domains VALUES ('clk','reset',1);
 CREATE TABLE rtl_files(path);
 ''')
    conn.executemany('INSERT INTO signals VALUES (1,?,?)', [(p,'in' if p not in ('PREADY','PRDATA','PSLVERR') else 'out') for p in
        ('clk','reset','PSEL','PENABLE','PWRITE','PADDR','PWDATA','PREADY','PRDATA','PSLVERR')])
    conn.execute('INSERT INTO rtl_files VALUES (?)',(str(source),))
    conn.commit();conn.close()
    model=json.loads((Path(__file__).resolve().parents[2]/'Uvm/examples/soc/map.json').read_text())
    model['regions']=model['regions'][:2]
    model['regions'][1]['registers'][0]['reset']=0x42
    soc=tmp_path/'map.json';soc.write_text(json.dumps(model))
    return db,soc


def test_generated_bench_loads_and_selects_spinal_bus(tmp_path):
    from rvw.sim.cocotb import load
    db,soc=fixture(tmp_path)
    result=generate(db,soc,tmp_path/'bench')
    assert result['checks']==1 and result['agents'][0]['agent']=='apb'
    assert load(Path(result['manifest']))['top']=='apb_regs'
    compile((tmp_path/'bench/test_generated.py').read_text(),'generated','exec')
    with pytest.raises(FileExistsError):generate(db,soc,tmp_path/'bench')
    assert bus_type('spinal.lib.bus.amba4.axi.Axi4')=='axi'
    assert bus_type('unknown') is None


def test_unsupported_bus_is_explicit(tmp_path):
    db,soc=fixture(tmp_path)
    conn=sqlite3.connect(db)
    conn.execute("UPDATE bundles SET class_name='spinal.lib.bus.amba3.ahblite.AhbLite3'")
    conn.commit();conn.close()
    with pytest.raises(ValueError,match='APB bus'):
        generate(db,soc,tmp_path/'bench')
    assert not (tmp_path/'bench').exists()


def test_generated_native_reset_reads(tmp_path):
    if not shutil.which('verilator') or not importlib.util.find_spec('pyuvm'):
        pytest.skip('Verilator and pyuvm required')
    from rvw.sim.cocotb import run
    db,soc=fixture(tmp_path)
    result=generate(db,soc,tmp_path/'bench')
    report=run(Path(result['manifest']),tmp_path/'native',timeout=90)
    assert len(report['tests'])==1
    assert report['tests'][0]['status']=='pass'
