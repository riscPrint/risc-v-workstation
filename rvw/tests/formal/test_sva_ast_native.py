from argparse import Namespace
import json
import os
from pathlib import Path
import shutil

import pytest

from rvw.formal.sva_ast import run


def native_plugin():
    yosys=shutil.which('yosys')
    if not yosys:
        pytest.skip('Yosys required')
    plugin=Path(os.environ.get('RVW_SLANG') or Path(yosys).absolute().parent.parent/'share/yosys/plugins/slang.so')
    if not plugin.is_file():
        pytest.skip('native Slang plugin required')
    return plugin


CASES=[
    ('unbounded composition','assert property (@(posedge clk) strong(a[->1:3] intersect b[*1:$]));','Intersect'),
    ('local capture liveness','property p; logic saved; @(posedge clk) (a,saved=b) |-> s_eventually(c && saved); endproperty assert property(p);','SEventually'),
    ('multi-clock','assert property (@(posedge clk) a |=> @(posedge other) b);','NonOverlappedImplication'),
    ('within and first_match','assert property (@(posedge clk) strong(first_match(a ##[1:3] b) within c[*1:8]));','Within'),
    ('property arguments','property p(logic x,logic y); @(posedge clk) x |=> y; endproperty assert property(p(a,b));','NonOverlappedImplication'),
    ('default clocking','default clocking cb @(posedge clk); endclocking assert property(a |=> b);','NonOverlappedImplication'),
]


@pytest.mark.parametrize('feature,statements,operator',CASES)
def test_native_typed_grammar(tmp_path,feature,statements,operator):
    plugin=native_plugin()
    source=tmp_path/'m.sv'
    source.write_text('module m(input clk,other,a,b,c); '+statements+' endmodule')
    out=tmp_path/'out'
    code=run(Namespace(verilog=[str(source)],top='m',out=str(out),plugin=str(plugin),timeout=20))
    result=json.loads((out/'result.json').read_text())
    assert result['status'] in ('parsed','inconclusive'),result
    assert result['proof_status']==result['lowering_status']=='not_run'
    assert len(result['properties'])==1
    assert result['operators'][operator]>=1,(feature,result)
    if result['input_closure']['status']!='verified':
        assert result['status']=='inconclusive' and code==1
    else:
        assert code==0
    assert (out/'ast.json').is_file()
    assert result['compiler_capture']['files']


def test_native_invalid_source(tmp_path):
    plugin=native_plugin()
    source=tmp_path/'m.sv'
    source.write_text('module m(input clk); assert property (@(posedge clk) missing); endmodule')
    out=tmp_path/'out'
    assert run(Namespace(verilog=[str(source)],top='m',out=str(out),plugin=str(plugin),timeout=20))==1
    result=json.loads((out/'result.json').read_text())
    assert result['status']=='error' and result['cause']=='native_compilation_failed'
    assert not (out/'ast.json').exists()


def test_native_no_checks(tmp_path):
    plugin=native_plugin()
    source=tmp_path/'m.sv'
    source.write_text('module m(input clk,a); endmodule')
    out=tmp_path/'out'
    run(Namespace(verilog=[str(source)],top='m',out=str(out),plugin=str(plugin),timeout=20))
    result=json.loads((out/'result.json').read_text())
    assert result['status']=='no_checks'



def test_native_checker_bind_and_include_capture(tmp_path):
    plugin=native_plugin()
    header=tmp_path/'check.svh'
    header.write_text('checker ch(input logic clk,a,b); '
                      'assert property (@(posedge clk) a |-> ##[1:$] b); endchecker')
    source=tmp_path/'m.sv'
    source.write_text('`include "check.svh"\nmodule m(input clk,a,b); endmodule\n'
                      'bind m ch monitor(.clk(clk),.a(a),.b(b));')
    out=tmp_path/'out'
    run(Namespace(verilog=[str(source)],top='m',out=str(out),plugin=str(plugin),timeout=20))
    result=json.loads((out/'result.json').read_text())
    assert result['status'] in ('parsed','inconclusive'),result
    assert len(result['properties'])==1
    assert len(result['input_snapshot']['files'])==2
    assert result['node_kinds']['CheckerInstance']>=1
