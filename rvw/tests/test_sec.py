"""Seeded tiny RTL security experiments. Native tests stay outside the fast set."""
import json
import shutil
import pytest
from rvw.sec.ift import run


@pytest.mark.parametrize('leak',[True,False])
@pytest.mark.slow
def test_native_ift(tmp_path, leak):
    if not all(shutil.which(t) for t in ('yosys','verilator')):
        pytest.skip('Yosys and Verilator required')
    rtl = tmp_path/'unit.v'
    rtl.write_text('module unit(input clk,reset,secret, output reg bus);\n'
                   'always @(posedge clk) if(reset) bus<=0; else bus<='+('secret' if leak else '0')+'; endmodule')
    policy = tmp_path/'policy.json'
    policy.write_text(json.dumps(dict(clock='clk', reset='reset',sources=['secret'],sinks=['bus'])))
    stimulus = tmp_path/'stimulus.json'
    stimulus.write_text(json.dumps([dict(reset=1,secret=0),dict(reset=0,secret=1)]))
    result = run(rtl,'unit',policy,stimulus,tmp_path/'out')
    assert result['status'] == ('violation' if leak else 'no_leak_observed')
    if leak:
        assert result['findings'][0]['cycle'] == 1
        assert result['findings'][0]['candidate_path'][0] == 'secret'


@pytest.mark.slow
@pytest.mark.parametrize('leak',[True,False])
def test_native_pair_runner(tmp_path,leak):
    import sys
    from pathlib import Path
    from rvw.sec.pairs import run as pairs
    if not shutil.which('verilator'): pytest.skip('Verilator required')
    manifest=tmp_path/'pairs.json'
    manifest.write_text(json.dumps(dict(contract='constant-time',clauses=['pc'],observations=['cycles'],
        public={'leak':leak},secrets=[0,1],program=['nop'],minimize_runs=0,
        adapter_command=[sys.executable,str(Path(__file__).parent/'fixtures/sec/adapter.py'),'{request}','{out}'])))
    result=pairs(manifest,tmp_path/'pairs')
    assert result['status']==('violation' if leak else 'no_leak_observed'),result


@pytest.mark.slow
def test_no_sink_checks_is_inconclusive(tmp_path):
    if not all(shutil.which(t) for t in ('yosys','verilator')):pytest.skip('native tools required')
    rtl=tmp_path/'unit.v'
    rtl.write_text('module unit(input clk,reset,secret,allow_release,output reg bus); always @(posedge clk) if(reset) bus<=0; else bus<=secret; endmodule')
    policy=tmp_path/'policy.json'
    policy.write_text(json.dumps(dict(clock='clk',reset='reset',sources=['secret'],sinks=['bus'],declassifier='allow_release')))
    stimulus=tmp_path/'samples.json'
    stimulus.write_text(json.dumps([dict(reset=1,secret=0,allow_release=0),dict(reset=0,secret=1,allow_release=1)]))
    result=run(rtl,'unit',policy,stimulus,tmp_path/'out')
    assert result['status']=='inconclusive' and result['checked_cycles']==0
