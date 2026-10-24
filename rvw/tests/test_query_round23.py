"""Round 23 query usability regressions."""
from contextlib import closing
import json
import os
from pathlib import Path

import pytest

from rvw.cli import main
from rvw.mcp.registry import Registry
from rvw.query.db import DesignDB, QueryError
from rvw.query import ops
from rvw.query.mcp_tools import mcp_tools
from rvw.common.proc import run_group
from rvw.query.diff import diff
from test_query_capture import capture_classpath
from test_query_round19 import parity


@pytest.mark.parametrize('pattern', ['[', '(', '*', r'\x'])
def test_invalid_regex_is_query_error(gcd_db, capsys, pattern):
    with closing(DesignDB(gcd_db)) as db:
        with pytest.raises(QueryError, match='invalid regular expression'):
            ops.search(db, pattern, regex=True)
    args = ['query', 'search', pattern, '--regex', '--db', str(gcd_db)]
    assert main(args) == 2
    output = capsys.readouterr()
    assert not output.out
    assert 'invalid regular expression' in output.err
    assert 'Traceback' not in output.err
    assert main([*args, '--json']) == 2
    output = capsys.readouterr()
    cli = json.loads(output.out)
    assert not output.err
    assert 'invalid regular expression' in cli['error']
    text, _, error = Registry(mcp_tools()).call_json(
        'query_search', {'db': str(gcd_db), 'pattern': pattern, 'regex': True})
    assert error and cli == json.loads(text)


@pytest.fixture(scope='session')
def round23_arrays(tmp_path_factory, capture_classpath):
    root = tmp_path_factory.mktemp('round23-arrays')
    java = str(Path(os.environ['JAVA_HOME']) / 'bin/java')
    result = run_group([java, '-Xss64m', '-cp', capture_classpath,
                        'spinaldb.Round23ArrayFixtures', str(root)],
                       cwd=root, capture=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    return root


@pytest.mark.parametrize('connections', [True, False])
def test_array_phase_diff_cli_mcp(round23_arrays, capsys, connections):
    def path(name):
        return round23_arrays / name / 'design.db'

    with closing(DesignDB(path('array0'))) as a, closing(DesignDB(path('array1'))) as b:
        result = diff(a, b, connections=connections)
    assert result == parity(path('array0'), path('array1'), capsys, connections=connections)
    assert result['summary']['identical'] is True, result['undetermined']
    assert result['undetermined']['count'] == 0
    result = parity(path('array0'), path('changed'), capsys, connections=connections)
    assert result['summary']['identical'] is False
    assert result['emission_config']['changed']
