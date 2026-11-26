"""All providers declare effects; arch_sched_study lacks its llvm-mca inventory ID."""
import json
from pathlib import Path
import pytest
from rvw.mcp.audit import audit, debt
from rvw.mcp.registry import Registry

pytestmark = pytest.mark.fast
GAPS = {'arch_sched_study': 'llvm-mca'}


def test_only_named_inventory_gaps_remain():
    registry, problems = Registry.discover()
    assert not problems
    report = audit(registry)
    actual = {row['name'] for row in report['tools'] if row['findings']}
    assert actual == GAPS.keys()
    for row in report['tools']:
        assert row['side_effects'], row['name']
        for finding in row['findings']:
            assert finding['code'] == 'native_tools', row
            assert GAPS[row['name']] in row['side_effects']
    baseline = Path(__file__).with_name('data') / 'mcp-audit-baseline.json'
    assert json.loads(baseline.read_text()) == debt(report)


def test_replay_and_formal_discovery_stay_valid():
    registry, problems = Registry.discover()
    assert not problems
    rows = {row['name']: row for row in audit(registry)['tools']}
    assert not rows['formal_bmc']['findings']
    assert not rows['replay_pack']['findings']
    # Git is a base installer prerequisite, not an optional inventory ID.
    assert 'Git' in rows['replay_pack']['side_effects']
    assert registry.tools['replay_pack'].native_tools == ()
