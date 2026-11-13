"""A forbidden influence check must witness distinct legal source values."""
import hashlib
import json
import shutil
import sqlite3

import pytest

from rvw.cli import main


@pytest.mark.parametrize('fixed_source,latency', [(True,0),(True,1),(False,0),(False,1)])
def test_native_distinct_source_activation(gcd_db,tmp_path,fixed_source,latency):
    if any(not shutil.which(t) for t in ('yosys','sby','yices-smt2')):
        pytest.skip('native Yosys/SBY/Yices required')
    path=tmp_path/'design.db';shutil.copyfile(gcd_db,path)
    rtl=tmp_path/'GCD.v'
    rtl.write_text('''module GCD(input clk,reset,io_loadValues,input [31:0] io_a,io_b,
output [31:0] io_result,output io_resultIsValid);
assign io_result=io_b; assign io_resultIsValid=io_loadValues;
''' + ('always @* assume(io_a == 0);\n' if fixed_source else '') + 'endmodule\n')
    with sqlite3.connect(path) as db:
        db.execute('DELETE FROM rtl_files')
        db.execute('INSERT INTO rtl_files VALUES (?)',(str(rtl),))
        db.execute('INSERT INTO input_files VALUES (?, ?, ?, ?, ?)',
                   (str(rtl),str(rtl.resolve()),hashlib.sha256(rtl.read_bytes()).hexdigest(),rtl.stat().st_size,'{}'))
    table=tmp_path/'connections.json'
    table.write_text(json.dumps({'connection':[dict(id='isolation',kind='forbidden',source='io_a',destination='io_result',
                                                    latency=latency,enable='io_loadValues')]}))
    out=tmp_path/'report'
    assert main(['formal','connectivity',str(table),'--db',str(path),'--out',str(out),'--run',
                 '--proof-mode','prove','--depth','6','--timeout','10'])==1
    report=json.loads((out/'result.json').read_text())
    row=report['connections'][0]
    assert row['campaign']['observations']['transfer']['status']=='pass'
    assert row['campaign']['observations']['activation']['status']==('pass' if fixed_source else 'fail')
    assert row['semantic_status']==('incomplete' if fixed_source else 'proven')
