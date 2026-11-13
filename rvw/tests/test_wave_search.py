"""Expression search and edge counts agree on VCD streams and indexed snapshots."""
import pytest

from rvw.wave import index, search
from rvw.wave.expr import Expr, value_of
from rvw.wave.vcd import WaveError
from test_wave import VCD


@pytest.fixture(params=['vcd', 'rvwi'])
def wave(tmp_path, request):
    p = tmp_path / 'w.vcd'
    p.write_text(VCD)
    if request.param == 'vcd':
        return str(p)
    out = tmp_path / 'w.rvwi'
    index.build(str(p), str(out))
    return str(out)


def test_value_of():
    assert value_of('1') == 1 and value_of('x') is None
    assert value_of('b0101') == 5 and value_of('b01x1') is None
    assert value_of('r1.5') == 1.5 and value_of('sabc') == 'abc'


def test_find_intervals(wave):
    r = search.find(wave, 'valid && count == 1')
    assert r['signals'] == {'valid': 'TOP.Top.valid', 'count': 'TOP.Top.count'}
    assert r['matches'] == [{'start': 15, 'end': 20}]
    assert r['first'] == 15 and r['last'] == {'start': 15, 'end': 20}
    assert r['true_time'] == 5


def test_find_unknown_and_open_end(wave):
    r = search.find(wave, 'count[0] == 0')
    # count = 0 (t0..10), 1 (10..20), 2 (20..30), 0b0000001x from 30: bit 0 unknown.
    assert r['matches'] == [{'start': 0, 'end': 10}, {'start': 20, 'end': 30}]
    assert r['unknown_steps'] == 1
    r = search.find(wave, 'count[7:1] == 1', 25)
    assert r['matches'] == [{'start': 25, 'end': None}]
    assert r['true_time'] == 15


def test_find_rose_and_window(wave):
    r = search.find(wave, 'rose(clk)', 0, 25)
    assert [m['start'] for m in r['matches']] == [5, 15, 25]
    r = search.find(wave, 'rose(clk)', 0, None, limit=1)
    assert r['count'] == 3 and r['truncated'] and len(r['matches']) == 1
    assert r['first'] == 5 and r['last'] == {'start': 25, 'end': 30}
    assert search.find(wave, 'rose(clk) and !valid')['matches'] == [{'start': 5, 'end': 10}]


def test_find_errors(wave):
    with pytest.raises(WaveError, match='no signal'):
        search.find(wave, 'nosuch == 1')
    with pytest.raises(WaveError, match='invalid wave expression'):
        search.find(wave, 'valid &&')
    with pytest.raises(WaveError, match='unsupported'):
        search.find(wave, '__import__("os")')
    with pytest.raises(WaveError, match='end time'):
        search.find(wave, 'valid', 10, 5)


def test_ambiguous_and_quoted():
    from rvw.wave.vcd import Var
    vs = [Var('!', 'TOP.a.v', 1, 'wire'), Var('"', 'TOP.b.v', 1, 'wire'), Var('#', 'TOP.m[0]', 1, 'wire')]
    with pytest.raises(WaveError, match='ambiguous'):
        Expr('v', vs)
    e = Expr('a.v && `TOP.m[0]`', vs)
    assert e.evaluate({'!': '1', '#': '1'}, {}) is True
    assert e.evaluate({'!': '1', '#': 'x'}, {}) is None
    assert e.evaluate({'!': '0', '#': 'x'}, {}) is False


def test_edges(wave):
    r = {s['signal']: s for s in search.edges(wave, '.')['signals']}
    assert r['TOP.clk']['rising'] == 3 and r['TOP.clk']['falling'] == 3
    assert r['TOP.Top.valid'] == {'signal': 'TOP.Top.valid', 'width': 1, 'changes': 2,
                                  'rising': 1, 'falling': 1, 'unknown': 0}
    assert r['TOP.Top.count']['changes'] == 3 and r['TOP.Top.count']['unknown'] == 1
    w = {s['signal']: s for s in search.edges(wave, 'clk', 10, 20)['signals']}
    assert w['TOP.clk']['rising'] == 1 and w['TOP.clk']['falling'] == 2


def _fst(tmp_path):
    import shutil
    import subprocess
    tool = shutil.which('vcd2fst')
    if tool is None:
        pytest.skip('vcd2fst not on PATH')
    src = tmp_path / 'f.vcd'
    src.write_text(VCD)
    out = tmp_path / 'f.fst'
    subprocess.run([tool, str(src), str(out)], check=True, capture_output=True)
    return str(out)


def test_wellen_index_matches_fst2vcd(tmp_path):
    pytest.importorskip('pywellen')
    import shutil
    from rvw.wave import ops
    fst = _fst(tmp_path)
    if shutil.which('fst2vcd') is None:
        pytest.skip('fst2vcd not on PATH')
    a = index.build(fst, str(tmp_path / 'a.rvwi'), 'wellen')
    b = index.build(fst, str(tmp_path / 'b.rvwi'), 'vcd')
    assert a['reader'] == 'wellen' and b['reader'] == 'vcd'
    for regex in ['.', 'count', 'temp']:
        for t in [0, 12, 30, 40]:
            assert ops.sample(a['out'], regex, t) == ops.sample(b['out'], regex, t)
        # FST keeps no order between signals at one time.
        key = lambda r: (r['time'], r['signal'])
        assert sorted(ops.changes(a['out'], regex), key=key) == sorted(ops.changes(b['out'], regex), key=key)
    assert ops.detect_period(a['out']) == 10
    assert search.find(a['out'], 'valid && count == 1')['matches'] == [{'start': 15, 'end': 20}]


