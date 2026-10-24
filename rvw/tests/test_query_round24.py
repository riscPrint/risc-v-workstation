"""Round 24: conservative inout paths and bidirectional analog attachments."""
from contextlib import closing
import json
import os
from pathlib import Path
import shutil
import sqlite3

import pytest

from rvw.cli import main
from rvw.common.proc import run_group
from rvw.mcp.registry import Registry
from rvw.query import ops
from rvw.query.db import DesignDB, QueryError
from rvw.query.diff import diff
from rvw.query.mcp_tools import mcp_tools
from test_query_capture import capture_classpath


@pytest.fixture(scope='session')
def round24(tmp_path_factory, capture_classpath):
    root = tmp_path_factory.mktemp('round24-inout')
    result = run_group([str(Path(os.environ['JAVA_HOME']) / 'bin/java'), '-Xss64m',
                        '-cp', capture_classpath, 'spinaldb.Round24Fixtures', str(root)],
                       cwd=root, capture=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    return root


def parity(database, capsys, op, args, **options):
    with closing(DesignDB(database)) as db:
        api = getattr(ops, op)(db, *args, **options)
    cli_options = ['--' + k.replace('_', '-') for k, v in options.items() if v]
    assert main(['query', op, *args, '--db', str(database), '--json', *cli_options]) == 0
    cli = json.loads(capsys.readouterr().out)
    assert cli.pop('input_capture')['files']
    params = dict(zip(('a', 'b') if op == 'path' else ('signal',), args))
    text, _, error = Registry(mcp_tools()).call_json(
        'query_' + op, {'db': str(database), **params, **options})
    mcp = json.loads(text)
    assert not error, mcp
    assert mcp.pop('input_capture')['files']
    assert api == cli == mcp
    return api


@pytest.mark.parametrize('a,b', [('pad', 'q'), ('bb.pad', 'bb.q'),
                                 ('d', 'pad'), ('en', 'pad'),
                                 ('pad', 'bb.pad'), ('bb.pad', 'pad')])
@pytest.mark.parametrize('comb_only', [False, True])
def test_pad_paths(round24, capsys, a, b, comb_only):
    result = parity(round24 / 'pad/design.db', capsys, 'path', [a, b], comb_only=comb_only)
    assert result['found'], result
    assert all(p['register_stages'] == 0 for p in result['paths'])


@pytest.mark.parametrize('signal,readers,drivers', [
    ('pad', {'bb.pad'}, {'bb.pad'}),
    ('bb.pad', {'pad', 'bb.q'}, {'pad', 'bb.d', 'bb.en'}),
    ('bb.q', {'q'}, {'bb.pad', 'bb.d', 'bb.en'}),
    ('bb.d', {'bb.pad', 'bb.q'}, {'d'}),
    ('bb.en', {'bb.pad', 'bb.q'}, {'en'}),
])
def test_pad_loads_and_drivers(round24, capsys, signal, readers, drivers):
    database = round24 / 'pad/design.db'
    loads = parity(database, capsys, 'loads', [signal])
    driven = parity(database, capsys, 'drivers', [signal])
    assert readers <= {r['path'] for r in loads['readers']}
    assert drivers <= {r['path'] for r in driven['read_signals']}
    assert 'undriven' not in driven.get('origin', '')
    assert signal not in {r['path'] for r in loads['readers']}


def test_pad_register_boundary(round24, capsys):
    database = round24 / 'pad/design.db'
    result = parity(database, capsys, 'path', ['pad', 'delayed'])
    assert result['found']
    assert all(p['register_stages'] == 1 for p in result['paths'])
    assert not parity(database, capsys, 'path', ['pad', 'delayed'], comb_only=True)['found']


def test_partial_analog_attachment_keeps_digital_drivers_directional(round24, capsys):
    database = round24 / 'partial/design.db'
    for a, b in [('pads', 'bb.pad'), ('bb.pad', 'pads'), ('pads', 'q'), ('d', 'pads'), ('en', 'pads')]:
        result = parity(database, capsys, 'path', [a, b], comb_only=True)
        assert result['found'], result
        assert all(p['register_stages'] == 0 for p in result['paths'])
    for b in ['d', 'en', 'bb.d', 'bb.en']:
        assert not parity(database, capsys, 'path', ['pads', b], comb_only=True)['found']


def test_digital_connections_stay_directional(round24, capsys):
    database = round24 / 'digital/design.db'
    assert parity(database, capsys, 'path', ['a', 'q'], comb_only=True)['found']
    assert not parity(database, capsys, 'path', ['q', 'a'], comb_only=True)['found']
    with closing(DesignDB(database)) as db:
        edges = {(db.signal_by_id(a).path, db.signal_by_id(b).path, k)
                 for a, b, k in db.q('SELECT src,dst,kind FROM edges')}
        # These are the keys emitted by b72c950 before the inout fix.
        assert db.q('SELECT key FROM assignments ORDER BY seq') == [(' := a:Bool',), (' := bb.q:Bool',)]
        assert db.schema == 'rvw.designdb/20'
    assert edges == {('a', 'bb.a', 'data'), ('bb.a', 'bb.q', 'blackbox'), ('bb.q', 'q', 'data')}


def test_bidirectional_attachment_is_not_register_state(round24, capsys):
    database = round24 / 'pad/design.db'
    result = parity(database, capsys, 'path', ['pad', 'pad'], comb_only=True)
    assert result['found']
    assert all(p['length'] == 2 and p['register_stages'] == 0 for p in result['paths'])
    with closing(DesignDB(database)) as db:
        result = diff(db, db)
    assert result['summary']['identical'] is True
    assert result['undetermined']['count'] == 0


@pytest.mark.parametrize('src,dst', [('bb.pad', 'bb.q'), ('pad', 'bb.pad')])
def test_old_incomplete_inout_graph_refuses(round24, tmp_path, capsys, src, dst):
    database = tmp_path / 'old.db'
    shutil.copyfile(round24 / 'pad/design.db', database)
    with sqlite3.connect(database) as db:
        db.execute('DELETE FROM edges WHERE src=(SELECT id FROM signals WHERE path=?) '
                   'AND dst=(SELECT id FROM signals WHERE path=?)', (src, dst))
    with closing(DesignDB(database)) as db:
        for query, args in [(ops.path, ['pad', 'q']), (ops.drivers, ['pad']),
                            (ops.loads, ['pad']), (ops.fanin, ['q']), (ops.fanout, ['pad']),
                            (diff, [db])]:
            with pytest.raises(QueryError, match='incomplete inout dependency graph.*Rebuild'):
                query(db, *args)
    for op, args, params in [('path', ['pad', 'q'], {'a': 'pad', 'b': 'q'}),
                             ('drivers', ['pad'], {'signal': 'pad'}),
                             ('loads', ['pad'], {'signal': 'pad'}),
                             ('diff', [str(database), str(database)],
                              {'old': str(database), 'new': str(database)})]:
        db_args = [] if op == 'diff' else ['--db', str(database)]
        assert main(['query', op, *args, *db_args, '--json']) == 2
        cli = json.loads(capsys.readouterr().out)
        text, _, error = Registry(mcp_tools()).call_json(
            'query_' + op, {**({'db': str(database)} if op != 'diff' else {}), **params})
        assert error and json.loads(text) == cli
        assert 'incomplete inout dependency graph' in cli['error']
