import gzip
import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from rvw.query.db import DesignDB, QueryError
from rvw.query.debug import extract, main


@pytest.fixture
def database(gcd_db, tmp_path):
    path = tmp_path / 'debug.db'
    path.write_bytes(gcd_db.read_bytes())
    with sqlite3.connect(path) as conn:
        conn.execute('DELETE FROM artifacts')
        for name, data in [('pdg.json', b'{"vertices": []}'), ('hgldd/Top.dd', b'{"objects": []}'),
                           ('hgldd/Child.dd', b'{"objects": [1]}')]:
            conn.execute('INSERT INTO artifacts VALUES (?, ?, ?, ?, ?)',
                         (name, 'application/json', 'gzip', len(data), gzip.compress(data)))
    return path


def test_shared_identity_and_all_hgldd(database, tmp_path):
    with_db = DesignDB(database)
    try:
        out = tmp_path / 'metadata'
        manifest = extract(with_db, out)
        assert manifest['input_capture'] == with_db.capture.record()
        assert len(manifest['artifacts']) == 3
        for row in manifest['artifacts']:
            assert hashlib.sha256((out / row['name']).read_bytes()).hexdigest() == row['sha256']
        assert json.loads((out / 'database.json').read_text()) == manifest
        with pytest.raises(QueryError, match='empty'):
            extract(with_db, out)
    finally:
        with_db.close()


@pytest.mark.parametrize('consumer', ['trace', 'gui', 'surfer', 'check'])
def test_launch_separate_consumers(database, tmp_path, monkeypatch, consumer):
    commands = []
    class Result:
        returncode = 7
    def launch(argv, **kwargs):
        commands.append(argv)
        for flag in ('--pdg-path', '--hgldd-path', '--hgldd-dir'):
            if flag in argv:
                assert Path(argv[argv.index(flag) + 1]).exists()
        return Result()
    monkeypatch.setattr('rvw.query.debug.run_group', launch)
    out = tmp_path / consumer
    assert main(['--db', str(database), '--out', str(out), '--consumer', consumer,
                 '--binary', '/some tool', '--', '--vcd-path', 'a wave.vcd']) == 7
    assert commands[0][0] == '/some tool'
    assert commands[0][-1] == 'a wave.vcd'
    assert ('dyn-pdg' in commands[0]) == (consumer == 'trace')
    assert ('--pdg-path' in commands[0]) == (consumer in ('trace', 'gui'))


def test_missing_artifacts_do_not_launch(database, tmp_path, monkeypatch):
    with sqlite3.connect(database) as conn:
        conn.execute("DELETE FROM artifacts WHERE name='pdg.json'")
    monkeypatch.setattr('rvw.query.debug.run_group', lambda *a: pytest.fail('launched'))
    assert main(['--db', str(database), '--out', str(tmp_path / 'missing'), '--consumer', 'trace']) == 2
    assert not (tmp_path / 'missing').exists()
    assert main(['--db', str(database), '--out', str(tmp_path / 'waves'), '--consumer', 'export']) == 2


def test_surfer_only_database(database, tmp_path):
    with sqlite3.connect(database) as conn:
        conn.execute("DELETE FROM artifacts WHERE name='pdg.json'")
    db = DesignDB(database)
    try:
        assert len(extract(db, tmp_path / 'surfer', trace=False)['artifacts']) == 2
    finally:
        db.close()


def test_reject_metadata_override(database, tmp_path):
    with pytest.raises(SystemExit):
        main(['--db', str(database), '--out', str(tmp_path / 'bad'), '--', '--pdg-path=other'])
