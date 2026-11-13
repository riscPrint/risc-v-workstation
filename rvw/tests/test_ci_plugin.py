"""Exercise CI selection with synthetic items. No native tool runs."""
from pathlib import Path
import runpy
from types import SimpleNamespace
import pytest

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]
select = runpy.run_path(str(ROOT / 'scripts/ci_plugin.py'))['pytest_collection_modifyitems']


class Item:
    def __init__(self, nodeid, **markers):
        self.nodeid = nodeid
        self.markers = markers
        self.added = []

    def get_closest_marker(self, name):
        return self.markers.get(name)

    def add_marker(self, marker):
        self.added.append(marker)


def apply(monkeypatch, tier, items, shard='0/1'):
    from rvw.doctor import inventory
    monkeypatch.setattr(inventory, 'report', lambda: [])
    monkeypatch.setenv('RVW_CI_TIER', tier)
    monkeypatch.setenv('CI_SHARD', shard)
    drop = []
    config = SimpleNamespace(hook=SimpleNamespace(pytest_deselected=lambda items: drop.extend(items)))
    select(config, items)
    return drop


def test_absent_native_tool_is_an_explicit_skip(monkeypatch):
    item = Item('formal::tiny', native_light=SimpleNamespace(args=('Yosys',)), slow=True)
    items = [item]
    assert apply(monkeypatch, 'native-light', items) == []
    assert items == [item]
    assert 'Yosys' in item.added[0].kwargs['reason']


def test_nightly_excludes_fast_and_native(monkeypatch):
    slow = Item('slow', slow=True)
    items = [slow, Item('fast', fast=True), Item('native', slow=True, native_light=SimpleNamespace(args=()))]
    drop = apply(monkeypatch, 'nightly', items)
    assert items == [slow]
    assert {item.nodeid for item in drop} == {'fast', 'native'}


def test_slow_shards_are_disjoint_and_complete(monkeypatch):
    shards = []
    for index in range(4):
        items = [Item(f'test::{i}', slow=True) for i in range(40)]
        apply(monkeypatch, 'nightly', items, f'{index}/4')
        shards.append({item.nodeid for item in items})
    assert len(set.union(*shards)) == 40
    assert sum(map(len, shards)) == 40


def test_invalid_shard_fails(monkeypatch):
    with pytest.raises(pytest.UsageError):
        apply(monkeypatch, 'nightly', [], '4/4')
