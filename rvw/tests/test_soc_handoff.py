import hashlib
import json
import sqlite3
from pathlib import Path
import pytest
from lint_builder import Builder
from rvw.soc.handoff import export

pytestmark=pytest.mark.fast


def design(tmp_path):
    b=Builder(tmp_path/'design.db')
    b.domain(1,clock='clk')
    b.sig('clk',direction='in',role='clock')
    b.reg('state',1)
    db=b.done()
    rtl=tmp_path/'top.v'
    rtl.write_text('module top(input clk); endmodule\n')
    with sqlite3.connect(db) as c:
        c.execute('INSERT INTO rtl_files VALUES(?)',(str(rtl),))
        c.execute('INSERT INTO input_files VALUES(?,?,?,?,?)',(str(rtl),str(rtl),hashlib.sha256(rtl.read_bytes()).hexdigest(),rtl.stat().st_size,'{}'))
    return db,rtl


def test_export(tmp_path):
    db,rtl=design(tmp_path)
    result=export(db,tmp_path/'out',{'sdc':{'clocks':{'clk':{'period_ns':10}}}})
    assert result['status']=='exported'
    assert 'create_clock' in (tmp_path/'out/constraints.sdc').read_text()
    assert (tmp_path/'out/inputs/0000/top.v').read_bytes()==rtl.read_bytes()
    assert 'inputs/0000/top.v' in (tmp_path/'out/files.f').read_text()
    assert (tmp_path/'out/mem_ports.json').exists()
    with pytest.raises(ValueError,match='must be new'):
        export(db,tmp_path/'out')


def test_refuse_stale_rtl(tmp_path):
    db,rtl=design(tmp_path)
    rtl.write_text('changed')
    with pytest.raises(ValueError,match='differs'):
        export(db,tmp_path/'out')
    assert not (tmp_path/'out').exists()
