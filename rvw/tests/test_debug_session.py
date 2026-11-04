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


def test_active_trace_uses_captured_artifacts_and_keeps_accuracy(session, monkeypatch, tmp_path):
    import types
    import rvw.common.proc
    synthetic = tmp_path / 'synthetic.db'
    synthetic.write_bytes(session.db.input.copy.read_bytes())
    with sqlite3.connect(synthetic) as c:
        # The fixture is explicitly synthetic here. This tests transport, not engine parity.
        for name in ('pdg.json', 'hgldd/VexTop.dd'):
            c.execute('INSERT INTO artifacts VALUES(?,?,?,?,?)', (name,'application/json','identity',2,b'{}'))
    calls=[]
    def launch(argv, **kwargs):
        calls.append(argv)
        assert json.loads(Path(argv[argv.index('--pdg-path')+1]).read_text()) == {}
        Path(argv[argv.index('-o')+1]).write_text(json.dumps(dict(accuracy={'status':'incomplete'},vertices=[dict(assigns_to='execute_PC')],edges=[])))
        return types.SimpleNamespace(returncode=0,stderr='')
    monkeypatch.setattr(rvw.common.proc, 'run_group', launch)
    traced = Session(synthetic, session.wave)
    try:
        result = traced.request(dict(op='trace',signal='execute_PC',time='10'))
    finally:
        traced.close()
    assert result['result']['graph']['accuracy']['status']=='incomplete'
    assert calls[0][calls[0].index('--at-time')+1]=='10'
    assert calls[0][calls[0].index('-s')+1]=='signal:execute_PC'


@pytest.mark.parametrize('pruned', [0, 1])
def test_pruned_and_stale_source_are_visible(session, tmp_path, pruned):
    import hashlib
    source = tmp_path / 'Source.scala'
    source.write_text('val execute_PC = UInt(32 bits)\n')
    db = tmp_path / 'stale.db'
    db.write_bytes(session.db.input.copy.read_bytes())
    with sqlite3.connect(db) as c:
        c.execute('INSERT INTO files VALUES(9999,?)', (str(source),))
        c.execute("UPDATE signals SET file_id=9999,line=1,pruned=? WHERE path='execute_PC'", (pruned,))
        c.execute('INSERT INTO input_files VALUES(?,?,?,?,?)', (str(source),str(source),hashlib.sha256(source.read_bytes()).hexdigest(),source.stat().st_size,'{}'))
    captured = Session(db, session.wave)
    try:
        source.write_text('changed source\n')
        result = captured.request(dict(op='select',signal='execute_PC',time='0'))['result']
        assert result['mapping'] == ('pruned' if pruned else 'resolved')
        assert result['source'] is None
        assert result['where']['status'] == 'inconclusive'
        assert ('pruned' if pruned else 'differs from the database capture') in result['where']['cause']
    finally:
        captured.close()


def test_unresolved_wave_is_explicit(session):
    with sqlite3.connect(session.wave) as c:
        meta = json.loads(c.execute('SELECT value FROM metadata').fetchone()[0])
        meta['header']['vars'][0]['name'] = 'TOP.Other.execute_PC'
        c.execute('UPDATE metadata SET value=?', (json.dumps(meta),))
    result = session.request(dict(op='select',signal='execute_PC',time='0'))['result']
    assert result['mapping'] == 'unresolved wave'
    assert result['values'] == []


def test_adjacent_c1_binding_keeps_inconclusive_run_and_database_limit(session):
    import hashlib
    path = Path(session.wave).parent / 'result.json'
    run = dict(schema='rvw.run/1', status='error', inconclusive='missing retirement evidence',
               artifacts={'wave': 'wave.vcd'}, config='fixture')
    path.write_text(json.dumps(run))
    binding = session.request(dict(op='open'))['result']['run_binding']
    assert binding['status'] == 'bound'
    assert binding['run'] == run
    assert binding['result_sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert 'unverified' in binding['database']
    # A session retains its captured evidence, not a later producer rewrite.
    path.write_text('{}')
    assert session.request(dict(op='open'))['result']['run_binding'] == binding


@pytest.mark.parametrize('change,cause', [
    ('missing', 'no adjacent'), ('invalid', 'schema'), ('undeclared', 'no declared'),
    ('other', 'different wave'), ('stale', 'differ'), ('deleted', 'No such file'),
])
def test_c1_binding_never_accepts_missing_or_mismatched_evidence(session, change, cause):
    path = Path(session.wave).parent / 'result.json'
    run = dict(schema='rvw.run/1', status='pass', artifacts={'wave': 'wave.vcd'})
    if change == 'invalid':
        run['schema'] = 'other/1'
    if change == 'undeclared':
        run['artifacts'] = {}
    if change == 'other':
        run['artifacts']['wave'] = 'other.vcd'
    if change != 'missing':
        path.write_text(json.dumps(run))
    wave = path.parent / 'wave.vcd'
    if change == 'stale':
        wave.write_text(wave.read_text() + '#30\n')
    if change == 'deleted':
        wave.unlink()
    binding = session.request(dict(op='open'))['result']['run_binding']
    assert binding['status'] == 'inconclusive'
    assert cause in binding['cause']
    assert 'run' not in binding


@pytest.mark.parametrize('payload', [
    None, {}, {'op':'source','file':'Unit.scala','line':True},
    {'op':'source','file':'Unit.scala','line':1.5},
    {'op':'select','signal':'','time':'0'},
    {'op':'select','signal':'execute_PC','time':'0','end':1},
    {'op':'select','signal':'execute_PC','time':'10','end':'9'},
    *[dict(op='trace', signal='execute_PC', time=value)
      for value in ['-1', '1.5', '9223372036854775808', 10, '9'*200]],
])
def test_native_and_web_requests_reject_invalid_navigation(session, payload):
    with pytest.raises((QueryError, KeyError)):
        session.request(payload)
