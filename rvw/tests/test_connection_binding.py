"""Native internal observations without abstraction cuts."""
import shutil

import pytest

from rvw.formal.connection_binding import expose
from rvw.query.db import DesignDB


@pytest.mark.parametrize('width', [32,16])
def test_native_expose(gcd_db,tmp_path,width):
    if any(not shutil.which(t) for t in ('yosys','sby','yices-smt2')):
        pytest.skip('native Yosys/SBY/Yices required')
    rtl=tmp_path/'GCD.v'
    rtl.write_text(f'''module GCD(input clk,reset,io_loadValues,input [31:0] io_a,io_b,
output [31:0] io_result,output io_resultIsValid);
wire [{width-1}:0] x = io_a ^ 32'h1234;
assign io_result=x; assign io_resultIsValid=io_loadValues;
endmodule
''')
    db=DesignDB(gcd_db)
    rule=dict(kind='required',source='x',destination='io_result')
    try:
        if width != 32:
            with pytest.raises(ValueError,match='width differs'):
                expose(db,rule,[rtl],tmp_path/'binding',10)
            return
        files,ports,identity=expose(db,rule,[rtl],tmp_path/'binding',10)
        assert ports['rvw_conn_observe_0'].width==32
        assert identity['bindings']==[dict(signal='x',port='rvw_conn_observe_0',width=32)]
        assert len(identity['derived_sha256'])==64
        from rvw.formal.apps import flow
        wrapper=tmp_path/'oracle.sv'
        wrapper.write_text('''module oracle(input clk,reset,input [31:0] a);
wire [31:0] observed,result; wire valid;
GCD dut(.clk(clk),.reset(reset),.io_a(a),.io_b(32'b0),.io_loadValues(1'b1),
.io_result(result),.io_resultIsValid(valid),.rvw_conn_observe_0(observed));
always @(posedge clk) if(!reset) begin
assert(observed == (a ^ 32'h1234)); assert(result == observed);
end
endmodule
''')
        result=flow([*files,wrapper],'oracle','clk','reset',tmp_path/'proof',4,'smtbmc:yices',10)
        assert result['status']=='pass'
    finally:
        db.close()


def test_internal_forbidden_refused(gcd_db,tmp_path):
    db=DesignDB(gcd_db)
    try:
        with pytest.raises(ValueError,match='state-coupling'):
            expose(db,dict(kind='forbidden',source='x',destination='io_result'),[],tmp_path/'binding',1)
    finally:
        db.close()


@pytest.mark.parametrize('internal_source,latency,wrong', [(True,0,False),(True,1,False),(True,0,True),(False,0,False)])
def test_native_internal_campaign(gcd_db,tmp_path,internal_source,latency,wrong):
    import hashlib
    import json
    import sqlite3
    from rvw.cli import main
    if any(not shutil.which(t) for t in ('yosys','sby','yices-smt2')):
        pytest.skip('native Yosys/SBY/Yices required')
    path=tmp_path/'design.db';shutil.copyfile(gcd_db,path)
    rtl=tmp_path/'GCD.v'
    rhs='x ^ 1' if wrong else 'x'
    output = (f'always @(posedge clk) if(reset) io_result <= 0; else io_result <= {rhs};' if latency else f'always @* io_result = {rhs};')
    rtl.write_text('''module GCD(input clk,reset,io_loadValues,input [31:0] io_a,io_b,
output reg [31:0] io_result,output io_resultIsValid);
wire [31:0] x = io_a;
assign io_resultIsValid=io_loadValues;
''' + output + '\nendmodule\n')
    with sqlite3.connect(path) as db:
        db.execute('DELETE FROM rtl_files')
        db.execute('INSERT INTO rtl_files VALUES (?)',(str(rtl),))
        db.execute('INSERT INTO input_files VALUES (?, ?, ?, ?, ?)',
                   (str(rtl),str(rtl.resolve()),hashlib.sha256(rtl.read_bytes()).hexdigest(),rtl.stat().st_size,'{}'))
    table=tmp_path/'connections.json'
    table.write_text(json.dumps({'connection':[dict(id='internal',kind='required',source='x' if internal_source else 'io_a',
                                                    destination='io_result' if internal_source else 'x',latency=latency,mode='io_resultIsValid')]}))
    out=tmp_path/'report'
    assert main(['formal','connectivity',str(table),'--db',str(path),'--out',str(out),'--run',
                 '--proof-mode','prove','--depth','6','--timeout','10'])==1
    report=json.loads((out/'result.json').read_text())
    row=report['connections'][0]
    assert row['semantic_status']==('contradicted' if wrong else 'proven'),row
    assert row['campaign']['binding']['bindings'][0]['signal']=='x'
    assert row['campaign']['observations']['activation']['status']=='fail'
    assert report['status']=='incomplete'


@pytest.mark.parametrize('wrong', [False, True])
def test_source_cut_native_contract(gcd_db, tmp_path, wrong):
    import hashlib
    import json
    import sqlite3
    from rvw.soc.connection_run import run_cut
    if any(not shutil.which(t) for t in ('yosys','sby','yices-smt2')):
        pytest.skip('native Yosys/SBY/Yices required')
    path = tmp_path/'design.db'
    shutil.copyfile(gcd_db,path)
    rtl = tmp_path/'GCD.v'
    rtl.write_text("module GCD(input clk,reset,io_loadValues,input [31:0] io_a,io_b,\n"
                   "output [31:0] io_result,output io_resultIsValid);\n"
                   "wire [31:0] x = io_a; assign io_result = x" + (" ^ 1" if wrong else "") +
                   "; assign io_resultIsValid=io_loadValues;\nendmodule\n")
    with sqlite3.connect(path) as db:
        db.execute('DELETE FROM rtl_files')
        db.execute('INSERT INTO rtl_files VALUES (?)',(str(rtl),))
        db.execute('INSERT INTO input_files VALUES (?, ?, ?, ?, ?)',
                   (str(rtl),str(rtl.resolve()),hashlib.sha256(rtl.read_bytes()).hexdigest(),rtl.stat().st_size,'{}'))
    manifest = tmp_path/'connections.json'
    manifest.write_text(json.dumps(dict(connection=[dict(id='wire',kind='required',source='x',destination='io_result')])))
    report = run_cut(path,manifest,tmp_path/'out',timeout=10)
    assert report['status'] == ('fail' if wrong else 'proven'), report
