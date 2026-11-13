"""Round-21 long dependency path regression."""
from contextlib import closing
import json
import os
from pathlib import Path

import pytest

from test_query_capture import capture_classpath
from rvw.cli import main
from rvw.common.proc import run_group
from rvw.mcp.envelope import envelope
from rvw.mcp.registry import Registry
from rvw.query import ops
from rvw.query.db import DesignDB
from rvw.query.mcp_tools import mcp_tools


@pytest.fixture(scope='session')
def round21_path(tmp_path_factory, capture_classpath):
    root = tmp_path_factory.mktemp('round21-path')
    java = str(Path(os.environ['JAVA_HOME']) / 'bin/java')
    result = run_group([java, '-Xss64m', '-cp', capture_classpath, 'spinaldb.Round21PathFixtures', str(root)],
                       cwd=root, capture=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    return root


@pytest.mark.parametrize('max_paths', [1, 2, 3])
def test_long_delay_path_is_bounded(round21_path, capsys, max_paths):
    database = round21_path / 'delay/design.db'
    with closing(DesignDB(database)) as db:
        result = ops.path(db, 'a', 'y', max_paths=max_paths)
        assert not ops.path(db, 'a', 'y', comb_only=True)['found']
    assert result['found']
    assert len(result['paths']) == min(max_paths, 2)
    for path in result['paths']:
        assert path['register_stages'] == 1100
        assert path['length'] == 1102
        assert path['hops'][0]['path'] == 'a'
        assert path['hops'][-1]['path'] == 'y'
    assert main(['query', 'path', 'a', 'y', '--db', str(database), '--max-paths', str(max_paths), '--json']) == 0
    cli = json.loads(capsys.readouterr().out)
    assert cli.pop('input_capture')['files']
    assert cli == result
    text, _, error = Registry(mcp_tools(), max_text=2_000_000).call_json('query_path',
        {'db': str(database), 'a': 'a', 'b': 'y', 'max_paths': max_paths})
    mcp = json.loads(text)
    assert not error and mcp.pop('input_capture')['files']
    assert mcp == envelope(result)
