"""Strict environment replay compares results without copying DUT values."""
import json
import pytest
from rvw.cosim.checker import check
from rvw.cosim.platform import Platform
from test_state import fixture, Model

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('wrong', [False, True])
def test_device_response_is_input_and_not_synchronization(tmp_path, wrong):
    header, row = fixture()
    header.update(capabilities=['environment'],environment='retirement-ordered/1')
    for name in ['fd_valid','fd','fd_wdata','fflags','fcsr']:
        row.pop(name,None)
    platform = Platform.load('boom')
    address = platform.mmio[0][0]
    row.update(insn='0x2283', rd=5, mem_addr=hex(address), mem_rmask=15,
               mem_rdata='0x11',rd_wdata='0x11')
    model = Model(row)
    model.environment_inputs = lambda levels: None
    def step(**kwargs):
        assert kwargs['mmio'] == (address,17)
        return dict(model.effect)
    model.step = step
    if wrong:row.update(rd_wdata='0x12',mem_rdata='0x12')
    records = [header,dict(event='environment',kind='pins',cycle=0,before_order=0,levels='0x0'),
               dict(event='environment',kind='device-read',cycle=1,before_order=0,address=hex(address),size=4,data='0x11'),
               row,dict(event='end',cycle=2,status='pass')]
    path=tmp_path/'trace.jsonl';path.write_text('\n'.join(map(json.dumps,records)))
    result=check(path,model,platform,sync=())
    assert result['status'] == ('mismatch' if wrong else 'match')
    assert result['synchronized'] == 0
    assert result['state_coverage']['environment_events'] == 2
