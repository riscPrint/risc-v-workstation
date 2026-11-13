import importlib.util
from pathlib import Path
import pytest

pytestmark = pytest.mark.fast
spec = importlib.util.spec_from_file_location('smp_programs', Path(__file__).parents[1]/'programs.py')
programs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(programs)


def test_atomic_matrix():
    text = programs.assembly(1, 'amo')
    instructions = [line for line in text.splitlines() if line.startswith('amo')]
    assert len(instructions) == 9*2*4
    assert len(set(instructions)) == 72
    assert text.count('bne t2, t0, fail') == 72
    assert text.count('bne t3, t4, fail') == 72
    assert 'csrr a0, mhartid\nli t0, 1\nbne a0, t0, fail' in text


def test_lrsc_success_retry_and_failure_checks():
    text = programs.assembly(0, 'lrsc')
    for width in ['w', 'd']:
        assert f'bnez t3, retry_{width}' in text
        assert f'sc.{width} t3, t0, (s0)\nbeqz t3, fail' in text
    assert text.count('bne t4, t2, fail') == 4


def test_invalid_hart_count_does_not_create_outputs(tmp_path):
    with pytest.raises(ValueError):
        programs.build(tmp_path/'bad', harts=1)
    assert not (tmp_path/'bad').exists()
