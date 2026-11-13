"""Portable debug sessions: saved identities, moved artifacts, missing and changed files."""
import json
import shutil
import subprocess
import sys

import pytest

from rvw.wave import session
from rvw.wave.vcd import WaveError
from test_wave import VCD


def test_save_and_open_moved(tmp_path):
    run = tmp_path / 'run'
    run.mkdir()
    (run / 'wave.vcd').write_text(VCD)
    (run / 'result.json').write_text('{"status": "fail"}')
    q = tmp_path / 'q.rvwq.json'
    q.write_text(json.dumps({'schema': 'rvw.wave-query/1', 'kind': 'find', 'wave': 'wave.vcd', 'args': ['valid'], 'options': {}}))
    s = session.save(str(run / 's.json'), str(run / 'wave.vcd'), signals=['count|valid'], cursors=[25, 10],
                     queries=[str(q)], note='hang at 25')
    assert s['signals'] == ['TOP.Top.count', 'TOP.Top.valid'] and s['cursors'] == [10, 25]
    assert set(s['artifacts']) == {'wave', 'result'}
    assert session.open_session(str(run / 's.json'))['status'] == 'complete'
    moved = tmp_path / 'elsewhere'
    shutil.move(str(run), str(moved))
    r = session.open_session(str(moved / 's.json'))
    assert r['status'] == 'complete' and r['artifacts']['wave']['path'] == str(moved / 'wave.vcd')
    assert r['queries'][0]['kind'] == 'find'
    (moved / 'wave.vcd').write_text(VCD.replace('#40', '#41'))
    r = session.open_session(str(moved / 's.json'))
    assert r['status'] == 'incomplete' and r['artifacts']['wave']['status'] == 'changed'
    (moved / 'result.json').unlink()
    assert session.open_session(str(moved / 's.json'))['artifacts']['result']['status'] == 'missing'


def test_errors_and_cli(tmp_path):
    w = tmp_path / 'w.vcd'
    w.write_text(VCD)
    with pytest.raises(WaveError, match='no signal'):
        session.save(str(tmp_path / 'x.json'), str(w), signals=['nosuch'])
    run = lambda *a: subprocess.run([sys.executable, '-m', 'rvw', 'wave', 'session', *a], capture_output=True, text=True)
    out = run('save', str(tmp_path / 's.json'), '--wave', str(w), '--signal', 'clk', '--cursor', '5', '--json')
    assert out.returncode == 0, out.stderr
    assert run('save', str(tmp_path / 's.json'), '--wave', str(w)).returncode == 2      # exists
    assert run('open', str(tmp_path / 's.json')).returncode == 0
    w.unlink()
    out = run('open', str(tmp_path / 's.json'))
    assert out.returncode == 1 and 'wave: missing' in out.stdout
