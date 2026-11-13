"""Clocked sequences, handshake transactions and wave diffs on VCD and indexed input."""
import pytest

from rvw.wave import index, temporal, wdiff
from rvw.wave.vcd import WaveError

# Clock period 10, rising edges at 5, 15, 25, ... Values change at the edges (registered),
# so the sampled (pre-edge) value at edge k is the value set at edge k-1.
HS = """$timescale 1ns $end
$scope module TOP $end
$scope module dut $end
$var wire 1 ! clk $end
$var wire 1 " io_cmd_valid $end
$var wire 1 # io_cmd_ready $end
$var wire 8 $ io_cmd_payload [7:0] $end
$var wire 1 % done $end
$upscope $end
$upscope $end
$enddefinitions $end
#0
$dumpvars
0!
0"
0#
b0 $
0%
$end
#5
1!
1"
b1 $
#10
0!
#15
1!
1#
#20
0!
#25
1!
b10 $
0#
#30
0!
#35
1!
b11 $
1%
#40
0!
#45
1!
0"
1#
0%
#50
0!
#55
1!
#60
0!
"""
# Sampled per edge (time: valid ready payload done):
#  5: 0 0 0 0 | 15: 1 0 1 0 | 25: 1 1 1 0 (fire 1) | 35: 1 0 2 0 | 45: 1 0 3 1 (payload changed)
# 55: 0 1 3 0 (valid dropped)


@pytest.fixture(params=['vcd', 'rvwi'])
def wave(tmp_path, request):
    p = tmp_path / 'hs.vcd'
    p.write_text(HS)
    if request.param == 'vcd':
        return str(p)
    out = tmp_path / 'hs.rvwi'
    index.build(str(p), str(out))
    return str(out)


def test_parse_sequence():
    assert temporal.parse_sequence('a ##1 b ##[1:3] c') == [(0, 0, 'a'), (1, 1, 'b'), (1, 3, 'c')]
    assert temporal.parse_sequence('a ##[2:$] b')[1][:2] == (2, None)
    with pytest.raises(WaveError):
        temporal.parse_sequence('a ##1')
    with pytest.raises(WaveError):
        temporal.parse_sequence('a ##[3:1] b')


def test_sequence(wave):
    r = temporal.sequence(wave, 'io_cmd_valid && !io_cmd_ready ##1 io_cmd_ready')
    assert r['clock'] == 'TOP.dut.clk' and r['cycles'] == 6
    # Starts at 15, 35 and 45; ready is sampled high at 25 and 55, low at 45.
    assert r['matched'] == 2 and r['matches'] == [{'start': 15, 'end': 25, 'cycles': 1},
                                                  {'start': 45, 'end': 55, 'cycles': 1}]
    assert r['failed'] == 1 and r['failures'][0]['start'] == 35
    r = temporal.sequence(wave, 'rose(io_cmd_valid) ##[1:4] done')
    assert r['matched'] == 1 and r['matches'][0]['end'] == 45
    r = temporal.sequence(wave, 'io_cmd_valid ##[1:$] done', 0, 40)
    assert r['pending'] == 3 and r['matched'] == 0


def test_transactions(wave):
    r = temporal.transactions(wave, 'io_cmd_valid', 'io_cmd_ready', 'io_cmd_payload')
    assert r['kind'] == 'Stream' and r['transfers'] == 1
    assert r['transactions'] == [{'time': 25, 'wait_cycles': 1, 'payload': {'TOP.dut.io_cmd_payload': '0x1'}}]
    assert r['stall_edges'] == 3 and r['idle_edges'] == 2
    assert [i['issue'] for i in r['issues']] == ['payload_changed', 'valid_dropped']
    flow = temporal.transactions(wave, 'io_cmd_valid', None, 'io_cmd_payload')
    assert flow['kind'] == 'Flow' and flow['transfers'] == 4 and flow['issues'] == []


def test_stream_from_database(cluster_db):
    s = temporal.stream_signals(str(cluster_db), 'io.cmd')
    assert s['type'] == 'Stream'
    assert s['valid'] == 'TOP.GcdCluster.io_cmd_valid' and s['ready'] == 'TOP.GcdCluster.io_cmd_ready'
    assert sorted(s['payload']) == ['TOP.GcdCluster.io_cmd_payload_0', 'TOP.GcdCluster.io_cmd_payload_1']
    f = temporal.stream_signals(str(cluster_db), 'io.rsp')
    assert f['type'] == 'Flow' and f['ready'] is None


def test_diff(tmp_path, wave):
    other = tmp_path / 'b.vcd'
    other.write_text(HS.replace('#35\n1!\nb11 $', '#35\n1!\nb111 $'))
    same = wdiff.diff(wave, wave)
    assert same['status'] == 'match' and same['first_divergence'] is None
    r = wdiff.diff(wave, str(other))
    assert r['status'] == 'diverged' and r['first_divergence'] == 35
    assert r['divergent'] == [{'signal': 'TOP.dut.io_cmd_payload', 'b_signal': 'TOP.dut.io_cmd_payload',
                               'a': '0x3', 'b': '0x7'}]
    clocked = wdiff.diff(wave, str(other), clock='clk')
    assert clocked['first_divergence'] == 45         # pre-edge sample sees the change one edge later
    later = wdiff.diff(wave, str(other), t0=50)
    assert later['first_divergence'] == 50           # still different at the window start
    shifted = tmp_path / 'c.vcd'
    import re
    shifted.write_text(re.sub(r'#(\d+)', lambda m: f'#{int(m.group(1)) + 100}', HS))
    assert wdiff.diff(wave, str(shifted), offset=100, t0=0)['status'] == 'match'
    full = wdiff.diff(wave, str(other), stop=False)
    assert full['first_divergence_by_signal'] == [{'signal': 'TOP.dut.io_cmd_payload', 'time': 35}]
    with pytest.raises(WaveError, match='in common'):
        wdiff.diff(wave, str(other), map_prefix=('TOP.', 'X.'))


def test_cli_and_mcp(tmp_path, cluster_db):
    import json
    import subprocess
    import sys
    from rvw.mcp.registry import Registry
    p = tmp_path / 'hs.vcd'
    p.write_text(HS)
    run = lambda *a: subprocess.run([sys.executable, '-m', 'rvw', 'wave', *a], capture_output=True, text=True)
    out = run('seq', str(p), 'io_cmd_valid ##1 io_cmd_ready', '--json')
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout)['matched'] == 2
    out = run('txn', str(p), '--valid', 'io_cmd_valid', '--ready', 'io_cmd_ready', '--payload', 'payload')
    assert out.returncode == 0 and 'ISSUE 45: payload_changed' in out.stdout
    other = tmp_path / 'b.vcd'
    other.write_text(HS.replace('b11 $', 'b111 $'))
    out = run('diff', str(p), str(other))
    assert out.returncode == 1 and 'first divergence at 35' in out.stdout
    assert run('diff', str(p), str(p)).returncode == 0
    registry, _ = Registry.discover({'wave'})
    try:
        _, data, error = registry.call_json('wave_diff', {'wave': str(p), 'other': str(other), 'on_clock': True})
        assert not error and data['first_divergence'] == 45
        _, data, error = registry.call_json('wave_txn', {'wave': str(p), 'valid': 'io_cmd_valid'})
        assert not error and data['kind'] == 'Flow'
    finally:
        registry.jobs.shutdown()
