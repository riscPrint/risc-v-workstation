"""Round-21 anonymous Area regressions."""
from contextlib import closing
import os
from pathlib import Path

import pytest

from test_query_capture import capture_classpath
from test_query_round19 import parity
from rvw.common.proc import run_group
from rvw.query.db import DesignDB
from rvw.query.diff import diff


@pytest.fixture(scope='session')
def round21(tmp_path_factory, capture_classpath):
    root = tmp_path_factory.mktemp('round21')
    java = str(Path(os.environ['JAVA_HOME']) / 'bin/java')
    result = run_group([java, '-Xss64m', '-cp', capture_classpath, 'spinaldb.Round21Fixtures', str(root)],
                       cwd=root, capture=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    return root


@pytest.mark.parametrize('connections', [True, False])
@pytest.mark.parametrize('other', [0, 1])
def test_anonymous_area_is_identical(round21, capsys, connections, other):
    paths = [round21 / f'area{n}/design.db' for n in (0, other)]
    with closing(DesignDB(paths[0])) as a, closing(DesignDB(paths[1])) as b:
        result = diff(a, b, connections=connections)
    assert result == parity(*paths, capsys, connections=connections)
    assert result['summary']['identical'] is True, result['undetermined']
