import json
import shutil
import pytest
from rvw.common.proc import run_group
from rvw.checks.streams import generate
from lint_builder import Builder


def inputs(tmp_path):
    path=tmp_path/'db.sqlite';b=Builder(path)
    b.domain(1,reset='reset',kind='SYNC')
    b.sig('clk',direction='in');b.sig('reset',direction='in')
    b.sig('v',direction='in',domain=1);b.sig('r',direction='out',domain=1)
    b.sig('data',direction='in',width=8,domain=1)
    b.done()
    report=dict(schema='rvw.checks/1',channels=[dict(kind='Stream',path='',object='tx',valid='v',ready='r',payload=['data'])])
    return path,report


def test_reviewed_stream_has_instance_binding(tmp_path):
    db,report=inputs(tmp_path)
    result=generate(db,report,{'tx':dict(stable=True)},tmp_path/'out')
    assert result['status']=='generated' and result['complete']
    assert result['channels'][0]['ports']==dict(clk=1,reset=1,v=1,r=1,data=8)
    assert 'bind Top rvw_channel_0' in (tmp_path/'out/binds.sv').read_text()


def test_unreviewed_stream_cannot_pass(tmp_path):
    db,report=inputs(tmp_path)
    result=generate(db,report,{},tmp_path/'out')
    assert result['status']=='no_checks'
    assert 'stable=true' in result['channels'][0]['reason']


def test_flow_needs_a_range_contract(tmp_path):
    db,report=inputs(tmp_path)
    report['channels'][0].update(kind='Flow',ready=None)
    result=generate(db,report,{'tx':dict(max_value=15)},tmp_path/'out')
    assert result['status']=='generated'
    assert 'rvw_prev' not in (tmp_path/'out/monitors.sv').read_text()
    bad=generate(db,report,{},tmp_path/'bad')
    assert bad['status']=='no_checks'


@pytest.mark.slow
def test_native_stream_bind_elaborates(tmp_path):
    tool=shutil.which('verilator')
    if not tool: pytest.skip('Verilator required')
    db,report=inputs(tmp_path)
    generate(db,report,{'tx':dict(stable=True)},tmp_path/'out')
    top=tmp_path/'top.sv'
    top.write_text('module Top(input clk,reset,v,r,input [7:0] data); endmodule\n')
    r=run_group(['nice','-n','10',tool,'--lint-only','-Wno-fatal','--top-module','Top',
        str(top),str(tmp_path/'out/monitors.sv'),str(tmp_path/'out/binds.sv')],capture=True,timeout=15)
    assert r.returncode==0,r.stdout+r.stderr
