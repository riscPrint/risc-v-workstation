"""CI-only selection. Ordinary pytest runs keep their existing selection."""
import hashlib
import os
from pathlib import Path
import pytest


def pytest_configure(config):
    config.addinivalue_line('markers', 'native_light(*tools): bounded native fixture; names from the tool inventory')


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config, items):
    tier = os.environ.get('RVW_CI_TIER')
    if tier not in ('native-light', 'nightly'):
        return
    from rvw.doctor.inventory import report
    present = {r['name'] for r in report() if r['status'] == 'installed'}
    index, count = map(int, os.environ.get('CI_SHARD', '0/1').split('/'))
    if not 0 <= index < count:
        raise pytest.UsageError('CI_SHARD must be INDEX/COUNT with 0 <= INDEX < COUNT')
    keep, drop = [], []
    for item in items:
        native = item.get_closest_marker('native_light')
        selected = bool(native) if tier == 'native-light' else bool(item.get_closest_marker('slow')) and not native
        selected = selected and int(hashlib.sha256(item.nodeid.encode()).hexdigest(), 16) % count == index
        if not selected:
            drop.append(item)
            continue
        if native:
            missing = set(native.args) - present
            if missing:
                item.add_marker(pytest.mark.skip(reason='CI inventory missing: ' + ', '.join(sorted(missing))))
        keep.append(item)
    config.hook.pytest_deselected(items=drop)
    items[:] = keep
