"""Reject upstream environment changes that remove the initialization anchor."""
import importlib.util
from pathlib import Path
import pytest

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('dv_baseline', ROOT/'scripts/riscv-dv-baseline.py')
baseline = importlib.util.module_from_spec(spec); spec.loader.exec_module(baseline)


def test_baseline_refuses_an_unknown_environment_header():
    with pytest.raises(ValueError, match='one reset-vector jump'):
        baseline.header('unrecognized upstream reset sequence')
