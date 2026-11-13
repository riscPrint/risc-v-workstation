"""A completed attempt cannot hide a later pending clock obligation."""
from argparse import Namespace
import json
import shutil

import pytest

from rvw.formal.event_sim import run
from rvw.results import load_run


@pytest.mark.skipif(not all(shutil.which(t) for t in ('yosys', 'iverilog', 'vvp')),
                    reason='needs Yosys and Icarus')
@pytest.mark.parametrize('kind', ['assert', 'assume'])
def test_completed_attempt_does_not_discharge_later_request(tmp_path, kind):
    source = tmp_path / 'm.sv'
    source.write_text('module m(input a,b,req,ack); '
                      f'p: {kind} property (@(posedge a) req |=> @(posedge b) ack); endmodule')
    events = tmp_path / 'events.json'
    events.write_text(json.dumps(dict(schema='rvw.formal-events/1', events=[
        dict(time=0, inputs=dict(a='0', b='0', req='1', ack='1')),
        dict(time=1, inputs=dict(a='1')),
        dict(time=2, inputs=dict(b='1')),
        dict(time=3, inputs=dict(a='0', b='0')),
        dict(time=4, inputs=dict(a='1')),
    ])))
    out = tmp_path / 'out'
    code = run(Namespace(verilog=[str(source)], top='m', events=str(events), out=str(out),
                         backend='icarus', observe=None, check_x=False, timeout=15))
    result = load_run(out)
    assert result.status == 'error', result.to_dict()
    assert code == 1
    assert result.extra['assertions'][0]['passed'] == 1
    assert result.extra['assertions'][0]['pending'] == 1
