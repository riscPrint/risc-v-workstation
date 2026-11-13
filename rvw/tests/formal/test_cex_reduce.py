from pathlib import Path
import pytest
from rvw.formal.cex_reduce import reduce_trace, testbench as emit_testbench
from rvw.wave import vcd

TRACE = '''$timescale 1ns $end
$scope module top $end
$var wire 1 a input $end
$var wire 1 b unused $end
$var wire 1 c out $end
$upscope $end
$enddefinitions $end
#0
0a
0b
0c
#10
1a
1b
#20
0b
1c
#30
0a
'''
PORTS = [dict(name='input', direction='input', bits=[1]),
         dict(name='unused', direction='input', bits=[2]),
         dict(name='out', direction='output', bits=[3])]


def test_reduction_preserves_first_values_and_same_failure(tmp_path):
    source, target = tmp_path / 'in.vcd', tmp_path / 'out.vcd'
    source.write_text(TRACE)
    def oracle(path, index):
        with path.open() as stream:
            vcd.read_header(stream)
            rows = list(vcd.body_records(stream))
        return (10, 'a', '1') in rows and (20, 'c', '1') in rows
    report = reduce_trace(source, target, PORTS, 'top', oracle)
    assert report['end_time'] == 20
    assert len(report['removed_input_events']) == 2
    assert '0a' in target.read_text() and '0b' in target.read_text()
    assert oracle(target, 0)
    assert source.read_text() == TRACE


def test_failed_baseline_refuses_reduction(tmp_path):
    source = tmp_path / 'in.vcd'
    source.write_text(TRACE)
    with pytest.raises(ValueError, match='baseline'):
        reduce_trace(source, tmp_path / 'out.vcd', PORTS, 'top', lambda *_: False)


def test_budget_never_claims_shortest_prefix(tmp_path):
    source = tmp_path / 'in.vcd'
    source.write_text(TRACE)
    report = reduce_trace(source, tmp_path / 'out.vcd', PORTS, 'top', lambda *_: True, 1)
    assert not report['earliest_prefix_checked']
    assert len(report['checks']) == 1


def test_testbench_uses_delays_and_preserves_unknowns(tmp_path):
    source, target = tmp_path / 'in.vcd', tmp_path / 'tb.sv'
    source.write_text(TRACE.replace('0a', 'xa'))
    emit_testbench(source, target, PORTS, 'top')
    text = target.read_text()
    assert "input = 1'bx;" in text and '#10;' in text
    assert 'out =' not in text
    assert '`timescale 1ns/1fs' in text
