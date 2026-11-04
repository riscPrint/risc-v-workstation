"""Declared schedules have exact level, period and phase semantics."""
import json
import shutil

import pytest

from rvw.cli import main
from rvw.formal.schedule import parse


@pytest.mark.parametrize('items', [
    ['clk=01'], ['clk=01', 'other=000'], ['clk=01', 'other=01x'],
    ['clk=01', 'clk=10'], ['nope=01'], ['clk=01', 'other=01'*129],
    ['clk=' + '0'*126+'1', 'other=' + '0'*128+'1'],
])
def test_invalid_schedule(items):
    with pytest.raises(ValueError):
        parse(items, ['clk', 'other'])


def test_phase_and_period():
    assert parse(['clk=01', 'other=0011'], ['clk', 'other']) == {'clk': '01', 'other': '0011'}
    assert parse([], ['clk']) == {}


@pytest.mark.skipif(not all(shutil.which(x) for x in ('yosys','sby','yices-smt2')), reason='needs native formal tools')
@pytest.mark.parametrize('phase,expected', [('01', 'pass'), ('10', 'fail')])
def test_native_relative_phase(tmp_path, phase, expected):
    source = tmp_path / 'top.sv'
    # clk2fflogic samples property data before the edge. Same-phase other is low then.
    source.write_text('module top(input clk, other); always @(posedge clk) assert(!other); endmodule')
    out = tmp_path / 'out'
    rc = main(['formal','bmc','--verilog',str(source),'--top','top','--depth','12',
               '--event-clock','other','--clock-schedule','clk=01',
               '--clock-schedule','other='+phase,'--out',str(out)])
    result = json.loads((out / 'result.json').read_text())
    assert result['status'] == expected, result
    assert rc == (0 if expected == 'pass' else 1)
    assert result['event_model']['schedules'] == {'clk': '01', 'other': phase}
    if expected == 'pass':
        assert result['reachability']['status'] == 'reachable'


@pytest.mark.skipif(not all(shutil.which(x) for x in ('yosys','sby','yices-smt2')), reason='needs native formal tools')
@pytest.mark.parametrize('pattern,expected', [('0011', 'pass'), ('1100', 'fail')])
def test_native_two_to_one_ratio(tmp_path, pattern, expected):
    source = tmp_path / 'top.sv'
    source.write_text('module top(input clk, other); reg parity=0; '
                      'always @(posedge clk) begin parity <= !parity; assert(other == parity); end endmodule')
    out = tmp_path / 'out'
    main(['formal','bmc','--verilog',str(source),'--top','top','--depth','14',
          '--event-clock','other','--clock-schedule','clk=01',
          '--clock-schedule','other='+pattern,'--out',str(out)])
    assert json.loads((out / 'result.json').read_text())['status'] == expected
