"""Cross-check portable single-hart assertions on two reference models.

These are reference tests. They supply no DUT or independent bus evidence.
"""
import importlib.util
from pathlib import Path

import pytest
from cosim_build import _build
from model_fixtures import generate, Sail
from rvw.cosim.checker import check

SPEC = importlib.util.spec_from_file_location('ordering_reference_suite',
    Path(__file__).resolve().parents[3] / 'RiscvSim/tests/ordering/suite.py')
suite = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(suite)


# Extension generators need explicit ISA/CMO profiles and have dedicated tests
# under tests/ordering. Keep this base-profile cross-model corpus portable.
@pytest.mark.parametrize('name', [*suite.DEFAULT_SUITES, 'amo-fault'])
def test_spike_sail_ordering(tmp_path_factory, tmp_path, integer_platform, sail, name):
    platform = integer_platform
    source = tmp_path / (name + '.S')
    source.write_text(suite.GENERATORS[name](64, 7))
    elf = _build(tmp_path_factory, source, march='rv64ima_zicsr_zifencei')
    trace = tmp_path / 'reference.jsonl'
    assert generate(elf, trace, platform, 100000 if name == 'amo-fault' else 20000)['termination'] == 'pass'
    model = Sail(platform, elf, trace, sail)
    try:
        result = check(trace, model, platform)
    finally:
        model.close()
    assert result['status'] == 'match', result
    assert result['trace_complete'] and result['end_status'] == 'pass', result
