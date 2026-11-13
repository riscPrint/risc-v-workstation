"""Small schedules test mechanisms, not RTL accuracy."""
from dataclasses import asdict, replace
import json

import pytest
from rvw.ooo.core import Instruction, simulate
from rvw.ooo.structures import check_configuration
from test_ooo import cfg, op


def test_ports_and_register_pressure():
    stream = [op(dst=1), op(dst=2), op(dst=3), op(dst=4)]
    baseline = simulate(stream, cfg())
    ports = simulate(stream, replace(cfg(), ports={"alu": 1}))
    regs = simulate(stream, replace(cfg(), physical_registers=33))
    assert ports["cycles"] > baseline["cycles"]
    assert ports["events"]["port_blocked"] > 0
    assert regs["cycles"] > baseline["cycles"]
    assert regs["events"]["register_full"] > 0


def test_branch_recovery_and_predictor_interface():
    c = replace(cfg(), latencies={"alu": 1, "branch": 2}, branch_penalty=4)
    seq = [Instruction("branch", pc=0, next_pc=16), op()]
    miss = simulate(seq, c)
    class Perfect:
        def predict(self, pc, fallthrough):
            return 16
        def update(self, pc, actual_next):
            assert actual_next == 16
    hit = simulate(seq, c, predictor=Perfect())
    assert miss["events"]["branch_misses"] == 1
    assert hit["events"].get("branch_misses", 0) == 0
    assert miss["cycles"] == hit["cycles"] + 4
    assert hit["cycles"] == 6


def test_forwarding_and_nonalias_loads():
    c = replace(cfg(), memory_policy="disambiguate", latencies={"load": 5, "store": 6})
    st = Instruction("store", address=256, size=8)
    ld = Instruction("load", dest=1, address=256, size=4)
    r = simulate([st, ld], c)
    assert r["events"]["forwarded_loads"] == 1
    assert r["cycles"] < simulate([st, ld], replace(c, memory_policy="ordered"))["cycles"]
    independent = replace(ld, address=512)
    assert simulate([st, independent], c)["cycles"] < simulate([st, independent], replace(c, memory_policy="ordered"))["cycles"]
    partial = replace(ld, address=260, size=8)
    assert simulate([st, partial], c)["events"]["partial_forward_blocked"] > 0


def test_unresolved_store_inputs_block_load():
    c = replace(cfg(), memory_policy="disambiguate", latencies={"alu": 5, "store": 2, "load": 2})
    seq = [op(dst=1), Instruction("store", (1,), address=256, size=8),
           Instruction("load", address=512, size=8)]
    assert simulate(seq, c)["events"]["store_address_blocked"] > 0
    with pytest.raises(ValueError, match="address"):
        simulate([Instruction("load")], c)


def snapshot(c):
    return dict(schema="rvw.ooo-effective/1", source_revision="a"*40, config="tiny",
                parameters=asdict(c), extraction_keys={k: "top."+k for k in asdict(c)},
                required_structures=["integer"])


def test_snapshot_checks_every_field_and_rejects_unsupported(tmp_path):
    c = cfg()
    p = tmp_path / "effective.json"
    data = snapshot(c)
    p.write_text(json.dumps(data))
    assert check_configuration(c, p)["config"] == "tiny"
    for key in asdict(c):
        changed = snapshot(c)
        changed["parameters"][key] = None
        p.write_text(json.dumps(changed))
        with pytest.raises(ValueError, match="drift"):
            check_configuration(c, p)
    for change in ({"required_structures": ["cache"]}, {"extraction_keys": {}}, {"source_revision": "main"}):
        p.write_text(json.dumps({**data, **change}))
        with pytest.raises(ValueError):
            check_configuration(c, p)


@pytest.mark.parametrize("change", [dict(ports={"load": 0}), dict(physical_registers=32),
    dict(branch_penalty=-1), dict(memory_policy="guess"), dict(forwarding_latency=True)])
def test_bad_structure_configuration(change):
    with pytest.raises(ValueError):
        replace(cfg(), **change)


def test_c2_branches_and_snapshot_identity(tmp_path):
    from test_ooo import trace
    from rvw.ooo.core import run
    c = replace(cfg(), latencies={"branch": 2})
    cp, tp, sp = [tmp_path / n for n in ("config", "trace", "snapshot")]
    cp.write_text(json.dumps(asdict(c)))
    trace(tp, insn="0x63")
    sp.write_text(json.dumps(snapshot(c)))
    assert run(cp, tp, effective_config=sp)["events"]["branches"] == 4
    changed = snapshot(c)
    changed["config"] = "other"
    sp.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="C2 selected"):
        run(cp, tp, effective_config=sp)
