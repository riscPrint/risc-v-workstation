"""Require explicit core selection before native example tests can build RTL."""
import os
from pathlib import Path

import pytest


# These tests use fake launchers or explicitly selected, previously captured RTL.
NO_CORE_BUILD = {"test_vex_project.py", "test_native_engines.py", "test_native_reduction.py"}


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: native example tests")


def pytest_collection_modifyitems(items):
    for item in items:
        if item.path.parent == Path(__file__).parent and item.path.name not in NO_CORE_BUILD:
            item.add_marker(pytest.mark.slow(reason="builds the selected private VexRiscv core"))
            if not os.environ.get("VEXRISCV"):
                item.add_marker(pytest.mark.skip(reason="set VEXRISCV to a private core checkout for native example tests"))
