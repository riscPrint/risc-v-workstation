import json
import shutil
from argparse import Namespace
import pytest
from rvw.formal.shortest import search, run
from rvw.common.proc import run_group


def test_increasing_depth_and_shortest_certificate():
    report = search(5, lambda d: {'status': 'fail' if d == 3 else 'pass'})
    assert report['depth'] == 3 and report['shortest']
    assert [r['depth'] for r in report['attempts']] == [1, 2, 3]


def test_unknown_and_bounded_pass_cannot_certify_shortest():
    assert search(5, lambda d: {'status': 'unknown'})['status'] == 'inconclusive'
    report = search(3, lambda d: {'status': 'pass'})
    assert report['status'] == 'inconclusive' and not report['shortest']


def test_native_shortest(tmp_path):
    if not all(shutil.which(t) for t in ('yosys', 'sby', 'z3')):
        pytest.skip('native formal tools required')
    root = tmp_path / 'run'
    (root / 'sby/model').mkdir(parents=True)
    rtl = tmp_path / 'top.v'
    rtl.write_text('module top(input clk); reg [2:0] count=0; always @(posedge clk) count<=count+1; always @* assert(count<2); endmodule')
    il = root / 'sby/model/design.il'
    proc = run_group(['yosys', '-Q', '-T', '-p', f'read_verilog -formal {rtl}; prep -top top; write_rtlil {il}'], capture=True, timeout=10)
    assert proc.returncode == 0
    (root / 'result.json').write_text(json.dumps(dict(schema='rvw.formal/1', assertions=1, flow='bmc', top='original')))
    out = tmp_path / 'out'
    assert run(Namespace(result=str(root), out=str(out), max_depth=5, timeout=30, engine='smtbmc:z3', json=False)) == 1
    report = json.loads((out / 'result.json').read_text())
    assert report['shortest'] and report['depth'] == 3


def test_native_multiple_properties(tmp_path):
    if not all(shutil.which(t) for t in ('yosys','sby','z3')):
        pytest.skip('native formal tools required')
    root=tmp_path/'run'; (root/'sby/model').mkdir(parents=True)
    rtl=tmp_path/'top.v'
    rtl.write_text('module top(input clk); reg [2:0] count=0; always @(posedge clk) count<=count+1; always @* begin early: assert(count<2); late: assert(count<4); end endmodule')
    il=root/'sby/model/design.il'
    proc=run_group(['yosys','-Q','-T','-p',f'read_verilog -formal -sv {rtl}; prep -top top; write_rtlil {il}'],capture=True,timeout=10)
    assert proc.returncode==0
    (root/'result.json').write_text(json.dumps({'schema':'rvw.formal/1','assertions':2,'flow':'bmc','top':'top'}))
    out=tmp_path/'out'
    run(Namespace(result=str(root),out=str(out),max_depth=5,timeout=50,engine='smtbmc:z3',json=False))
    report=json.loads((out/'result.json').read_text())
    assert sorted(r['depth'] for r in report['properties'])==[3,5]
    assert all(r['shortest'] for r in report['properties'])


def test_typed_output_missing_tool(tmp_path,monkeypatch):
    from rvw.formal.shortest import typed_output
    from rvw.common.capture import Capture
    monkeypatch.setattr(shutil,'which',lambda _:None)
    report=typed_output(tmp_path,tmp_path,'top',tmp_path,Capture(tmp_path/'capture'),1)
    assert report['status']=='inconclusive'


def test_native_typed_witness_export(tmp_path):
    from rvw.formal.shortest import typed_output
    from rvw.common.capture import Capture
    if not shutil.which('spinalwaves-check'):
        pytest.skip('spinalwaves-check required')
    engine=tmp_path/'witness/engine_0';engine.mkdir(parents=True)
    (engine/'trace.vcd').write_text('$timescale 1 ns $end\n$scope module top $end\n$var wire 3 ! count $end\n$upscope $end\n$enddefinitions $end\n#0\nb000 !\n#1\nb010 !\n')
    hgldd=tmp_path/'hgldd';hgldd.mkdir()
    (hgldd/'top.dd').write_text(json.dumps({'HGLDD':{'version':'1.0','file_info':['top.v']},'objects':[{'kind':'module','obj_name':'top','module_name':'top','port_vars':[{'var_name':'count','type_name':'logic','packed_range':[2,0],'source_lang_type_info':{'type_name':'UInt(3 bits)'},'value':{'sig_name':'count'}}],'children':[]}]}))
    out=tmp_path/'types';out.mkdir()
    report=typed_output(tmp_path/'witness',hgldd,'top',out,Capture(out/'inputs'),10)
    assert report['status']=='completed'
    assert (out/'typed.vcd').stat().st_size>0
