"""Explicit slow marks take precedence over the legacy module allowlist."""
from pathlib import Path

import pytest

pytestmark = pytest.mark.fast


def test_explicit_slow_test_in_legacy_fast_module_stays_slow(request):
    path = Path(__file__).with_name('conftest.py').resolve()
    root = next(plugin for plugin in request.config.pluginmanager.get_plugins()
                if getattr(plugin, '__file__', None) and Path(plugin.__file__).resolve() == path)
    HERE = path.parent
    pytest_collection_modifyitems = root.pytest_collection_modifyitems

    class Item:
        path = HERE / 'test_perf.py'
        markers = {'slow': pytest.mark.slow}

        def get_closest_marker(self, name):
            return self.markers.get(name)

        def add_marker(self, name):
            self.markers[name] = name

    item = Item()
    pytest_collection_modifyitems([item])
    assert item.get_closest_marker('slow')
    assert not item.get_closest_marker('fast')
