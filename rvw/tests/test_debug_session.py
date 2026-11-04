"""VexRiscv captured database plus a small, synthetic wave fixture."""
import gzip
import json
from pathlib import Path
import sqlite3

import pytest

from rvw.query.session import Session
from rvw.query.db import QueryError
from rvw.wave.index import build


@pytest.fixture
def session(tmp_path):
    root = Path(__file__).resolve().parents[2]
    db = tmp_path / 'vex.db'
    with sqlite3.connect(db) as c:
        c.executescript(gzip.decompress((root / 'vscode/features/debug/test/fixtures/vex.sql.gz').read_bytes()).decode())
    vcd = tmp_path / 'wave.vcd'
    vcd.write_text('''$timescale 1ns $end
$scope module TOP $end
$scope module VexTop $end
$var wire 32 ! execute_PC $end
$upscope $end
$upscope $end
$enddefinitions $end
#0
b0 !
#10
b100 !
#20
bx !
''')
    wave = tmp_path / 'wave.rvwi'
    build(str(vcd), str(wave))
    s = Session(db, str(wave))
    yield s
    s.close()


def test_vex_open_shared_capture_and_missing_artifact(session):
    opened = session.request(dict(op='open'))
    assert opened['result']['blocks'] is None
    assert opened['result']['signals'][0]['name'] == 'TOP.VexTop.execute_PC'
    assert 'unverified' in opened['result']['binding']
    selected = session.request(dict(op='select', signal='execute_PC', time='10'))
    assert selected['database'] == opened['database']
    assert selected['result']['mapping'] == 'resolved'
    assert selected['result']['values'][0]['initial'] == '0x4'
    assert selected['result']['values'][0]['changes'][0]['time'] == '20'
    assert 'x' in selected['result']['values'][0]['changes'][0]['value']
    assert 'drivers' in selected['result']


def test_reverse_source_mapping_and_bad_times(session):
    sig = session.db.resolve_one('execute_PC')
    candidates = session.request(dict(op='source', file=sig.file, line=sig.line))['result']['candidates']
    assert sig.path in candidates
    with pytest.raises(QueryError, match='invalid time'):
        session.request(dict(op='select', signal=sig.path, time='-1'))
    with pytest.raises(QueryError):
        session.request(dict(op='select', signal='missing', time='0'))


def test_missing_and_stale_wave_trace_is_inconclusive(session):
    with sqlite3.connect(session.wave) as conn:
        meta = json.loads(conn.execute('select value from metadata').fetchone()[0])
    path = Path(meta['source'])
    path.write_text(path.read_text() + '#30\n')
    assert 'stale wave' in session.request(dict(op='trace', signal='execute_PC', time='10'))['result']['cause']
    path.unlink()
    assert session.request(dict(op='trace', signal='execute_PC', time='10'))['result']['status'] == 'inconclusive'


def test_window_bound_and_signal_index(session):
    with sqlite3.connect(session.wave) as c:
        c.executemany('INSERT INTO events VALUES(?,?,?,?)', [(100+i,30+i,'!', '1') for i in range(600)])
        plan = str(c.execute('EXPLAIN QUERY PLAN SELECT t, raw FROM events WHERE code=? AND t>? AND t<=? ORDER BY t, seq LIMIT 501', ('!',0,1000)).fetchall())
        assert 'signal_time' in plan
    result = session.request(dict(op='select',signal='execute_PC',time='0',end='1000'))['result']
    assert result['values'][0]['truncated']
    assert len(result['values'][0]['changes']) == 500
