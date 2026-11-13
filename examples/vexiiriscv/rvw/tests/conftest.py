"""Require explicit core selection before native example tests can build RTL."""
import os
from pathlib import Path

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "slow: native example tests")


def pytest_collection_modifyitems(items):
    for item in items:
        if item.path.parent == Path(__file__).parent and item.path.name != "test_vexii_project.py":
            item.add_marker(pytest.mark.slow(reason="builds the selected private VexiiRiscv core"))
            if not os.environ.get("VEXIIRISCV"):
                item.add_marker(pytest.mark.skip(reason="set VEXIIRISCV to a private core checkout for native example tests"))
