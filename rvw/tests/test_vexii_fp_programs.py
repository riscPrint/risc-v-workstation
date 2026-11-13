import importlib.util
from pathlib import Path
import pytest
pytestmark = pytest.mark.fast
FILE = Path(__file__).resolve().parents[2] / 'examples/vexiiriscv/rvw/fpu/programs.py'

def test_class_cross_and_repeatable_random_operands():
    spec = importlib.util.spec_from_file_location('fp_programs', FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    first = module.arithmetic(32, 7, 2)
    assert first == module.arithmetic(32, 7, 2)
    assert first != module.arithmetic(32, 8, 2)
    assert first.count('  csrw fcsr, zero') == 38 * 5 * 5
    assert 'fsqrt.s f0, f1, rmm' in first
