"""Portable regressions from /tmp/review20-design/test_findings.py."""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3

import pytest

from race_injection import race_injector
from test_query_capture import capture_classpath, hdl
from test_query_round19 import parity
from rvw.cli import main
from rvw.common.capture import Capture
from rvw.common.proc import run_group
from rvw.mcp.registry import Registry
from rvw.query import ops
from rvw.query.db import DesignDB
from rvw.query.diff import diff
from rvw.query.mcp_tools import mcp_tools


@pytest.fixture(scope='session')
def round20(tmp_path_factory, capture_classpath):
    root = tmp_path_factory.mktemp('round20')
    (root / 'src/main/scala').mkdir(parents=True)
    java = str(Path(os.environ['JAVA_HOME']) / 'bin/java')
    result = run_group([java, '-Xss64m', '-cp', capture_classpath, 'spinaldb.Round20Fixtures', str(root)],
                       cwd=root, capture=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    return root


@pytest.mark.parametrize('connections', [True, False])
def test_generated_port_references_keep_identity(round20, capsys, connections):
    paths = [round20 / f'ports{n}/design.db' for n in (0, 1)]
    with closing(DesignDB(paths[0])) as a, closing(DesignDB(paths[1])) as b:
        result = diff(a, b, connections=connections)
    assert result == parity(*paths, capsys, connections=connections)
    assert result['summary']['identical'] is False, result['summary']


def test_default_navigation_roots_can_be_absent(round20):
    with closing(DesignDB(round20 / 'main-only/design.db')) as db:
        result = diff(db, db)
        record = json.loads(db.meta['input_capture'])
    assert result['summary']['identical'] is True, result.get('cause')
    assert {'source': str(round20 / 'src/test/scala'), 'state': 'absent'} in record['optional_source_roots']


def test_explicit_navigation_root_is_required(round20):
    with closing(DesignDB(round20 / 'required/design.db')) as db:
        result = diff(db, db)
    assert result['summary']['identical'] is None
    assert result['status'] == 'inconclusive'


def test_optional_source_root_does_not_hide_broken_link(tmp_path):
    alias = tmp_path / 'src'; alias.symlink_to(tmp_path / 'missing', target_is_directory=True)
    root = tmp_path / 'batch'; root.mkdir()
    result = hdl.capture_batch([], root, optional_source_roots=[str(alias)])
    assert result['files']['problems']
    assert result['files']['capture']['problems']


def test_optional_source_root_check_error_invalidates_capture(tmp_path, monkeypatch):
    source = tmp_path / 'src'
    original = Path.lstat

    def denied(path, *args, **kwargs):
        if path == source:
            raise PermissionError('cannot inspect source root')
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'lstat', denied)
    root = tmp_path / 'batch'; root.mkdir()
    result = hdl.capture_batch([], root, optional_source_roots=[str(source)])
    assert result['files']['problems']
    assert result['files']['capture']['problems']


@pytest.mark.parametrize('replace,revert', [(True, False), (False, True)])
@pytest.mark.parametrize('legacy', [False, True])
def test_captured_source_root_keeps_symlink_lookup(gcd_db, tmp_path, race_injector, replace, revert, legacy):
    real = tmp_path / 'real'; real.mkdir()
    source = real / 'Probe.scala'; source.write_bytes(b'original Scala source\n')
    alias = tmp_path / 'alias'; alias.symlink_to(real, target_is_directory=True)
    logical = alias / source.name
    root = tmp_path / 'batch'; root.mkdir()
    batch = hdl.capture_batch([], root, source_roots=[str(alias)])
    database = tmp_path / 'design.db'; shutil.copyfile(gcd_db, database)
    with sqlite3.connect(database) as db:
        db.execute('UPDATE files SET path=? WHERE id=(SELECT file_id FROM signals WHERE path="x")', (str(logical),))
        db.execute('DELETE FROM input_files')
        for item in batch['files']['capture']['files']:
            if legacy and item['source'] == str(logical):
                continue
            db.execute('INSERT INTO input_files VALUES (?,?,?,?,?)',
                       (item['source'], item['resolved'], item['sha256'], item['size'], json.dumps(item)))
        db.execute('UPDATE meta SET value=? WHERE key="input_capture"', (json.dumps(batch['files']['capture']),))
        db.execute('DELETE FROM rtl_files')
    hook = race_injector.file(Capture, 'file', source, b'changed Scala source\n', when='after',
                              replace=replace, revert=revert, occurrence=2)
    with closing(DesignDB(database)) as db:
        result = ops.where(db, 'x')
    assert result.get('status') != 'inconclusive', result.get('cause')
    assert hook.fired
    assert result['signal']['source']['sha256'] == hashlib.sha256(b'original Scala source\n').hexdigest()
    assert result['signal']['source']['source'] == str(logical)
    assert result['signal']['loc'].startswith(str(logical))
    record = batch['files']['capture']
    binding = next(item for item in record['files'] if item['source'] == str(logical))
    assert {'path': str(alias), 'target': str(real)} in binding['symlinks']


def test_text_where_handles_memory_read_state(round20, capsys):
    path = round20 / 'sync/design.db'
    with closing(DesignDB(path)) as db:
        state = db.q("SELECT path FROM signals WHERE kind='mem_read'")[0][0]
    text, _, error = Registry(mcp_tools()).call_json('query_where', {'db': str(path), 'signal': state})
    result = json.loads(text)
    assert not error and 'verilog' not in result['signal']
    assert result.get('status') != 'inconclusive'
    assert main(['query', 'where', state, '--db', str(path)]) == 0
    output = capsys.readouterr().out
    assert result['signal']['origin'] in output
    assert 'clock' in output
    assert 'wave' not in output and 'verilog' not in output


def test_where_refuses_unrecorded_symlink_alias(gcd_db, tmp_path):
    source = tmp_path / 'source.scala'; source.write_text('source\n')
    alias = tmp_path / 'alias.scala'; alias.symlink_to(source)
    database = tmp_path / 'design.db'; shutil.copyfile(gcd_db, database)
    with sqlite3.connect(database) as db:
        db.execute('UPDATE files SET path=? WHERE id=(SELECT file_id FROM signals WHERE path="x")', (str(alias),))
        db.execute('DELETE FROM input_files')
        db.execute('INSERT INTO input_files VALUES (?,?,?,?,?)',
                   (str(source), str(source), hashlib.sha256(source.read_bytes()).hexdigest(), source.stat().st_size, '{}'))
        db.execute('UPDATE meta SET value=? WHERE key="input_capture"', (json.dumps({'trees': []}),))
        db.execute('DELETE FROM rtl_files')
    with closing(DesignDB(database)) as db:
        result = ops.where(db, 'x')
    assert result['status'] == 'inconclusive'
    assert 'loc' not in result['signal']
