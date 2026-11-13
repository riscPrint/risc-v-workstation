from rvw.mcp.envelope import envelope
"""User emission code keys, round 22."""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3

import pytest

from test_query_capture import capture_classpath
from test_query_round19 import parity
from rvw.cli import main
from rvw.common.proc import run_group
from rvw.mcp.registry import Registry
from rvw.query.db import DesignDB, QueryError
from rvw.query.diff import diff
from rvw.query.mcp_tools import mcp_tools


@pytest.fixture(scope='session')
def round22(tmp_path_factory, capture_classpath):
    root = tmp_path_factory.mktemp('round22')
    java = str(Path(os.environ['JAVA_HOME']) / 'bin/java')
    result = run_group([java, '-Xss64m', '-cp', capture_classpath, 'spinaldb.Round22Fixtures', str(root)],
                       cwd=root, capture=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    return root


@pytest.mark.parametrize('connections', [True, False])
def test_same_user_callback_is_identical(round22, capsys, connections):
    paths = [round22 / f'callback{n}/design.db' for n in (0, 1)]
    with closing(DesignDB(paths[0])) as a, closing(DesignDB(paths[1])) as b:
        result = diff(a, b, connections=connections)
    assert result == parity(*paths, capsys, connections=connections)
    assert result['summary']['identical'] is True, result['undetermined']
    assert result['undetermined']['count'] == 0


def test_changed_user_phase_code_is_different(round22, capsys):
    paths = [round22 / f'code{n}/design.db' for n in (0, 1)]
    result = parity(*paths, capsys)
    assert result['summary']['identical'] is False
    assert result['emission_config']['changed']
    keys = [result['emission_config'][side] for side in ('old', 'new')]
    assert all('r22.UserPhase' in key and 'sha256=' in key for key in keys)
    # The changed helper selects X or zero for the same don't-care assignment.
    assert (round22 / 'code0/rtl/Round22Poison.v').read_text() != (
        round22 / 'code1/rtl/Round22Poison.v').read_text()


def test_unreadable_user_phase_is_undetermined(round22, capsys):
    path = round22 / 'unreadable/design.db'
    result = parity(path, path, capsys)
    assert result['summary']['identical'] is None
    assert '<emission_config>' in result['undetermined']['paths']


@pytest.mark.parametrize('old_side', [True, False])
def test_schema19_diff_is_refused(gcd_db, tmp_path, capsys, old_side):
    legacy = tmp_path / 'schema19.db'
    with sqlite3.connect(gcd_db) as src, sqlite3.connect(legacy) as dst:
        src.backup(dst)
        dst.execute("UPDATE meta SET value='rvw.designdb/19' WHERE key='schema'")
    paths = (legacy, gcd_db) if old_side else (gcd_db, legacy)
    with closing(DesignDB(paths[0])) as a, closing(DesignDB(paths[1])) as b:
        with pytest.raises(QueryError, match='diff needs rvw.designdb/20'):
            diff(a, b)
    assert main(['query', 'diff', *map(str, paths), '--json']) == 2
    cli = json.loads(capsys.readouterr().out)
    text, _, error = Registry(mcp_tools()).call_json('query_diff', dict(zip(('old', 'new'), map(str, paths))))
    assert error and envelope(cli) == json.loads(text)
    assert 'diff needs rvw.designdb/20' in cli['error']


@pytest.fixture(scope='session')
def round22_collections(tmp_path_factory, capture_classpath):
    root = tmp_path_factory.mktemp('round22-collections')
    java = str(Path(os.environ['JAVA_HOME']) / 'bin/java')
    result = run_group([java, '-Xss64m', '-cp', capture_classpath,
                        'spinaldb.Round22CollectionFixtures', str(root)],
                       cwd=root, capture=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    return root


@pytest.mark.parametrize('connections', [True, False])
def test_immutable_list_phase_diff(round22_collections, capsys, connections):
    def path(name):
        return round22_collections / name / 'design.db'

    with closing(DesignDB(path('list0'))) as a, closing(DesignDB(path('list1'))) as b:
        result = diff(a, b, connections=connections)
    assert result == parity(path('list0'), path('list1'), capsys, connections=connections)
    assert result['summary']['identical'] is True, result['undetermined']
    assert result['undetermined']['count'] == 0
    result = parity(path('list0'), path('changed'), capsys, connections=connections)
    assert result['summary']['identical'] is False
    assert result['emission_config']['changed']
    result = parity(path('subclass'), path('subclass'), capsys, connections=connections)
    assert result['summary']['identical'] is None
    assert '<emission_config>' in result['undetermined']['paths']
