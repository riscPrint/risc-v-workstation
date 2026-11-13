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
