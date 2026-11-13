import ast
import json
import sqlite3
import shutil
import pytest
from rvw.vip.catalog import agents,buses,skeleton
from rvw.vip.mcp_tools import mcp_tools
from rvw.cli import main
from rvw.query.db import QueryError


@pytest.fixture
def typed_db(gcd_db,tmp_path):
    copied=tmp_path/"design.db"
    shutil.copyfile(gcd_db,copied)
    gcd_db=copied
    with sqlite3.connect(gcd_db) as db:
        db.execute("INSERT INTO bundles(id,component_id,path,class_name) VALUES(999,1,'io.bus','spinal.lib.bus.amba4.apb.Apb4')")
        from rvw.vip.apb import Pins
        for i,name in enumerate(Pins.__dataclass_fields__):
            if name=='reset_n': continue
            db.execute('INSERT INTO signals(id,component_id,name,path,spinal_path,kind,width) VALUES(?,1,?,?,?,?,32)',
                       (10000+i,name,'io_bus_'+name,'io.bus.'+name,'Bits'))
    return gcd_db


def test_inventory_cli_and_mcp(capsys):
    assert len(agents()['agents'])==20
    assert main(['vip','list'])==0
    assert json.loads(capsys.readouterr().out)==agents()
    assert {t.name for t in mcp_tools()}=={'vip_list','vip_buses','vip_bench'}


def test_bound_skeleton(typed_db,tmp_path):
    assert buses(typed_db)['buses']==[dict(path='io.bus',spinal_type='spinal.lib.bus.amba4.apb.Apb4',agent='apb')]
    target=tmp_path/'bench.py'
    result=skeleton(typed_db,target,clock='clock',reset='rst_n')
    assert result['status']=='skeleton'
    assert result['bindings']['paddr']=='io_bus_paddr'
    assert result['bindings']['clk']=='clock'
    ast.parse(target.read_text())
    assert "CocotbAgent(view)" in target.read_text()
    assert 'NotImplementedError' in target.read_text()
    with pytest.raises(FileExistsError): skeleton(typed_db,target)


def test_missing_type_and_pin(typed_db,tmp_path):
    with pytest.raises(QueryError,match='exactly one'): skeleton(typed_db,tmp_path/'no.py',bus='unknown')
    with sqlite3.connect(typed_db) as db: db.execute("DELETE FROM signals WHERE name='paddr'")
    with pytest.raises(QueryError,match='missing required'): skeleton(typed_db,tmp_path/'no.py')
    assert not (tmp_path/'no.py').exists()


def test_uart_uses_named_serial_handles(typed_db,tmp_path):
    with sqlite3.connect(typed_db) as db:
        db.execute("UPDATE bundles SET class_name='spinal.lib.com.uart.Uart' WHERE id=999")
        db.execute("UPDATE signals SET name='txd',path='io_bus_txd',spinal_path='io.bus.txd' WHERE name='paddr'")
        db.execute("UPDATE signals SET name='rxd',path='io_bus_rxd',spinal_path='io.bus.rxd' WHERE name='prdata'")
    target=tmp_path/'uart_bench.py';report=skeleton(typed_db,target)
    assert report['bindings']['tx']=='io_bus_txd'
    assert report['bindings']['rx']=='io_bus_rxd'
    assert 'CocotbAgent(view)' in target.read_text()
