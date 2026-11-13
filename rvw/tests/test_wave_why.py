"""Active-driver tracing joins SpinalDB drivers with indexed wave values (GCD fixture)."""
import json
import subprocess
import sys

import pytest

from rvw.wave import why
from rvw.wave.vcd import WaveError

# GCD: x, y registers. when(y < x) x := x - y else y := y - x; when(io_loadValues) x := io_a, y := io_b.
# when_Gcd_l19 is the `y < x` condition signal. Clock period 10, rising edges at 5, 15, 25, ...
GCD_VCD = """$timescale 1ns $end
$scope module TOP $end
$scope module GCD $end
$var wire 1 ! clk $end
$var wire 1 " reset $end
$var wire 32 # io_a [31:0] $end
$var wire 32 $ io_b [31:0] $end
$var wire 1 % io_loadValues $end
$var wire 32 & x [31:0] $end
$var wire 32 ' y [31:0] $end
$var wire 1 ( when_Gcd_l19 $end
$var wire 32 ) io_result [31:0] $end
$upscope $end
$upscope $end
$enddefinitions $end
#0
$dumpvars
0!
1"
b1100 #
b1000 $
0%
b0 &
b0 '
0(
b0 )
$end
#2
0"
1%
#5
1!
b1100 &
b1000 '
b1100 )
1(
#7
0%
#10
0!
#15
1!
b100 &
b100 )
0(
#20
0!
#25
1!
b0 '
1(
#30
0!
"""


@pytest.fixture
def wave(tmp_path, monkeypatch):
    monkeypatch.setenv('RVW_WAVE_INDEX_DIR', str(tmp_path / 'cache'))
    p = tmp_path / 'gcd.vcd'
    p.write_text(GCD_VCD)
    return str(p)


def test_register_load(gcd_db, wave):
    r = why.why(str(gcd_db), wave, 'x', 8, depth=1)
    node = r['trace']
    assert node['value'] == '0xc' and node['set_at'] == 5 and node['evaluated_at'] == 4
    assert node['status'] == 'active'
    active = next(a for a in node['assignments'] if a['id'] == node['active'])
    assert active['source'] == 'io_a'
    assert active['conditions'][0]['signal'] == 'io_loadValues' and active['conditions'][0]['holds'] is True
    assert node['children'][0]['signal'] == 'io_a' and node['children'][0]['status'] == 'no_driver'
    assert node['children'][0]['value'] == '0xc'


def test_register_subtract_and_walk(gcd_db, wave):
    node = why.why(str(gcd_db), wave, 'x', 18, depth=2)['trace']
    assert node['value'] == '0x4' and node['set_at'] == 15
    active = next(a for a in node['assignments'] if a['id'] == node['active'])
    assert active['source'] == 'x - y'
    assert {c['signal']: c['value'] for c in node['children']} == {'x': '0xc', 'y': '0x8'}
    assert node['children'][0]['set_at'] == 5      # x before the edge was loaded at 5
    held = why.why(str(gcd_db), wave, 'y', 18, depth=0)['trace']
    assert held['set_at'] == 5


def test_comb_output_and_reset(gcd_db, wave):
    node = why.why(str(gcd_db), wave, 'io_result', 18, depth=1)['trace']
    assert node['status'] == 'active' and node['evaluated_at'] == 18
    assert node['children'][0]['signal'] == 'x'
    early = why.why(str(gcd_db), wave, 'x', 1, depth=1)['trace']
    assert early['status'] == 'initial'


def test_unknown_and_cli(gcd_db, wave, tmp_path):
    with pytest.raises(Exception):
        why.why(str(gcd_db), wave, 'nosuch_signal', 10)
    with pytest.raises(WaveError):
        why.why(str(gcd_db), wave, 'x', -1)
    out = subprocess.run([sys.executable, '-m', 'rvw', 'wave', 'why', wave, 'x', '--at', '18', '--db', str(gcd_db),
                          '--json'], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    data = json.loads(out.stdout)
    assert data['trace']['set_at'] == 15 and data['binding'].startswith('unverified')
    text = subprocess.run([sys.executable, '-m', 'rvw', 'wave', 'why', wave, 'x', '--at', '18', '--db', str(gcd_db)],
                          capture_output=True, text=True)
    assert 'x - y' in text.stdout and 'set at 15' in text.stdout


def test_mcp(gcd_db, wave):
    from rvw.mcp.registry import Registry
    registry, _ = Registry.discover({'wave'})
    try:
        _, data, error = registry.call_json('wave_why', {'wave': wave, 'signal': 'y', 'at': '28',
                                                         'db': str(gcd_db), 'depth': 1})
        assert not error, data
        node = data['trace']
        assert node['value'] == '0x0' and node['set_at'] == 25
        active = next(a for a in node['assignments'] if a['id'] == node['active'])
        assert active['source'] == 'y - x'
        assert active['conditions'][0]['kind'] == 'else' and active['conditions'][0]['holds'] is True
    finally:
        registry.jobs.shutdown()