def test_wellen_vcd_reader(tmp_path):
    pytest.importorskip('pywellen')
    from rvw.wave import ops
    p = tmp_path / 'w.vcd'
    p.write_text(VCD)
    a = index.build(str(p), str(tmp_path / 'a.rvwi'), 'wellen')
    for t in [0, 12, 30, 40]:
        assert ops.sample(a['out'], '.', t) == ops.sample(str(p), '.', t)


def test_ensure_rebuilds_stale(tmp_path, monkeypatch):
    import os
    monkeypatch.setenv('RVW_WAVE_INDEX_DIR', str(tmp_path / 'cache'))
    p = tmp_path / 'w.vcd'
    p.write_text(VCD)
    first = index.ensure(str(p))
    assert index.ensure(str(p)) == first
    assert search.find(first, 'count == 2')['matches'] == [{'start': 20, 'end': 30}]
    p.write_text(VCD.replace('b00000010 "', 'b00000011 "'))
    os.utime(p, ns=(1, 1))
    again = index.ensure(str(p))
    assert again == first
    assert search.find(again, 'count == 2')['matches'] == []
    assert index.metadata(again)['source_stat']['mtime_ns'] == 1
    assert index.verify(again)['fresh'] is True
    p.write_text(VCD)
    v = index.verify(again)
    assert v['fresh'] is False and 'differs' in v['reason']


def test_cli_and_mcp(tmp_path, monkeypatch):
    import json
    import subprocess
    import sys
    from rvw.mcp.registry import Registry
    monkeypatch.setenv('RVW_WAVE_INDEX_DIR', str(tmp_path / 'cache'))
    p = tmp_path / 'w.vcd'
    p.write_text(VCD)
    out = subprocess.run([sys.executable, '-m', 'rvw', 'wave', 'find', str(p), 'valid && count == 1',
                          '--indexed', '--json'], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert json.loads(out.stdout)['matches'] == [{'start': 15, 'end': 20}]
    assert list((tmp_path / 'cache').glob('*.rvwi'))
    out = subprocess.run([sys.executable, '-m', 'rvw', 'wave', 'edges', str(p), 'clk', '--json'],
                         capture_output=True, text=True)
    assert json.loads(out.stdout)['signals'][0]['rising'] == 3
    out = subprocess.run([sys.executable, '-m', 'rvw', 'wave', 'find', str(p), 'nosuch'],
                         capture_output=True, text=True)
    assert out.returncode == 2 and 'no signal' in out.stderr
    registry, problems = Registry.discover({'wave'})
    try:
        _, data, error = registry.call_json('wave_find', {'wave': str(p), 'expr': 'rose(clk)', 't1': '2c',
                                                          'indexed': True})
        assert not error, data
        assert [m['start'] for m in data['matches']] == [5, 15]
        _, data, error = registry.call_json('wave_sample', {'wave': str(p), 'regex': 'count', 'at': '20',
                                                            'indexed': True})
        assert not error and data['values'] == {'TOP.Top.count': '0x2'}
    finally:
        registry.jobs.shutdown()


def test_native_fst_queries_match_vcd(tmp_path, monkeypatch):
    pytest.importorskip('pywellen')
    fst = _fst(tmp_path)
    vcd_path = str(tmp_path / 'f.vcd')
    from rvw.wave import temporal
    calls = []
    import rvw.wave.vcd as vcdmod
    real = vcdmod.open_text
    monkeypatch.setattr(vcdmod, 'open_text', lambda p, *a: calls.append(p) or real(p, *a))
    for expr, bounds in [('valid && count == 1', (0, None)), ('rose(clk)', (0, 25)), ('count[0] == 0', (12, 35))]:
        a, b = search.find(fst, expr, *bounds), search.find(vcd_path, expr, *bounds)
        assert a['matches'] == b['matches'] and a['first'] == b['first']
    assert len(calls) == 3 and not any(c.endswith('.fst') for c in calls)   # the FST was never converted
    assert search.edges(fst, '.')['signals'] == search.edges(vcd_path, '.')['signals']
    for seq in ['rose(valid) ##1 count == 1', 'rose(clk) ##[1:2] valid']:
        a, b = temporal.sequence(fst, seq), temporal.sequence(vcd_path, seq)
        assert (a['matched'], a['failed'], a['matches']) == (b['matched'], b['failed'], b['matches'])
    monkeypatch.setenv('RVW_WAVE_FST_READER', 'vcd')
    if __import__('shutil').which('fst2vcd'):
        assert search.find(fst, 'valid')['matches'] == search.find(vcd_path, 'valid')['matches']
