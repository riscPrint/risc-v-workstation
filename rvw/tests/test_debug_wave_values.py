"""Review 17: debug state must not depend on scalar or binary VCD spelling."""
import json
import re

import pytest

from rvw.bundle import handshakes, snapshot
from rvw.common.proc import run_group
from rvw.mcp.registry import Registry
from rvw.wave import ops, vcd
from test_debug_tools import fake_run
from test_mcp_tools import call


TEXT = """$timescale 1ps $end
$scope module TOP $end
$var wire 1 ! clk $end
$var wire 1 a a_valid $end
$var wire 1 b a_ready $end
$var wire 4 c a_source $end
$var wire 1 i d_valid $end
$var wire 1 j d_ready $end
$var wire 4 k d_source $end
$upscope $end
$enddefinitions $end
#0
0! 1a 1b b11 c 0i 1j b11 k
#5
1!
#10
0! 0a
#15
1!
#20
0! 1a 1i
#25
1!
#30
0! 1a 0b 0i
#35
1!
"""

CHANNELS = {n: {'valid': f'{n}_valid', 'ready': f'{n}_ready', 'id': f'{n}_source'}
            for n in ('a', 'd')}
HANDSHAKES = {'scope': r'^TOP\.', 'clock': 'clk', 'requests': ['a'],
              'responses': ['d'], 'channels': CHANNELS}
SNAPSHOT = [{'name': 'live', 'scope': r'^TOP\.', 'counts': {'valid': 'a_valid'},
             'busy': {'active': {'pattern': 'a_valid', 'idle': 0}},
             'table': {'key': 'a_valid', 'columns': {'id': 'a_source'}}}]


@pytest.fixture(params=['scalar', 'binary'])
def encoding(request):
    return request.param


def encode(text, encoding):
    if encoding == 'binary':
        return re.sub(r'(?<!\S)([01xz])([!abij])(?=\s|$)', r'b\1 \2', text)
    return text


@pytest.fixture(params=['vcd', 'fst', 'roundtrip'])
def debug_wave(request, encoding, tmp_path):
    path = tmp_path / 'values.vcd'
    # GTKWave expects one value record per line. Our reader also accepts compact records.
    text = encode(TEXT, encoding)
    path.write_text(re.sub(r' (?=[01xz][!abij]|b[01xz]+ )', '\n', text))
    if request.param == 'vcd':
        return str(path)
    assert vcd.tool('vcd2fst') and vcd.tool('fst2vcd'), 'GTKWave tools required'
    fst = tmp_path / 'values.fst'
    assert run_group([vcd.tool('vcd2fst'), str(path), str(fst)], capture=True).returncode == 0
    if request.param == 'fst':
        return str(fst)
    back = tmp_path / 'roundtrip.vcd'
    with back.open('w') as out:
        assert run_group([vcd.tool('fst2vcd'), str(fst)], stdout=out).returncode == 0
    return str(back)


def check_handshakes(result):
    assert result['channels']['a']['fires'] == 2
    assert result['channels']['d']['fires'] == 1
    assert result['channels']['a']['stalled_cycles'] == 0
    assert [(r['channel'], r['id'], r['age_cycles']) for r in result['open_requests']] == [
        ('a', '0x3', 1)]


def check_snapshot(result):
    assert result[0]['counts'] == {'valid': '1/1', 'active': '1/1'}
    assert result[0]['table']['rows'] == [{'#': None, 'id': '0x3'}]


def test_handshake_value_encodings(debug_wave):
    assert ops.detect_period(debug_wave) == 10
    check_handshakes(handshakes.analyze(HANDSHAKES, debug_wave, 35, 10))


def test_snapshot_value_encodings(debug_wave):
    check_snapshot(snapshot.take(SNAPSHOT, debug_wave, 35))


def test_commit_counts_value_encodings(debug_wave):
    from rvw.bundle.clock import WaveClock, commit_cycles
    counts, lo, hi = commit_cycles(debug_wave, 'a_valid', WaveClock(10, 5, True, 'fixture'))
    assert (dict(counts), lo, hi) == ({0: 1, 1: 1, 2: 1, 3: 1, 4: 1}, 0, 4)


