"""Round 15: parse replay waveforms without silently retaining stale state."""
import io

import pytest

from rvw.formal import vcdsnap

HEADER = '''$timescale 1 ps $end
$scope module tb $end $scope module dut $end
$var wire 1 ! clk $end
$var reg 1 " q $end
$upscope $end $upscope $end
$enddefinitions $end
'''



def snapshot(body, header=HEADER, cycle=None, time=10):
    return vcdsnap._take(io.StringIO(header + body), ['tb', 'dut'], 'clk', cycle, time)



@pytest.mark.parametrize('body', [
    '#0 0! 0" #5 1! 1" #10 0!',
    '#0\n0!\n0"\n#5\n  1!\n\t1"\n#10\n0!\n',
    '#0 $dumpvars 0! 0" $end #5 1! b1 " #10 0!',
])
def test_whitespace_is_not_a_value_change_boundary(body):
    assert snapshot(body).values['"'] in ('1', 'b1')
    assert snapshot(body, cycle=1, time=None).time == 5



def test_unknown_values_replace_previous_known_values():
    s = snapshot('#0 0! 1" #5 1! X" #10 z"')
    assert s.values['"'] == 'z'



def test_header_and_body_can_share_a_line():
    assert snapshot('#0 0! 0" #10 1"', header=' '.join(HEADER.split()) + ' ').values['"'] == '1'



def test_aliases_and_nested_scopes_round_trip(tmp_path):
    header = HEADER.replace('$upscope $end $upscope $end',
                            '$scope module child $end $var wire 1 " alias $end '
                            '$upscope $end $upscope $end $upscope $end')
    snap = snapshot('#0 0! 0" #10 1"', header=header)
    out = tmp_path / 's.vcd'
    vcdsnap.write(snap, out, 'top')
    again = vcdsnap.take(out, 'top', None, None, 10)
    assert [(v.path, again.values[v.code]) for v in again.vars] == [
        (['clk'], '0'), (['q'], '1'), (['child', 'alias'], '1')]



@pytest.mark.parametrize('body', [
    '#0 0! 0" #5 $dumpoff 0" $end #10 1!',
    '#0 0! 0" #5 r1.0 " #10 1!',
    '#0 0! 0" #5 b2 " #10 1!',
    '#0 0! 0" #5 b10 " #10 1!',
    '#0 0! 0" #5 1undeclared #10 1!',
    '#0 0! 0" #5 unsupported #10 1!',
    '#0 0! 0" #5 $unknown $end #10 1!',
    '#0 0! 0" #5 $dumpvars 1"',
    '#0 0! 0" #5 1! #4 0! #10 1!',
])
def test_unsupported_or_malformed_body_is_refused(body):
    with pytest.raises(SystemExit) as e:
        snapshot(body)
    assert e.value.code == 2



@pytest.mark.parametrize('header', [
    HEADER.replace('1 ps', '10 ps'),
    HEADER.replace('1 ps', '1 frogs'),
    HEADER.replace('$timescale 1 ps $end', ''),
    HEADER.replace('$var reg 1 " q $end', '$var real 1 " q $end'),
    HEADER.replace('$var reg 1 " q $end', '$var reg 2 ! q $end'),
    HEADER.replace('$var reg 1 " q $end', '$var reg 1 ! clk $end'),
    HEADER.replace('$var reg 1 " q $end', '$var reg 1 " q $end $var reg 1 # q $end'),
    HEADER.replace('$enddefinitions $end', ''),
])
def test_unsupported_or_malformed_header_is_refused(header):
    with pytest.raises(SystemExit) as e:
        snapshot('#0 0! 0" #10 1!', header=header)
    assert e.value.code == 2



def test_unknown_clock_is_refused_for_cycle_selection():
    with pytest.raises(SystemExit):
        snapshot('#0 0! 0" #5 x! #10 1! #20 0!', cycle=1, time=None)



def test_failed_fst_conversion_cannot_supply_partial_state(tmp_path, monkeypatch):
    from rvw.common.proc import Result

    def fail(argv, **kwargs):
        kwargs['stdout'].write(HEADER + '#0 0! 0" #10 1!')
        return Result(returncode=1, stderr='corrupt FST')

    monkeypatch.setattr(vcdsnap, 'run_group', fail)
    with pytest.raises(SystemExit):
        vcdsnap.take(tmp_path / 'bad.fst', 'tb.dut', 'clk', 1, None)



def test_memory_hoisting_must_not_merge_different_variables():
    header = HEADER.replace('$upscope $end $upscope $end',
                            '$var wire 1 # m[0] $end '
                            '$scope module m $end $var wire 1 $ m[0] $end '
                            '$upscope $end $upscope $end $upscope $end')
    with pytest.raises(SystemExit):
        snapshot('#0 0! 0" 0# 1$ #10 1!', header=header)


def test_declared_range_must_agree_with_width():
    header = HEADER.replace('$var reg 1 " q $end', '$var reg 1 " q [7:0] $end')
    with pytest.raises(SystemExit):
        snapshot('#0 0! 0" #10 1!', header=header)


def test_cycle_selection_refuses_multiple_edges_at_one_time():
    with pytest.raises(SystemExit):
        snapshot('#0 0! 0" #5 1! 0! 1! 1" #10 0!', cycle=1, time=None)


def test_scope_discovery_does_not_hide_a_late_ambiguous_match(tmp_path):
    trace = tmp_path / 'many_scopes.vcd'
    trace.write_text('$timescale 1ps $end $scope module top $end '
                     '$var wire 1 ! clk $end $upscope $end '
                     + ''.join(f'$scope module filler{i} $end $upscope $end ' for i in range(2000))
                     + '$scope module other $end $scope module top $end '
                     '$var wire 1 " clk $end $upscope $end $upscope $end $enddefinitions $end')
    with trace.open() as stream:
        assert [s for s in vcdsnap.scopes(stream) if s.split('.')[-1] == 'top'] == ['top', 'other.top']
