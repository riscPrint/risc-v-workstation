import json
import shutil
from types import SimpleNamespace
import pytest
from rvw.formal.security.policy import run

TOOLS = all(shutil.which(x) for x in ('yosys','sby','yosys-abc'))

@pytest.mark.skipif(not TOOLS, reason='needs native Yosys, SBY and ABC')
@pytest.mark.parametrize('leak,release', [(False,False),(True,False),(True,True)])
def test_secure_path_native(tmp_path,leak,release):
    rtl=tmp_path/'dut.v'
    rhs='(release ? secret : public)' if release else 'secret' if leak else 'public'
    rtl.write_text(f'module top(input clk,reset,secret,public,release, output reg sink); always @(posedge clk) sink <= reset ? 0 : {rhs}; endmodule')
    policy={'clock':'clk','reset':'reset','sources':['secret'],'sinks':['sink'],
            'adversary':'controls secret and public inputs','unmodeled_channels':['physical effects']}
    # A registered release must stay effective until its data leaves the sink.
    # This test deliberately exposes that a one-cycle release is insufficient.
    if release: policy['declassifier']='release'
    path=tmp_path/'policy.json';path.write_text(json.dumps(policy))
    out=tmp_path/'out'
    run(SimpleNamespace(rtl=str(rtl),top='top',policy=str(path),out=str(out),timeout=30))
    result=json.loads((out/'result.json').read_text())
    assert result['status']==('fail' if leak else 'pass'),result


def test_missing_threat_model_refused():
    from rvw.formal.security.policy import bind
    with pytest.raises(ValueError):
        bind({'modules':{'top':{'ports':{}}}},'top',{'clock':'clk','reset':'reset','sources':['secret'],'sinks':['sink']})

@pytest.mark.skipif(not TOOLS, reason='needs native Yosys, SBY and ABC')
@pytest.mark.parametrize('mutant', [False,True])
def test_static_isolation_policy(tmp_path,mutant):
    rtl=tmp_path/'dut.v'
    # A fixed 4-byte access must fit wholly inside the allowed interval.
    allowed="1'b1" if mutant else '(address>=16 && address<=28 && master==0 && privilege==1 && !write && !execute)'
    rtl.write_text(f'module top(input clk,reset,request,write,execute,input [1:0] privilege, input master,input [7:0] address,output grant); assign grant={allowed}; endmodule')
    policy={'kind':'isolation','clock':'clk','reset':'reset','access_bytes':4,
            'signals':{k:k for k in ('request','grant','write','execute','privilege','master','address')},
            'regions':[{'start':16,'end':32,'permissions':[{'master':0,'privilege':1,'read':True}]}],
            'adversary':'arbitrary requests from either master','unmodeled_channels':['physical effects','policy CSR updates']}
    path=tmp_path/'policy.json';path.write_text(json.dumps(policy));out=tmp_path/'out'
    run(SimpleNamespace(rtl=str(rtl),top='top',policy=str(path),out=str(out),timeout=30))
    result=json.loads((out/'result.json').read_text())
    assert result['status']==('fail' if mutant else 'pass'),result


def test_security_cli_and_mcp():
    from rvw.formal.mcp_tools import _argv, mcp_tools
    from rvw.cli import build_parser
    argv=_argv('security prove',{'rtl':'dut.v','top':'top','policy':'p.json','out':'out'})
    assert argv[4:6]==['security','prove']
    assert build_parser().parse_args(argv[3:]).func.__module__ == 'rvw.formal.security.policy'
    assert 'formal_security_prove' in {t.name for t in mcp_tools()}


def test_control_alias_cannot_disable_sink_assertions():
    from rvw.formal.security.policy import bind
    ports={n:{'direction':'input','bits':[i]} for i,n in enumerate(('clk','reset','secret'),1)}
    ports['sink']={'direction':'output','bits':[4]}
    policy={'clock':'clk','reset':'reset','sources':['secret'],'sinks':['sink'],
            'declassifier':'clk','adversary':'input control','unmodeled_channels':['power']}
    with pytest.raises(ValueError,match='control ports'):
        bind({'modules':{'top':{'ports':ports}}},'top',policy)

@pytest.mark.skipif(not TOOLS, reason='needs native Yosys, SBY and ABC')
@pytest.mark.parametrize('kind', ['release','constant_time'])
def test_release_and_timing_policy(tmp_path,kind):
    rtl=tmp_path/'dut.v';path=tmp_path/'policy.json';out=tmp_path/'out'
    rtl.write_text('module top(input clk,reset,secret,public,release,output sink); assign sink=release ? secret : public; endmodule')
    policy={'clock':'clk','reset':'reset','sources':['secret'],'sinks':['sink'],
            'adversary':'all input control','unmodeled_channels':['physical effects']}
    if kind=='release': policy['declassifier']='release'
    else: policy.update(kind='constant_time',operations=['test-operation'])
    path.write_text(json.dumps(policy))
    run(SimpleNamespace(rtl=str(rtl),top='top',policy=str(path),out=str(out),timeout=30))
    result=json.loads((out/'result.json').read_text())
    assert result['status']==('pass' if kind=='release' else 'fail'),result
