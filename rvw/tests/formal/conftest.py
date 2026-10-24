"""Formal helper tests use the same captured input interface as the CLI."""
from types import SimpleNamespace

import pytest

from rvw.formal import common
from rvw.formal.snapshot import InputSnapshot


@pytest.fixture
def probe_ports():
    def probe(files, top, out, timeout=None):
        snapshot = InputSnapshot(SimpleNamespace(verilog=files, checks=None), out)
        return common.module_ports(snapshot.sources, top, out, timeout, snapshot=snapshot)
    return probe