def test_bundle_mcp_value_encodings(debug_wave, tmp_path, monkeypatch):
    monkeypatch.setenv('RVW_NO_LOCK', '1')
    config = tmp_path / 'debug.toml'
    config.write_text(r"""[core]
period = 10
[[snapshot]]
name = 'live'
scope = '^TOP\.'
counts = { valid = 'a_valid' }
busy = { active = { pattern = 'a_valid', idle = 0 } }
[snapshot.table]
key = 'a_valid'
columns = { id = 'a_source' }
[handshakes]
scope = '^TOP\.'
clock = 'clk'
requests = ['a']
responses = ['d']
[handshakes.channels]
a = { valid = 'a_valid', ready = 'a_ready', id = 'a_source' }
d = { valid = 'd_valid', ready = 'd_ready', id = 'd_source' }
""")
    run = fake_run(tmp_path / 'run', '--seed', '9')
    data = json.loads((run / 'result.json').read_text())
    data.update(cycles=4, artifacts={'wave': debug_wave},
                details={'wave_time_of_cycle_1': 5, 'wave_time_per_cycle': 10})
    (run / 'result.json').write_text(json.dumps(data))
    registry, problems = Registry.discover({'bundle'})
    assert not problems
    try:
        result = call(registry, 'bundle_make', run_dir=str(run), out=str(tmp_path / 'bundle'),
                      core_config=str(config), no_rerun=True, no_spinaltrace=True)
        check_handshakes(result['handshakes'])
        check_snapshot(result['snapshot'])
    finally:
        registry.jobs.shutdown()


@pytest.mark.parametrize('unknown', ['x', 'z'])
@pytest.mark.parametrize('signal', ['clk', 'd_valid', 'd_ready', 'd_source'])
def test_unknown_response_cannot_close_request(tmp_path, encoding, unknown, signal):
    text = TEXT.replace('#20\n0! 1a 1i', '#20\n0! 0a 1i')
    replacement = {'clk': f'#20\n{unknown}! 0a 1i',
                   'd_valid': f'#20\n0! 0a {unknown}i',
                   'd_ready': f'#20\n0! 0a 1i {unknown}j',
                   'd_source': f'#20\n0! 0a 1i b{unknown} k'}[signal]
    text = text.replace('#20\n0! 0a 1i', replacement).split('#30')[0]
    path = tmp_path / 'unknown.vcd'
    path.write_text(encode(text, encoding))
    result = handshakes.analyze(HANDSHAKES, str(path), 25, 10)
    assert [(r['channel'], r['id']) for r in result['open_requests']] == [('a', '0x3')]


@pytest.mark.parametrize('unknown', ['x', 'z'])
def test_unknown_ready_is_not_a_known_stall(tmp_path, encoding, unknown):
    path = tmp_path / 'unknown.vcd'
    path.write_text(encode(TEXT.replace('0! 1a 0b 0i', f'0! 1a {unknown}b 0i'), encoding))
    result = handshakes.analyze(HANDSHAKES, str(path), 35, 10)
    assert 'stalled_cycles' not in result['channels']['a']
    assert result['open_requests']


@pytest.mark.parametrize('unknown', ['x', 'z'])
def test_snapshot_unknown_is_not_zero(tmp_path, encoding, unknown):
    path = tmp_path / 'unknown.vcd'
    path.write_text(encode(TEXT.replace('0! 1a 0b 0i', f'0! {unknown}a 0b 0i'), encoding))
    result = snapshot.take(SNAPSHOT, str(path), 35)
    assert result[0]['counts'] == {'valid': '?/1', 'active': '?/1'}
    entries = result[0]['table']['unknown_entries']
    assert len(entries) == 1 and entries[0]['#'] is None
    assert entries[0]['value'] in (unknown, 'b' + unknown)
    assert 'unknown entry keys' in snapshot.render_md(result)
    assert 'no live entries' not in snapshot.render_md(result)
