"""The coverage demo's proof plan (round-4 finding: the resetless demo plan did not say
`"reset": null`, so the stricter vacuity guard refused it and the demo failed)."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil

import pytest

from rvw.cov.proof import elaborate, prove, sanity_plan

EXAMPLE = Path(__file__).resolve().parents[2] / "examples" / "coverage"


def _demo():
    spec = importlib.util.spec_from_file_location("coverage_demo", EXAMPLE / "demo.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.skipif(not shutil.which("yosys"), reason="yosys not on PATH (source spinal-boom/env.sh)")
def test_demo_plan_passes_the_guard(tmp_path):
    plan = _demo().proof_plan(EXAMPLE, "p1")
    assert "reset" in plan and plan["reset"] is None
    netlist = elaborate(tmp_path, [EXAMPLE / s for s in plan["sources"]], (EXAMPLE / "harness.sv").read_text(), plan["top"],
                        yosys=shutil.which("yosys"))
    sanity = sanity_plan(plan, netlist)
    assert "error" not in sanity and sanity["expression"] == "!$initstate && !$stable({y})"
    # Without the statement the guard refuses: `tiny` has no reset port (by register or by name).
    del plan["reset"]
    assert "tiny dut has no reset" in sanity_plan(plan, netlist)["error"]


@pytest.mark.skipif(not all(shutil.which(t) for t in ("sby", "yosys", "z3")),
                    reason="SymbiYosys, yosys and z3 not on PATH (source spinal-boom/env.sh)")
def test_demo_proof_step_excludes_the_point(tmp_path):
    tiny = EXAMPLE / "tiny.sv"
    db = {"schema": "rvw.coverage/1", "point_universe": "u", "source_root": str(EXAMPLE), "source_revision": None,
          "sources": {"tiny.sv": {"path": str(tiny), "sha256": hashlib.sha256(tiny.read_bytes()).hexdigest()}},
          "tests": {"t": {"run": None}},
          "points": [{"id": "p1", "key": "k", "fields": {"f": "tiny.sv", "l": "9", "o": "if"}, "count": 0, "tests": {}}]}
    (tmp_path / "db.json").write_text(json.dumps(db))
    (tmp_path / "plan.json").write_text(json.dumps(_demo().proof_plan(EXAMPLE, "p1")))
    r = prove(tmp_path / "plan.json", tmp_path / "db.json", tmp_path / "proof", timeout=60)
    assert r["sanity"]["passed"] and r["points"][0]["unreachable"], r


def test_demo_does_not_treat_incomplete_mutation_observations_as_earned():
    demo = _demo()
    result = {'status': 'inconclusive', 'cause': 'input_not_captured:mcy_dependencies',
              'counts': {state: 0 for state in ('killed', 'survived', 'equivalent', 'control')},
              'observed_counts': {'killed': 10, 'survived': 13}}
    assert demo.mutation_observations(result) == {'killed': 10, 'survived': 13}
    result['counts']['killed'] = 10
    with pytest.raises(ValueError, match='earned'):
        demo.mutation_observations(result)
