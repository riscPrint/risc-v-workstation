"""A core need not implement range matching to support trigger chains."""
import pytest
from rvw.debug import checks, profile, suite

pytestmark = pytest.mark.fast


def test_equality_only_trigger_chain():
    p = profile.normalize({'scratch': 0x80010000, 'triggers': {
        'count': 2, 'types': [2], 'matches': [0], 'chain': True}})
    driver, dm = suite.model_driver(p)
    result = suite.run_one(suite.CHECKS['trig.chain'], p, driver)
    assert result['status'] == 'pass', result
    assert result['observations']['equality_chain'] == [0x10, 0x20]
