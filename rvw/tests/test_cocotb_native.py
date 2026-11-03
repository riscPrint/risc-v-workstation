"""Small native conformance cases. No core checkout is required."""
import importlib.util
import json
from pathlib import Path
import shutil
import pytest

from rvw.sim.cocotb import run


@pytest.mark.parametrize('backend', ['icarus', 'verilator'])
def test_native_semantics(tmp_path, backend):
    if not importlib.util.find_spec('cocotb') or not shutil.which('iverilog' if backend == 'icarus' else backend):
        pytest.skip('optional cocotb or native backend absent')
    fixture = Path(__file__).parent / 'fixtures' / 'cocotb'
    request = dict(schema='rvw.cocotb/1', name='semantics', backend=backend,
                   top='semantics', sources=[str(fixture / 'semantics.v')],
                   python_paths=[str(fixture)], test_module='semantic_bench',
                   requires=['timer', 'clock'], clock=dict(signal='clk', period_ns=10),
                   reset=dict(signal='reset', active=1, cycles=2))
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(json.dumps(request))
    result = run(manifest, tmp_path / 'out', timeout=120)
    assert [t['status'] for t in result['tests']] == ['pass', 'pass'], (tmp_path / 'out/run.log').read_text()
