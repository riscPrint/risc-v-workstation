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
