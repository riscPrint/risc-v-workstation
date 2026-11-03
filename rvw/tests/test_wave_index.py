"""Compare the indexed reader with the strict streaming reader."""
import hashlib
import json
import sqlite3
import subprocess
import sys

import pytest

from rvw.wave import index, ops, vcd
from test_wave import VCD


@pytest.fixture
def pair(tmp_path):
    source = tmp_path / 'wave.vcd'
    source.write_text(VCD.replace('$enddefinitions', '$var wire 8 " alias [7:0] $end\n$var string 1 % text $end\n$enddefinitions') + '#40\nshello %\nbxZ "\nb10 "\n#100\n')
    out = tmp_path / 'wave.rvwi'
    result = index.build(str(source), str(out))
    assert result['sha256'] == hashlib.sha256(source.read_bytes()).hexdigest()
    return str(source), str(out)


@pytest.mark.parametrize('regex', ['.', 'count|alias', 'text|temp', 'absent'])
@pytest.mark.parametrize('bounds', [(0, None), (12, 25), (40, 40), (101, 200)])
def test_equivalent(pair, regex, bounds):
    source, saved = pair
    for limit in [None, 0, 1, 3, 1000]:
        assert ops.changes_page(saved, regex, *bounds, limit) == ops.changes_page(source, regex, *bounds, limit)
    for t in [0, 12, 40, 100, 101]:
        assert ops.sample(saved, regex, t) == ops.sample(source, regex, t)
    assert ops.sample_raw(saved, ['alias', 'TOP.Top.count'], 40) == ops.sample_raw(source, ['alias', 'TOP.Top.count'], 40)
    assert ops.list_signals(saved, regex) == ops.list_signals(source, regex)
    assert vcd.end_time(saved) == vcd.end_time(source)
    assert ops.detect_period(saved) == ops.detect_period(source)
    assert ops.info(saved).end == ops.info(source).end


@pytest.mark.parametrize('rebase', [False, True])
@pytest.mark.parametrize('bounds', [(0, None), (12, 25), (40, 40), (101, 200)])
def test_cut(pair, tmp_path, rebase, bounds):
    source, saved = pair
    paths = [str(tmp_path / f'cut{i}.vcd.gz') for i in range(2)]
    results = [ops.cut(p, o, *bounds, 'count|alias|temp|text', rebase) for p, o in zip(pair, paths)]
    assert results[0]['changes'] == results[1]['changes']
    for t in [0, 12, 40, 100, 200]:
        assert ops.sample(paths[0], '.', t) == ops.sample(paths[1], '.', t)
    assert vcd.end_time(paths[0]) == vcd.end_time(paths[1])


def test_snapshot_and_plan(pair, monkeypatch):
    source, saved = pair
    # An index is an explicit snapshot, never a cache of the current source.
    from pathlib import Path
    Path(source).unlink()
    monkeypatch.setattr(vcd, 'open_text', lambda *_: pytest.fail('full wave read'))
    assert ops.sample(saved, 'count', 40)['TOP.Top.count'] == '0x2'
    with sqlite3.connect(saved) as db:
        plan = db.execute('EXPLAIN QUERY PLAN SELECT raw FROM events WHERE code=? AND t<=? ORDER BY t DESC, seq DESC LIMIT 1', ('"', 40)).fetchall()
        assert any('signal_time' in str(row) for row in plan)
    result = subprocess.run([sys.executable, '-m', 'rvw', 'wave', 'changes', saved, 'count', '--from', '40', '--json'], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert len(json.loads(result.stdout)['changes']) == 2


def test_failed_build_and_invalid_index(tmp_path):
    source, out = tmp_path / 'bad.vcd', tmp_path / 'bad.rvwi'
    source.write_text(VCD + '#3\n')
    with pytest.raises(vcd.WaveError, match='decrease'):
        index.build(str(source), str(out))
    assert not out.exists()
    out.write_text('not sqlite')
    with pytest.raises(vcd.WaveError, match='invalid wave index'):
        ops.sample(str(out), '.', 10)
    with pytest.raises(vcd.WaveError, match='already exists'):
        index.build(str(source), str(out))


def test_gzip_and_bounds(pair, tmp_path):
    import gzip
    from pathlib import Path
    source, saved = pair
    gz = tmp_path / 'source.vcd.gz'
    with gzip.open(gz, 'wb') as f:
        f.write(Path(source).read_bytes())
    out = str(tmp_path / 'compressed.rvwi')
    index.build(str(gz), out)
    assert ops.changes(out, '.') == ops.changes(saved, '.')
    for path in [saved, out]:
        with pytest.raises(vcd.WaveError, match='non-negative'):
            ops.sample(path, '.', -1)
        with pytest.raises(vcd.WaveError, match='before start'):
            ops.changes(path, '.', 10, 5)
        with pytest.raises(vcd.WaveError, match='input wave'):
            ops.cut(path, path, 0)
