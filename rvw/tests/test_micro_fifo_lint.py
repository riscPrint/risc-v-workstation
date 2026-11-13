"""Native lint of queue monitors must handle idle and simultaneous transfers."""
import shutil
import subprocess
import pytest
from rvw.formal.micro_checks import render

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('kind', ['fifo_order', 'fifo_flush'])
def test_fifo_case_covers_all_transfer_combinations(tmp_path, kind):
    verilator = shutil.which('verilator')
    if verilator is None:
        pytest.skip('Verilator is not installed')
    source = tmp_path / f'rvw_{kind}.sv'
    source.write_text(render(kind, 32, 8))
    result = subprocess.run([verilator, '--lint-only', '--assert', '-Wall', '-Wno-fatal',
                             '--top-module', f'rvw_{kind}', str(source)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    assert 'CASEINCOMPLETE' not in result.stderr
