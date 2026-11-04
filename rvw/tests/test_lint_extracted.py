"""Run after Test/runMain spinaldb.LintFixtures. No synthetic data in this check."""
import os
from pathlib import Path
import pytest
from rvw.query.db import run_on
from rvw.lint.structural import analyze


@pytest.mark.parametrize('name,expected', [
    ('single', set()), ('unsafe', {'cdc.unsynchronized'}),
    ('sync', {'cdc.sync_candidate'}), ('bus', {'cdc.multi_bit'}),
    ('reset-shared', set()), ('reset-independent', {'rdc.independent_reset', 'rdc.release_order_unproved'}),
    ('reset-async', {'rdc.independent_reset', 'rdc.async_release_unproved', 'rdc.release_order_unproved'}),
])
def test_extracted_reference(name, expected):
    root = os.environ.get('RVW_LINT_FIXTURES')
    if not root:
        pytest.skip('set RVW_LINT_FIXTURES to the extracted reference directory')
    result = run_on(Path(root) / name / 'design.db', analyze)
    assert {f['rule'] for f in result['findings']} == expected
    assert result['status'] == 'inconclusive'


@pytest.mark.parametrize('name,fifo,broken', [
    ('handshake',False,False), ('handshake-broken',False,True),
    ('fifo',True,False), ('fifo-broken',True,True)])
def test_extracted_protocol_topology(name, fifo, broken):
    root = os.environ.get('RVW_LINT_FIXTURES')
    if not root:
        pytest.skip('set RVW_LINT_FIXTURES to the extracted reference directory')
    declaration = dict(kind='async_fifo' if fifo else 'handshake',
                       forward=['a_source','b_first','b_last'],
                       reverse=['b_source','reverse_first','reverse_last'])
    if fifo:
        declaration.update(memory='storage', encoding='gray')
    result = run_on(Path(root) / name / 'design.db', lambda db: analyze(db, {'protocols':[declaration]}))
    assert f"cdc.{declaration['kind']}_" + ('invalid' if broken else 'candidate') in {f['rule'] for f in result['findings']}
    assert result['status'] == 'inconclusive'


@pytest.mark.parametrize('name,merge', [('separate',False), ('reconverge',True)])
def test_extracted_merge(name, merge):
    root = os.environ.get('RVW_LINT_FIXTURES')
    if not root:
        pytest.skip('set RVW_LINT_FIXTURES to the extracted reference directory')
    result = run_on(Path(root) / name / 'design.db', analyze)
    assert ('cdc.reconvergence' in {f['rule'] for f in result['findings']}) == merge


@pytest.mark.parametrize('ordered', [False,True])
def test_extracted_release_order(ordered):
    root = os.environ.get('RVW_LINT_FIXTURES')
    if not root:
        pytest.skip('set RVW_LINT_FIXTURES to the extracted reference directory')
    def check(db):
        domains = list(db.conn.execute('SELECT reset_key FROM clock_domains ORDER BY id'))
        intent = {'reset_order': [[domains[0][0], domains[1][0]]]} if ordered else {}
        return analyze(db, intent)
    result = run_on(Path(root) / 'reset-independent/design.db', check)
    assert ('rdc.release_order_unproved' in {f['rule'] for f in result['findings']}) != ordered
