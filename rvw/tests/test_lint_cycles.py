"""Wire cycles cannot form a CDC or reset synchronizer chain."""
import subprocess
import sys
import sqlite3

import pytest

from lint_builder import Builder
from rvw.lint.cdc import Crossings
from rvw.lint.graph import Design

pytestmark = pytest.mark.fast

CHECK = '''
import sqlite3
import sys
from rvw.lint.cdc import Crossings
from rvw.lint.graph import Design
from rvw.lint.rdc import _chain
from rvw.lint import structural
from rvw.query.db import run_on

path, method = sys.argv[1:]
if method == 'report':
    report = run_on(path, structural.analyze)
    assert report['status'] == 'inconclusive'
    domain = report['rdc']['domains'][0]
    assert domain['release'] == 'unsynchronized'
    assert domain['synchronizers'] == [None]
    assert any(f['rule'] == 'rdc.async_release_unsynchronized' for f in report['findings'])
else:
    with sqlite3.connect(path) as conn:
        design = Design(conn)
        root = design.by_path['a']
        if method == 'reset':
            result = _chain(design, root, 'clk:Bool')
        else:
            result = getattr(Crossings(design, None), method)(root)
        assert result is None
print('completed')
'''


@pytest.mark.parametrize('method', ['simple_up', 'simple_down', 'reset', 'report'])
def test_single_input_wire_cycle_terminates(tmp_path, method):
    builder = Builder(tmp_path / 'cycle.db')
    builder.domain(1, reset='a', kind='ASYNC')
    builder.sig('clk', direction='in', role='clock')
    builder.sig('a', role='reset')
    builder.sig('b')
    builder.reg('user', 1)
    builder.edge('a', 'b')
    builder.edge('b', 'a')
    path = builder.done()
    # Run out of process so a regression fails within a bound rather than hanging pytest.
    result = subprocess.run([sys.executable, '-c', CHECK, str(path), method],
                            capture_output=True, text=True, timeout=5, check=True)
    assert result.stdout == 'completed\n'


def test_register_feedback_still_ends_at_register(tmp_path):
    builder = Builder(tmp_path / 'feedback.db')
    builder.domain(1)
    root = builder.reg('state', 1)
    builder.edge('state', 'state')
    path = builder.done()
    conn = sqlite3.connect(path)
    try:
        crossings = Crossings(Design(conn), None)
        assert crossings.simple_up(root) == root
        assert crossings.simple_down(root) == root
    finally:
        conn.close()
