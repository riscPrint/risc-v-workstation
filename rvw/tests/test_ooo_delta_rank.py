"""Rank comparison uses step-normalized RTL elasticity and retains ties."""
from pathlib import Path
import runpy
import pytest

pytestmark = pytest.mark.fast
agreement = runpy.run_path(str(Path(__file__).resolve().parents[2] /
                              "examples/naxriscv/rvw/arch/rank.py"))["agreement"]


def test_rank_agreement_and_ties():
    sensitivity = {"ranking": [{"parameter": "a", "baseline_value": 16, "sensitivity": 2},
                                {"parameter": "b", "baseline_value": 16, "sensitivity": 1}]}
    matrix = [{"variant": "base", "cycles": 100},
              {"variant": "a", "cycles": 200, "changes": {"a": 8}},
              {"variant": "b", "cycles": 110, "changes": {"b": 8}}]
    result = agreement(sensitivity, matrix)
    assert result["kendall_tau_b"] == 1
    assert result["rows"][0]["measured_elasticity"] == 1
    sensitivity["ranking"][0]["sensitivity"] = 1
    result = agreement(sensitivity, matrix)
    assert result["model_ties"] == 1
    assert result["kendall_tau_b"] is None
