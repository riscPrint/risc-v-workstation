"""Proof exclusions: the vacuity guard (review finding: a harness holding reset forever made a
reachable point "unreachable")."""
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from rvw.cov.proof import _identifiers, apply_exclusions, elaborate as _elaborate, harness_inputs, point_cone, prove, sanity_plan


def elaborate(*args, **kwargs):
    """Select Yosys explicitly for direct netlist tests."""
    return _elaborate(*args, **kwargs, yosys=shutil.which("yosys"))


DUT = """module dut(input clk, input reset, input a, output reg q = 0);
  always @(posedge clk) if (reset) q <= 0; else if (a) q <= 1;
endmodule
"""
STUCK = """module h(input clk, input a);
  reg reset = 1;
  always @(posedge clk) reset <= reset;   // never leaves reset: over-constrained environment
  wire q;
  dut d(.clk(clk), .reset(reset), .a(a), .q(q));
  always @(posedge clk) begin
    // RVW_POINT
  end
endmodule
"""
GOOD = STUCK.replace("reg reset = 1;", "reg reset = 1;\n  always @(posedge clk) reset <= 0;").replace(
    "  always @(posedge clk) reset <= reset;   // never leaves reset: over-constrained environment\n", "")
TINY = """module tiny(input clk, input a, output reg [1:0] s = 0);
  always @(posedge clk) s <= (s == 2) ? 0 : s + 1;
endmodule
module h(input clk, input a);
  wire [1:0] s;
  tiny t(.clk(clk), .a(a), .s(s));
  always @(posedge clk) begin
    // RVW_POINT
  end
endmodule
"""


def _setup(tmp_path, harness, expression, dut=DUT, extra=None):
    (tmp_path / "dut.v").write_text(dut)
    (tmp_path / "harness.sv").write_text(harness)
    sha = hashlib.sha256(dut.encode()).hexdigest()
    src = str((tmp_path / "dut.v").resolve())
    db = {"schema": "rvw.coverage/1", "point_universe": "u", "source_root": str(tmp_path.resolve()), "source_revision": None,
          "sources": {"dut.v": {"path": src, "sha256": sha}}, "tests": {"t": {"run": None}},
          "points": [{"id": "p1", "key": "k", "fields": {"f": "dut.v", "l": "2"}, "count": 0, "tests": {}}]}
    (tmp_path / "db.json").write_text(json.dumps(db))
    cfg = {"sources": ["dut.v"], "harness": "harness.sv", "top": "h", "depth": 8,
           "points": [{"point_id": "p1", "expression": expression, "reason": "test"}], **(extra or {})}
    (tmp_path / "cfg.json").write_text(json.dumps(cfg))
    return tmp_path / "cfg.json", tmp_path / "db.json"


needs_sby = pytest.mark.skipif(not all(shutil.which(t) for t in ("sby", "yosys", "z3")),
                               reason="SymbiYosys, yosys and z3 not on PATH (source spinal-boom/env.sh)")
needs_yosys = pytest.mark.skipif(not shutil.which("yosys"), reason="yosys not on PATH (source spinal-boom/env.sh)")


def _plan(tmp_path, config, harness, dut=DUT):
    """`sanity_plan` on the harness as the solver elaborates it (Yosys, same files)."""
    work = tmp_path / f"e{len(list(tmp_path.glob('e*')))}"
    work.mkdir()
    (work / "dut.v").write_text(dut)
    return sanity_plan({"top": "h", **config}, elaborate(work / "out", [work / "dut.v"], harness, config.get("top", "h"), clock=config.get("clock", "clk")))


@needs_sby
def test_reset_held_forever_excludes_nothing(tmp_path):
    cfg, db = _setup(tmp_path, STUCK, "q == 1")
    r = prove(cfg, db, tmp_path / "w", timeout=60)
    point = r["points"][0]
    # The solver still proves q never becomes 1 under this harness ...
    assert point["jobs"]["prove"]["status"] == "PASS" and point["jobs"]["cover"]["status"] == "FAIL"
    # ... but the sanity cover shows the environment never leaves reset: no exclusion.
    assert r["sanity"]["status"] == "FAIL" and not r["sanity"]["passed"]
    assert not point["unreachable"] and "vacuous" in point["refused"]


@needs_sby
def test_working_harness_still_excludes_and_reachable_point_does_not(tmp_path):
    cfg, db = _setup(tmp_path, GOOD, "q == 1")
    r = prove(cfg, db, tmp_path / "w", timeout=60)
    assert r["sanity"]["passed"] and not r["points"][0]["unreachable"]  # q == 1 is reachable here
    # A modulo-3 counter never reaches 3: still excluded, without a reset in the harness.
    sub = tmp_path / "counter"
    sub.mkdir()
    dut, harness = TINY.split("module h")
    cfg, db = _setup(sub, "module h" + harness, "s == 2'd3", dut=dut, extra={"reset": None})  # states: no reset
    r = prove(cfg, db, sub / "w", timeout=60)
    assert r["sanity"]["reset"] is None and r["sanity"]["passed"] and r["points"][0]["unreachable"]
    (sub / "excl.json").write_text(json.dumps(r))
    excluded = apply_exclusions(json.loads(db.read_text()), sub / "excl.json")
    assert excluded["points"][0]["exclusion"]["point_id"] == "p1"


@needs_sby
@pytest.mark.parametrize('location', ['harness', 'dut'])
def test_unrelated_unreachable_cover_does_not_block_exclusion(tmp_path, location):
    dut, harness = TINY.split('module h')
    harness = 'module h' + harness
    if location == 'harness':
        harness = harness.replace('// RVW_POINT', "cover (s == 2'd3);\n// RVW_POINT")
    else:
        dut = dut.replace('endmodule', "always @(posedge clk) cover (s == 2'd3);\nendmodule")
    cfg, db = _setup(tmp_path, harness, "s == 2'd3", dut=dut, extra={'reset': None})
    result = prove(cfg, db, tmp_path / 'w', timeout=20)
    assert result['sanity']['passed'], result['sanity']
    point = result['points'][0]
    assert point['cone']['passed'], point
    assert point['unreachable'], point
    applied = apply_exclusions(json.loads(db.read_text()), tmp_path / 'w/exclusions.json')
    assert applied['points'][0]['exclusion']['point_id'] == 'p1'


@needs_sby
@pytest.mark.parametrize('location', ['harness', 'dut'])
def test_existing_reachable_cover_cannot_mask_vacuous_sanity(tmp_path, location):
    # The free input can satisfy the user cover even though reset holds q forever.
    dut, harness = DUT, STUCK
    if location == 'harness':
        harness = harness.replace('// RVW_POINT', 'cover (a);\n// RVW_POINT')
    else:
        dut = dut.replace('endmodule', 'always @(posedge clk) cover (a);\nendmodule')
    cfg, db = _setup(tmp_path, harness, 'q == 1', dut=dut)
    result = prove(cfg, db, tmp_path / 'w', timeout=20)
    assert not result['sanity']['passed']
    assert result['sanity']['status'] == 'FAIL'
    assert not result['points'][0]['unreachable']
    applied = apply_exclusions(json.loads(db.read_text()), tmp_path / 'w/exclusions.json')
    assert 'exclusion' not in applied['points'][0]


@needs_yosys
def test_cover_isolation_preserves_assumptions_and_assertions(tmp_path):
    from collections import Counter
    from rvw.common.proc import run_group
    from rvw.cov.proof import _job_harness, _sby_text

    dut, harness = TINY.split('module h')
    properties = 'always @(posedge clk) begin assume(a); assert(a || s != 2); cover(s == 3); end\n'
    source = tmp_path / 'dut.v'
    source.write_text(dut.replace('endmodule', properties + 'endmodule'))
    harness = ('module h' + harness).replace('endmodule', properties + 'endmodule')
    harness_path = tmp_path / 'sanity.sv'
    harness_path.write_text(_job_harness(harness, 'cover (!$initstate && !$stable(s));', 1))
    sby = _sby_text('cover', 8, 20, [source, harness_path], 'h', isolated_covers=1)
    script = sby.split('[script]\n')[1].split('\n[files]')[0] + '\nwrite_json isolated.json\n'
    result = run_group([shutil.which('yosys'), '-Q', '-T', '-p', script], cwd=tmp_path,
                       capture=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    modules = json.loads((tmp_path / 'isolated.json').read_text())['modules']
    kinds = Counter(cell.get('parameters', {}).get('FLAVOR') if cell['type'] == '$check'
                    else cell['type'].removeprefix('$')
                    for body in modules.values() for cell in body['cells'].values())
    assert kinds['cover'] == 1
    assert kinds['assume'] == 2
    assert kinds['assert'] == 2


RENAMED = STUCK.replace("reg reset = 1;", "reg hold = 1;").replace("reset <= reset;", "hold <= hold;").replace(
    ".reset(reset)", ".reset(hold)")


@needs_sby
def test_renamed_reset_held_forever_excludes_nothing(tmp_path):
    # Round-2 finding (/tmp/review2-design/prove/v3): the reset is `hold`, wired to `.reset(hold)`, and
    # the point reads the free harness input `a`. The default sanity cover was `!$stable({a, q})`,
    # reachable by toggling `a`, so a reachable point was excluded.
    cfg, db = _setup(tmp_path, RENAMED, "a && q")
    r = prove(cfg, db, tmp_path / "w", timeout=60)
    assert r["sanity"]["reset"] == "hold" and r["sanity"]["state"] == ["q"] and r["sanity"]["ignored_inputs"] == ["a"]
    assert not r["sanity"]["passed"] and not r["points"][0]["unreachable"] and "vacuous" in r["points"][0]["refused"]


CLR_DUT = DUT.replace("input reset", "input clr").replace("if (reset)", "if (clr)")
CLR = RENAMED.replace(".reset(hold)", ".clr(hold)")  # the reset port is not named like a reset


@needs_sby
def test_no_reset_found_refuses_unless_stated(tmp_path):
    # A reset the guard cannot see must not be taken as "no reset". Since round 8 a port that resets
    # a register is a reset whatever its name: `clr` is found and the held reset shows.
    cfg, db = _setup(tmp_path, CLR, "a && q", dut=CLR_DUT)
    r = prove(cfg, db, tmp_path / "w", timeout=60)
    assert r["sanity"]["resets"] == [{"expression": "hold", "active_low": False}]
    assert not r["sanity"]["passed"] and not r["points"][0]["unreachable"] and "vacuous" in r["points"][0]["refused"]
    # A port that resets nothing through plain logic and is not named like a reset: not seen, refused.
    gated = CLR_DUT.replace("if (clr)", "if (clr & a)")
    p = _plan(tmp_path, {"points": [{"expression": "a && q"}]}, CLR, dut=gated)
    # (Since round 13 `resets` also lists `a`: with `hold` bound to 1, `clr & a` is a reset by `a`.)
    assert p["expression"] is None and "no reset found" in p["error"], p
    # Stated by the user: the sanity cover runs and shows the environment never leaves reset.
    sub = tmp_path / "stated"
    sub.mkdir()
    cfg, db = _setup(sub, CLR, "a && q", dut=CLR_DUT, extra={"reset": "hold", "reset_active_low": False})
    r = prove(cfg, db, sub / "w", timeout=60)
    assert r["sanity"]["status"] == "FAIL" and not r["points"][0]["unreachable"]


@needs_sby
def test_hierarchical_or_unknown_names_in_sanity_refuse(tmp_path):
    # Yosys makes `d.q` a free undriven wire: a cover on it is trivially reachable. Every name the
    # sanity state reads must be a net of the elaborated harness top (round 7: `$stable({x})` on an
    # undeclared `x` passed without any free-wire warning).
    cfg, db = _setup(tmp_path, STUCK, "q == 1", extra={"sanity_state": ["d.q"]})
    r = prove(cfg, db, tmp_path / "w", timeout=60)
    assert "d.q" in r["sanity"]["error"] and not r["sanity"]["passed"] and not r["points"][0]["unreachable"]
    assert "not signals of the harness top" in _plan(tmp_path, {"points": [{"expression": "q"}],
                                                                "sanity_state": ["undeclared"]}, STUCK)["error"]


@needs_sby
def test_exclusions_without_sanity_are_rejected(tmp_path):
    dut, harness = TINY.split('module h')
    cfg, db = _setup(tmp_path, 'module h' + harness, "s == 2'd3", dut=dut, extra={'reset': None})
    evidence = prove(cfg, db, tmp_path / 'w')
    data = json.loads(db.read_text())
    assert evidence['points'][0]['unreachable']
    good_sanity = evidence.pop('sanity')
    target = tmp_path / 'e.json'
    for sanity in (None, {**good_sanity, 'status': 'FAIL', 'passed': False}):
        if sanity is not None:
            evidence['sanity'] = sanity
        target.write_text(json.dumps(evidence))
        with pytest.raises(ValueError, match='vacuity'):
            apply_exclusions(data, target)
    evidence['sanity'] = good_sanity
    target.write_text(json.dumps(evidence))
    assert apply_exclusions(data, target)['points'][0]['exclusion']
    cone = evidence['points'][0]['cone']
    for edit in ({'cone': None}, {'cone': {**cone, 'status': 'FAIL', 'passed': False}},
                 {'cone': {**cone, 'signals': []}}, {'cone': {**cone, 'problems': ['x']}}):
        target.write_text(json.dumps({**evidence, 'points': [{**evidence['points'][0], **edit}]}))
        with pytest.raises(ValueError, match='cone cover'):
            apply_exclusions(data, target)
    target.write_text(json.dumps(evidence))
    path = Path(cone['harness'])
    original = path.read_text()
    path.write_text('edited')
    with pytest.raises(ValueError, match='changed proof evidence'):
        apply_exclusions(data, target)
    path.write_text(original)
    Path(good_sanity['directory'], 'status').write_text('PASS edited')
    with pytest.raises(ValueError, match='changed proof evidence'):
        apply_exclusions(data, target)


LOW_DUT = DUT.replace("input reset", "input rst_n").replace("if (reset)", "if (!rst_n)")


@needs_yosys
def test_sanity_plan(tmp_path):
    assert _identifiers("y == 5'd31 && $past(q) && dut.s != 2'b11") == ["y", "q", "dut.s"]
    p = _plan(tmp_path, {"points": [{"expression": "q == 1"}]}, STUCK)
    assert p["expression"] == "!$initstate && !(reset) && !$stable({q})", p
    assert p["instances"] == [{"instance": "d", "module": "dut",
                               "resets": [{"port": "reset", "expression": "reset", "active_low": False}]}]
    # A harness declaration named like a reset is not evidence that the design gets it (round 4).
    low = _plan(tmp_path, {"points": [{"expression": "q"}]}, "module h(input clk, input rst_n);\nreg q;\n// RVW_POINT\nendmodule")
    assert low["expression"] is None and "no reset found" in low["error"]
    low = _plan(tmp_path, {"points": [{"expression": "q"}]},
                "module h(input clk, input rst_n);\n wire q; dut d(.clk(clk), .rst_n(rst_n), .a(1'b0), .q(q));\nendmodule",
                dut=LOW_DUT)
    assert low["reset"] == "rst_n" and low["expression"].startswith("!$initstate && (rst_n)"), low
    # Reset through an instance connection (also inverted); harness inputs are not state.
    h = "module h(input clk, input [3:0] a, input b, input go);\n wire q;\n dut d(.clk(clk), .rst_n(go), .a(a[0]), .q(q));\nendmodule"
    p = _plan(tmp_path, {"points": [{"expression": "a == 1 && b && q"}]}, h, dut=LOW_DUT)
    assert p["expression"] == "!$initstate && (go) && !$stable({q})" and p["ignored_inputs"] == ["a", "b"]
    p = _plan(tmp_path, {"points": [{"expression": "q"}]}, h.replace(".rst_n(go)", ".rst_n(!go)"), dut=LOW_DUT)
    assert p["expression"] == "!$initstate && (!(go)) && !$stable({q})", p
    # Only inputs read: nothing to check. No reset anywhere and none stated: refused.
    assert "no state" in _plan(tmp_path, {"points": [{"expression": "a"}], "reset": "r", "reset_active_low": False}, h, dut=LOW_DUT)["error"]
    assert "no reset found" in _plan(tmp_path, {"points": [{"expression": "q"}]}, "module h(input clk);\nreg q;\nendmodule")["error"]
    assert _plan(tmp_path, {"points": [{"expression": "q"}], "reset": None}, "module h(input clk);\nreg q;\nendmodule")[
        "expression"] == "!$initstate && !$stable({q})"
    assert _plan(tmp_path, {"points": [{"expression": "1'b0"}], "sanity_state": ["s"], "reset": "!go", "reset_active_low": False, "clock": "go"},
                 "module h(input go);\nreg s;\nendmodule")["expression"] == "!$initstate && !(!go) && !$stable({s})"
    # Yosys cannot elaborate: refused even with the reset stated (the plan has no netlist to trust).
    assert "could not elaborate" in _plan(tmp_path, {"points": [{"expression": "q"}], "reset": "go", "reset_active_low": False},
                                          "module h(input go); reg q; nosuch n(.x(go)); endmodule")["error"]


def _safe(plan, real="hold"):
    """The plan never accepts a reset set that leaves out the DUT's real reset."""
    return plan["expression"] is None or any(r["expression"] == real for r in plan["resets"])


POSITIONAL = """module h(input clk, input rst, input a);
  reg hold = 1;
  always @(posedge clk) hold <= hold;   // DUT never leaves reset
  reg [3:0] cnt = 0;
  always @(posedge clk) if (rst) cnt <= 0; else cnt <= cnt + 1;  // harness bookkeeping uses rst
  wire q;
  dut d(clk, hold, a, q);               // positional connection
  always @(posedge clk) begin
    // RVW_POINT
  end
endmodule
"""


@needs_sby
def test_positional_instance_refuses_unless_reset_is_stated(tmp_path):
    # Round-3 finding: with ports connected by position the guard picked the harness's own `rst`
    # and a harness counter made the sanity cover pass while the DUT was held in reset forever.
    # Now the netlist binds the positional `hold` to the DUT's reset port: the sanity cover fails.
    cfg, db = _setup(tmp_path, POSITIONAL, "a && q && cnt != 0")
    r = prove(cfg, db, tmp_path / "w", timeout=60)
    assert r["sanity"]["resets"] == [{"expression": "hold", "active_low": False}]
    assert not r["sanity"]["passed"] and not r["points"][0]["unreachable"] and "vacuous" in r["points"][0]["refused"]
    sub = tmp_path / "stated"
    sub.mkdir()
    cfg, db = _setup(sub, POSITIONAL, "a && q && cnt != 0", extra={"reset": "hold", "reset_active_low": False})
    r = prove(cfg, db, sub / "w", timeout=60)
    assert not r["points"][0]["unreachable"]


# Round-4 finding (/tmp/review4-design/positional-inline): the positional instance shares its line
# with a declaration, so the line-start scan missed it and the harness's own `rst` was taken.
SAME_LINE = POSITIONAL.replace("  wire q;\n  dut d(clk, hold, a, q);", "  wire q; dut d(clk, hold, a, q);")


@needs_yosys
def test_positional_instance_is_read_from_the_netlist(tmp_path):
    # Round 3/4: ports connected by position. Yosys binds them to the DUT's ports, so the real reset
    # `hold` is found wherever the instance sits; the harness's own `rst` is never taken alone.
    assert "wire q; dut d(clk, hold, a, q);" in SAME_LINE
    cfg = {"points": [{"expression": "a && q && cnt != 0"}]}
    for harness in (SAME_LINE, SAME_LINE.replace("dut d(clk", "dut\n  d (\n clk"),
                    SAME_LINE.replace("dut d(clk", "dut d [0:0] (clk"),
                    SAME_LINE.replace("dut d(clk, hold, a, q)", "dut d(.*)"),
                    SAME_LINE.replace("dut d(clk, hold, a, q)", "dut d(.reset(rst), .clk(clk), .a(a), .q(q)), e(clk, hold, a, q)")):
        p = _plan(tmp_path, cfg, harness)
        assert _safe(p), (harness, p)
    p = _plan(tmp_path, cfg, SAME_LINE)
    assert p["resets"] == [{"expression": "hold", "active_low": False}] and "!(hold)" in p["expression"]
    # A DUT port not named like a reset is found by the register it resets; a parameter the DUT
    # does not have is refused.
    assert _plan(tmp_path, cfg, SAME_LINE.replace("dut d(clk, hold, a, q)", "dut d(.clk(clk), .clr(hold), .a(a), .q(q))"),
                 dut=CLR_DUT)["resets"] == [{"expression": "hold", "active_low": False}]
    assert "could not elaborate" in _plan(tmp_path, cfg, SAME_LINE.replace("dut d(clk", "dut #(.W(1)) d(clk"))["error"]
    # Commented-out or quoted code is not an instance.
    named = SAME_LINE.replace("dut d(clk, hold, a, q);", "dut d(.clk(clk), .reset(hold), .a(a), .q(q)); // dut x(clk, rst, a, q);")
    assert _plan(tmp_path, cfg, named)["resets"] == [{"expression": "hold", "active_low": False}]


@needs_sby
def test_same_line_positional_instance_excludes_nothing(tmp_path):
    cfg, db = _setup(tmp_path, SAME_LINE, "a && q && cnt != 0")
    r = prove(cfg, db, tmp_path / "w", timeout=60)
    assert r["sanity"]["resets"] == [{"expression": "hold", "active_low": False}]
    assert not r["sanity"]["passed"] and not r["points"][0]["unreachable"] and "vacuous" in r["points"][0]["refused"]


# Round-5 finding (/tmp/review5-b/proof-escaped): an escaped instance name (`dut \d (...)`) ended the
# identifier scan, so the positional instance was skipped and a decoy instance's `.reset(rst)` was
# taken as the design's reset. The DUT was held in reset forever and the point was "excluded".
ESCAPED = SAME_LINE.replace("dut d(clk, hold, a, q);",
                            "dut \\d (clk, hold, a, q);\n wire dummy; dut decoy(.clk(clk), .reset(rst), .a(a), .q(dummy));")


@needs_yosys
def test_escaped_and_unreadable_instances_refuse(tmp_path):
    cfg = {"points": [{"expression": "a && q && cnt != 0"}]}
    p = _plan(tmp_path, cfg, ESCAPED)
    assert {"expression": "hold", "active_low": False} in p["resets"] and _safe(p), p
    # Escaped names, ports and expressions are names like any other.
    ok = SAME_LINE.replace("dut d(clk, hold, a, q);", "\\dut  \\d (.\\reset (\\hold ), .clk(clk), .a(a), .q(q));")
    assert _plan(tmp_path, cfg, ok)["resets"] == [{"expression": "hold", "active_low": False}]
    # Whatever Yosys cannot elaborate refuses; what it elaborates is read from the netlist.
    for bad in ("dut #5 d(clk, hold, a, q);", "dut d(.reset(rst), .q(q)) e;", "dut #(.W(1) d(.reset(rst));",
                "`DUT(d)", "`include \"dut_inst.svh\"",
                "dut d(.reset(rst), .q(q)); /* dut e(clk, hold, a, q);",
                'dut d(.reset(rst), .q(q)); initial $display("x);\n dut e(clk, hold, a, q);',
                "dut d(.reset(rst), .q(q)); \\ dut e(clk, hold, a, q);"):
        p = _plan(tmp_path, cfg, SAME_LINE.replace("dut d(clk, hold, a, q);", bad))
        assert _safe(p), (bad, p)
    # This Yosys drops `bind` statements, so the solver's model has no `e` either: the netlist is
    # what gets proved, and it has only `d`.
    bound = _plan(tmp_path, cfg, SAME_LINE.replace("dut d(clk, hold, a, q);",
                  "dut d(.reset(rst), .q(q));\nendmodule\nbind h dut e(clk, hold, a, q);\nmodule unused;"))
    assert [i["instance"] for i in bound["instances"]] == ["d"]
    # Round 7 (/tmp/review7/proof-ifdef-fake-top): an inactive `ifdef` holds no instance. The guard
    # read `dut d(.reset(rst))` from it; Yosys sees no instance, so nothing is inferred.
    off = SAME_LINE.replace("dut d(clk, hold, a, q);", "`ifdef X\n dut d(.reset(rst), .q(q));\n`endif\n"
                            " always @(posedge clk) assert property (a |-> ##1 q);")
    assert "no reset found" in _plan(tmp_path, cfg, off)["error"]
    # A harness wrapper is walked through: its own held reset is not a harness-top name (refused),
    # a reset port it passes on is traced to the top.
    wrap = ("module wrap(input clk, input reset, input a, output q);\n reg hold = 1;\n"
            " always @(posedge clk) hold <= hold;\n dut d(.clk(clk), .reset(hold), .a(a), .q(q));\nendmodule\n"
            + SAME_LINE.replace("dut d(clk, hold, a, q);", "wrap w(.clk(clk), .reset(rst), .a(a), .q(q));"))
    assert "dut w.d port reset is not wired to a named harness-top signal" in _plan(tmp_path, cfg, wrap)["error"]
    p = _plan(tmp_path, cfg, wrap.replace(".reset(hold)", ".reset(!reset)"))
    assert p["resets"] == [{"expression": "!(rst)", "active_low": False}], p
    # An undriven held reset is folded to a constant: the sanity cover then cannot release it.
    p = _plan(tmp_path, cfg, wrap.replace(" always @(posedge clk) hold <= hold;\n", ""))
    assert p["resets"] == [{"expression": "1'b1", "active_low": False}] and "!(1'b1)" in p["expression"], p
    # A harness module without instances counts as a design instance: it needs a reset too.
    leaf = "module mon(input clk, input a); endmodule\n" + SAME_LINE.replace(
        "dut d(clk, hold, a, q);", "dut d(clk, hold, a, q); mon m(clk, a);")
    assert "mon m has no reset" in _plan(tmp_path, cfg, leaf)["error"]


# Round 6 (/tmp/review6/proof-escaped-slash): `dut \d// (clk, hold, a, q);` hid the positional
# instance from the text guard. Round 7 (/tmp/review7/proof-*-fake-top): a fake top module in a
# `define body or an inactive `ifdef gave the text guard a decoy `.reset(rst)`.
ESCAPED_SLASH = ESCAPED.replace("\\d ", "\\d// ")
ESCAPED_BLOCK = ESCAPED.replace("\\d ", "\\d/* ")
MACRO_FAKE_TOP = "`define UNUSED module h; dut decoy(.reset(rst)); endmodule\n" + SAME_LINE
IFDEF_FAKE_TOP = "`ifdef UNDEFINED_REVIEW7\nmodule h; dut decoy(.reset(rst)); endmodule\n`endif\n" + SAME_LINE


@needs_yosys
def test_escaped_names_and_fake_tops_read_the_real_instance(tmp_path):
    cfg = {"points": [{"expression": "a && q && cnt != 0"}]}
    for harness in (ESCAPED_SLASH, ESCAPED_BLOCK, MACRO_FAKE_TOP, IFDEF_FAKE_TOP):
        p = _plan(tmp_path, cfg, harness)
        assert {"expression": "hold", "active_low": False} in p["resets"], (harness, p)
    quiet = SAME_LINE.replace("dut d(clk, hold, a, q);",
                              "dut d(.clk(clk), .reset(rst /* \\x // */), .a(a), .q(q)); // \\e dut e(clk, hold, a, q);\n"
                              " initial $display(\"dut f(clk, hold, a, q); // \\\" /*\");")
    assert _plan(tmp_path, cfg, quiet)["resets"] == [{"expression": "rst", "active_low": False}]
    # Harness inputs come from the netlist's top ports, escaped or not.
    work = tmp_path / "inputs"
    net = elaborate(work, [], "module h(input clk, input \\a /* x */, input b, output o); endmodule", "h")
    assert harness_inputs(net, "h") == ["a", "b", "clk"]


@pytest.mark.parametrize("harness", [MACRO_FAKE_TOP, IFDEF_FAKE_TOP], ids=["define", "ifdef"])
@needs_sby
def test_fake_top_module_excludes_nothing(tmp_path, harness):
    """The reviewer's solver runs: before the fix the decoy's `rst` was taken, the sanity cover passed
    on the harness counter and the DUT, held in reset by `hold`, was 'excluded'."""
    cfg, db = _setup(tmp_path, harness, "a && q && cnt != 0")
    r = prove(cfg, db, tmp_path / "w", timeout=60)
    assert {"expression": "hold", "active_low": False} in r["sanity"]["resets"]
    assert r["points"][0]["jobs"]["prove"]["status"] == "PASS"  # the vacuous proof the guard must refuse
    assert not r["sanity"]["passed"] and not r["points"][0]["unreachable"] and "vacuous" in r["points"][0]["refused"]
    assert "exclusion" not in apply_exclusions(json.loads(db.read_text()), tmp_path / "w" / "exclusions.json")["points"][0]


@needs_sby
def test_escaped_slash_instance_excludes_nothing(tmp_path):
    """The reviewer's solver run: before the fix the DUT, held in reset by `\\d//`, was 'excluded'."""
    cfg, db = _setup(tmp_path, ESCAPED_SLASH, "a && q && cnt != 0")
    r = prove(cfg, db, tmp_path / "w", timeout=60)
    assert {"expression": "hold", "active_low": False} in r["sanity"]["resets"] and not r["sanity"]["passed"]
    assert r["points"][0]["jobs"]["prove"]["status"] == "PASS"  # the vacuous proof the guard must refuse
    assert not r["points"][0]["unreachable"] and "vacuous" in r["points"][0]["refused"]
    assert "exclusion" not in apply_exclusions(json.loads(db.read_text()), tmp_path / "w" / "exclusions.json")["points"][0]


@needs_sby
def test_escaped_instance_name_excludes_nothing(tmp_path):
    cfg, db = _setup(tmp_path, ESCAPED, "a && q && cnt != 0")
    r = prove(cfg, db, tmp_path / "w", timeout=60)
    assert {"expression": "hold", "active_low": False} in r["sanity"]["resets"] and not r["sanity"]["passed"]
    assert not r["points"][0]["unreachable"] and "vacuous" in r["points"][0]["refused"]


# Round 8 (/tmp/review8/include-proof2): a header read through `include was not hashed, so after it
# changed (the point became reachable) the old exclusion was still accepted.
INCLUDE_HARNESS = SAME_LINE.replace("reg hold = 1;", "reg hold = 1; always @(posedge clk) hold <= 0;").replace(
    "always @(posedge clk) hold <= hold;", "").replace("wire q;", "wire [1:0] q;")
# Since round 14 every bit the point reads must change under the harness: `q` counts with a wrap to 1 at 2 with
# ENABLE 0 (0, 1, 2, 1, ...: q == 3 unreachable, both bits move) and modulo 4 with ENABLE 1 (reachable).
INCLUDE_POINT = "a && q == 2'd3"


def _include_dut(header):
    return f'`include "{header}"\n' + DUT.replace("output reg q = 0", "output reg [1:0] q = 0").replace(
        "else if (a) q <= 1;", "else q <= q + ((q == 2'd2 && !`ENABLE) ? 2'd3 : 2'd1);")  # no constant mux: not a reset


@needs_sby
def test_included_header_is_a_proof_input(tmp_path):
    header = tmp_path / "defs.svh"
    header.write_text("`define ENABLE 0\n")
    cfg, db = _setup(tmp_path, INCLUDE_HARNESS, INCLUDE_POINT, dut=_include_dut(header))
    r = prove(cfg, db, tmp_path / "before", timeout=60)
    assert r["schema"] == "rvw.coverage-exclusions/7" and r["points"][0]["unreachable"], r
    record = r["dependencies"][str(header)]
    assert record["sha256"] == hashlib.sha256(b"`define ENABLE 0\n").hexdigest() and len(r["dependencies"]) == 1
    assert record["opened"] == str(header) and record["resolved"] == str(header.resolve())
    assert apply_exclusions(json.loads(db.read_text()), tmp_path / "before" / "exclusions.json")["points"][0]["exclusion"]
    header.write_text("`define ENABLE 1\n")  # now reachable: the old exclusion must not apply
    with pytest.raises(ValueError, match="stale proof input: .*defs.svh"):
        apply_exclusions(json.loads(db.read_text()), tmp_path / "before" / "exclusions.json")
    # A file without the dependency record (schema /1) is refused.
    old = json.loads((tmp_path / "before" / "exclusions.json").read_text())
    header.write_text("`define ENABLE 0\n")
    for edit in ({"schema": "rvw.coverage-exclusions/1"}, {"schema": "rvw.coverage-exclusions/2"},
                 {"schema": "rvw.coverage-exclusions/3"}, {"schema": "rvw.coverage-exclusions/4"},
                 {"schema": "rvw.coverage-exclusions/5"}, {"schema": "rvw.coverage-exclusions/6"}, {"dependencies": None},
                 {"files": None}):
        (tmp_path / "old.json").write_text(json.dumps({**old, **edit}))
        with pytest.raises(ValueError, match="rerun rvw cov prove"):
            apply_exclusions(json.loads(db.read_text()), tmp_path / "old.json")


@needs_yosys
def test_unresolved_file_dependencies_refuse(tmp_path):
    cfg = {"points": [{"expression": "a && q && cnt != 0"}]}
    nested = tmp_path / "nested.svh"
    nested.write_text("`define ENABLE 1\n")
    outer = tmp_path / "outer.svh"
    outer.write_text(f'`include "{nested}"\n')
    p = _plan(tmp_path, cfg, INCLUDE_HARNESS, dut=_include_dut(outer))
    assert p["expression"] and set(p["dependencies"]) == {str(outer), str(nested)}, p
    # Relative to a directory the solver does not run in, or read during elaboration: refused.
    (tmp_path / "rel.svh").write_text("`define ENABLE 1\n")
    for dut in (_include_dut("../../../rel.svh"),
                DUT.replace("output reg q = 0);", "output reg q = 0);\n reg [1:0] m [0:1];\n"
                            ' initial $readmemh("/dev/null", m);')):
        p = _plan(tmp_path, cfg, INCLUDE_HARNESS, dut=dut)
        assert p["expression"] is None and "unresolved file dependencies" in p["error"], p
    # Without the preprocessor's file list nothing is known about includes: refused.
    from rvw.cov.proof import dependencies
    (tmp_path / "empty.txt").write_text("module x; endmodule\n")
    assert dependencies(tmp_path, [tmp_path / "empty.txt"], [tmp_path / "x.v"])[1]
    # Including another listed source by its plain name is what the solver reads too: allowed.
    p = _plan(tmp_path, cfg, '`include "dut.v"\n' + INCLUDE_HARNESS.replace("module h", "module h"), dut=DUT)
    assert "unresolved" not in (p.get("error") or ""), p


# Round 8 (/tmp/review8/polarity-proof): a parameter made the port `reset` active low; the guard took
# it as active high from its name, so a DUT held in reset by `hold = 0` passed the sanity cover.
PARAM_DUT = DUT.replace("module dut(", "module dut #(parameter RESET_ACTIVE_LOW=0)(").replace(
    "if (reset)", "if (RESET_ACTIVE_LOW ? !reset : reset)")
PARAM_LOW = SAME_LINE.replace("reg hold = 1;", "reg hold = 0;").replace(
    "dut d(clk, hold, a, q);", "dut #(.RESET_ACTIVE_LOW(1)) d(clk, hold, a, q);")


@needs_yosys
def test_reset_polarity_is_read_from_the_registers(tmp_path):
    cfg = {"points": [{"expression": "a && q && cnt != 0"}]}
    p = _plan(tmp_path, cfg, PARAM_LOW, dut=PARAM_DUT)
    assert p["resets"] == [{"expression": "hold", "active_low": True}] and "(hold)" in p["expression"], p
    assert _plan(tmp_path, cfg, SAME_LINE, dut=PARAM_DUT)["resets"] == [{"expression": "hold", "active_low": False}]
    # A name that says active low, a register that says active high: the register wins.
    named = DUT.replace("input reset", "input rst_n").replace("if (reset)", "if (rst_n)")
    assert _plan(tmp_path, cfg, SAME_LINE, dut=named)["resets"] == [{"expression": "hold", "active_low": False}]
    # Asynchronous, through a submodule, and inverted on the way.
    sub = ("module leaf(input clk, input r, input a, output reg q);\n"
           " always @(posedge clk or negedge r) if (!r) q <= 0; else q <= a;\nendmodule\n"
           "module dut(input clk, input reset, input a, output q);\n leaf l(clk, !reset, a, q);\nendmodule\n")
    assert _plan(tmp_path, cfg, SAME_LINE, dut=sub)["resets"] == [{"expression": "hold", "active_low": False}]
    # A port that resets no register, or registers at both levels: refused, whatever its name.
    unused = DUT.replace("if (reset) q <= 0; else if (a) q <= 1;", "if (a) q <= 1;")
    both = DUT.replace("output reg q = 0);", "output reg q = 0); reg z = 0;\n always @(posedge clk) z <= reset ? 0 : a;")
    both = both.replace("if (reset) q <= 0;", "if (!reset) q <= 0;")
    for dut, why in ((unused, "resets no register"), (both, "both levels")):
        p = _plan(tmp_path, cfg, SAME_LINE, dut=dut)
        assert p["expression"] is None and why in p["error"], p
    # A port not named like a reset that resets registers is a reset too.
    p = _plan(tmp_path, cfg, SAME_LINE.replace("dut d(clk, hold, a, q)", "dut d(.clk(clk), .clr(hold), .a(a), .q(q))"),
              dut=CLR_DUT)
    assert p["resets"] == [{"expression": "hold", "active_low": False}], p
    # A stated reset must state its polarity.
    p = _plan(tmp_path, {**cfg, "reset": "hold"}, SAME_LINE)
    assert p["expression"] is None and "reset_active_low" in p["error"], p


@needs_sby
def test_parameter_active_low_reset_excludes_nothing(tmp_path):
    cfg, db = _setup(tmp_path, PARAM_LOW, "a && q && cnt != 0", dut=PARAM_DUT)
    r = prove(cfg, db, tmp_path / "w", timeout=60)
    assert r["sanity"]["resets"] == [{"expression": "hold", "active_low": True}]
    assert r["points"][0]["jobs"]["prove"]["status"] == "PASS"  # the vacuous proof the guard must refuse
    assert not r["sanity"]["passed"] and not r["points"][0]["unreachable"] and "vacuous" in r["points"][0]["refused"]


# Round 9 (/tmp/review9/combined-reset): `if (reset || warm) q <= 0` gave a reset path through logic.
# The guard read only plain or inverted resets, found `reset` (also a plain reset of `r`), and the
# harness that held `warm` forever passed the sanity cover: a reachable point was excluded.
COMBINED_DUT = """module dut(input clk, input reset, input warm, input a, output reg q = 0, output reg r = 0);
 always @(posedge clk) if (reset) r <= 0; else r <= !r;
 always @(posedge clk) if (reset || warm) q <= 0; else if (a) q <= 1;
endmodule
"""
COMBINED_HARNESS = """module h(input clk, input a);
 reg rst = 1; always @(posedge clk) rst <= 0;
 reg warm = 1; always @(posedge clk) warm <= warm;
 wire q, r;
 dut d(clk, rst, warm, a, q, r);
 always @(posedge clk) begin
 // RVW_POINT
 end
endmodule
"""


@needs_sby
def test_reset_through_logic_excludes_nothing(tmp_path):
    cfg, db = _setup(tmp_path, COMBINED_HARNESS, "a && q && r", dut=COMBINED_DUT)
    r = prove(cfg, db, tmp_path / "w", timeout=60)
    point = r["points"][0]
    assert point["jobs"]["prove"]["status"] == "PASS"  # the vacuous proof: `warm` is held forever
    assert not r["sanity"]["passed"] and not point["unreachable"], r["sanity"]
    assert "warm" in r["sanity"]["error"] and "plain or inverted" in r["sanity"]["error"], r["sanity"]
    (tmp_path / "excl.json").write_text(json.dumps(r))
    assert "exclusion" not in apply_exclusions(json.loads(db.read_text()), tmp_path / "excl.json")["points"][0]
    # Stated by the user as the whole reset: the sanity cover shows `warm` is never released.
    sub = tmp_path / "stated"
    sub.mkdir()
    cfg, db = _setup(sub, COMBINED_HARNESS, "a && q && r", dut=COMBINED_DUT,
                     extra={"reset": "rst || warm", "reset_active_low": False})
    r = prove(cfg, db, sub / "w", timeout=60)
    assert r["sanity"]["status"] == "FAIL" and not r["points"][0]["unreachable"]


@needs_yosys
def test_every_reset_path_is_collected(tmp_path):
    cfg = {"points": [{"expression": "a && q && cnt != 0"}]}
    combined = COMBINED_DUT.replace("output reg r = 0);", "output reg r = 0);\n wire hold_q = reset || warm;")
    harness = COMBINED_HARNESS.replace("dut d(clk, rst, warm, a, q, r);", "dut d(clk, rst, warm, a, q, r); reg [3:0] cnt = 0;"
                                       " always @(posedge clk) cnt <= cnt + 1;")
    cases = {
        "sync": COMBINED_DUT,
        "async": COMBINED_DUT.replace("always @(posedge clk) if (reset || warm)",
                                      "wire ar = reset | warm;\n always @(posedge clk or posedge ar) if (ar)"),
        "set/clear": COMBINED_DUT.replace("always @(posedge clk) if (reset || warm) q <= 0; else if (a) q <= 1;",
                                          "wire s = warm & a;\n always @(posedge clk or posedge reset or posedge s)"
                                          " if (reset) q <= 0; else if (s) q <= 1; else q <= a;"),
        "async load": COMBINED_DUT.replace("always @(posedge clk) if (reset || warm) q <= 0; else if (a) q <= 1;",
                                           "wire l = reset ^ warm;\n always @(posedge clk or posedge l)"
                                           " if (l) q <= a; else q <= !q;"),
        "submodule": "module leaf(input clk, input z, input a, output reg q = 0);\n"
                     " always @(posedge clk) if (z) q <= 0; else if (a) q <= 1;\nendmodule\n"
                     + combined.replace("always @(posedge clk) if (reset || warm) q <= 0; else if (a) q <= 1;",
                                        "wire qq; leaf l(clk, hold_q, a, qq); always @(posedge clk) q <= qq;"),
        "gate cell": COMBINED_DUT.replace("always @(posedge clk) if (reset || warm) q <= 0; else if (a) q <= 1;",
                                          "wire qn; \\$_SDFF_PP0_ g(.C(clk), .R(warm), .D(a), .Q(qn));"
                                          " always @(posedge clk) if (reset) q <= 0; else q <= qn;"),
    }
    for label, dut in cases.items():
        p = _plan(tmp_path, cfg, harness, dut=dut)
        assert p["expression"] is None and "no reset found" in p["error"], (label, p)
        assert ("could not elaborate" if label == "gate cell" else "plain or inverted") in p["error"], (label, p)
    # A state cell whose resets are not known (here a cell type Yosys may add later): refused.
    from rvw.cov.proof import reset_paths
    port = {"direction": "input", "bits": [2]}
    body = {"ports": {"clk": port, "warm": {"direction": "input", "bits": [3]}},
            "cells": {"f": {"type": "$future_ff", "parameters": {}, "port_directions": {"D": "input", "Q": "output"},
                            "connections": {"D": [3], "Q": [4]}}}}
    assert "not modelled" in reset_paths({"m": body}, "m")[1][0]
    # A clear that reads only the design's own state (a counter wrapping to 0) is no harness reset.
    wrap = COMBINED_DUT.replace("always @(posedge clk) if (reset || warm) q <= 0; else if (a) q <= 1;",
                                "reg [1:0] s = 0; always @(posedge clk) s <= (s == 2) ? 0 : s + 1;\n"
                                " always @(posedge clk) if (reset) q <= 0; else if (a && s == 1) q <= 1;")
    p = _plan(tmp_path, cfg, harness, dut=wrap)
    assert p["expression"] and p["resets"] == [{"expression": "rst", "active_low": False}], p
    # Two plain resets at their own polarity: both are resets the sanity cover releases.
    two = COMBINED_DUT.replace("if (reset || warm) q <= 0;", "if (!warm) q <= 0;")
    p = _plan(tmp_path, cfg, harness, dut=two)
    assert p["resets"] == [{"expression": "rst", "active_low": False}, {"expression": "warm", "active_low": True}], p


# Round 9 (/tmp/review9/symlink-include): an include through a symbolic link was hashed by its target,
# so after the link was pointed at another header (the point became reachable) the old exclusion
# was still accepted.
@needs_sby
def test_retargeted_include_link_is_stale(tmp_path):
    disabled, enabled = tmp_path / "disabled.svh", tmp_path / "enabled.svh"
    disabled.write_text("`define ENABLE 0\n")
    enabled.write_text("`define ENABLE 1\n")
    link = tmp_path / "defs.svh"
    link.symlink_to(disabled)
    cfg, db = _setup(tmp_path, INCLUDE_HARNESS, INCLUDE_POINT, dut=_include_dut(link))
    r = prove(cfg, db, tmp_path / "before", timeout=60)
    assert r["points"][0]["unreachable"], r
    assert apply_exclusions(json.loads(db.read_text()), tmp_path / "before" / "exclusions.json")["points"][0]["exclusion"]
    link.unlink()
    link.symlink_to(enabled)
    with pytest.raises(ValueError, match="stale proof input: .*defs.svh"):
        apply_exclusions(json.loads(db.read_text()), tmp_path / "before" / "exclusions.json")
    record = r["dependencies"][str(link)]
    assert record["links"] == [[str(link), str(disabled)]] and record["resolved"] == str(disabled.resolve()), record
    after = prove(cfg, db, tmp_path / "after", timeout=60)  # and the point is in fact reachable now
    assert after["points"][0]["jobs"]["cover"]["status"] == "PASS" and not after["points"][0]["unreachable"]


@needs_sby
def test_retargeted_directory_or_source_link_is_stale(tmp_path):
    for d, value in (("a", 0), ("b", 1)):
        (tmp_path / d).mkdir()
        (tmp_path / d / "defs.svh").write_text(f"`define ENABLE {value}\n")
    (tmp_path / "inc").symlink_to(tmp_path / "a")
    cfg, db = _setup(tmp_path, INCLUDE_HARNESS, INCLUDE_POINT, dut=_include_dut(tmp_path / "inc" / "defs.svh"))
    # The source itself through a link too: dut.v -> real/dut.v.
    (tmp_path / "real").mkdir()
    (tmp_path / "dut.v").rename(tmp_path / "real" / "dut.v")
    (tmp_path / "dut.v").symlink_to(tmp_path / "real" / "dut.v")
    r = prove(cfg, db, tmp_path / "w", timeout=60)
    assert r["points"][0]["unreachable"], r
    assert r["files"][str(tmp_path / "dut.v")]["links"][-1] == [str(tmp_path / "dut.v"), str(tmp_path / "real" / "dut.v")]
    excl = tmp_path / "w" / "exclusions.json"
    assert apply_exclusions(json.loads(db.read_text()), excl)["points"][0]["exclusion"]
    (tmp_path / "inc").unlink()
    (tmp_path / "inc").symlink_to(tmp_path / "b")
    with pytest.raises(ValueError, match="stale proof input: .*inc/defs.svh .symbolic links changed"):
        apply_exclusions(json.loads(db.read_text()), excl)
    (tmp_path / "inc").unlink()
    (tmp_path / "inc").symlink_to(tmp_path / "a")
    assert apply_exclusions(json.loads(db.read_text()), excl)["points"][0]["exclusion"]
    # Same bytes behind another link target: still stale (the lookup is part of the evidence).
    shutil.copyfile(tmp_path / "real" / "dut.v", tmp_path / "copy.v")
    (tmp_path / "dut.v").unlink()
    (tmp_path / "dut.v").symlink_to(tmp_path / "copy.v")
    with pytest.raises(ValueError, match="stale proof input: .*dut.v"):
        apply_exclusions(json.loads(db.read_text()), excl)


def test_file_records_keep_lookup_links(tmp_path):
    from rvw.cov.proof import file_record

    def resolve_links(path):
        item = file_record(path)
        return item["links"], item["resolved"]
    root = tmp_path.resolve()
    (root / "d").mkdir()
    (root / "d" / "f").write_text("x")
    (root / "rel").symlink_to("d")                 # relative target
    (root / "up").symlink_to("d/../d/f")           # `..` after a link-free directory
    (root / "loop").symlink_to("loop")
    assert resolve_links(root / "rel" / "f") == ([[str(root / "rel"), "d"]], str(root / "d" / "f"))
    assert resolve_links(root / "up") == ([[str(root / "up"), "d/../d/f"]], str(root / "d" / "f"))
    (root / "d" / "back").symlink_to(root / "rel")  # absolute target that is itself a link
    chain, end = resolve_links(root / "d" / "back" / "f")
    assert chain == [[str(root / "d" / "back"), str(root / "rel")], [str(root / "rel"), "d"]] and end == str(root / "d" / "f")
    with pytest.raises(ValueError, match="symlink cycle|too many symbolic links"):
        resolve_links(root / "loop")


# Round 13 (/tmp/review13-a/proof-dynamic-input.py): `if (hold) q <= seed` is no reset in `dut` alone,
# so the guard (which read resets per module, after `opt_dff`) did not see it. The harness ties
# `seed` to 0 and holds `hold` (`warm`) by an assumption: once bound, `hold` resets `q` forever, the
# sanity cover was reached through `r`, and the reachable point `a && q && r` was excluded.
HOLD_DUT = """module dut(input clk, input reset, input hold, input seed, input a, output reg q = 0, output reg r = 0);
 always @(posedge clk) begin
  if (reset) r <= 0; else r <= !r;
  if (hold) q <= seed; else if (a) q <= 1;
 end
endmodule
"""
HOLD_HARNESS = """module h(input clk, input a, input warm);
 always @* assume(warm == HELD);
 reg rst = 1; always @(posedge clk) rst <= 0;
 wire q, r;
 dut d(clk, rst, warm, 1'b0, a, q, r);
 always @(posedge clk) begin
 // RVW_POINT
 end
endmodule
"""


@needs_sby
@pytest.mark.parametrize("mode", ["held", "tied", "released"])
def test_reset_formed_by_a_harness_tie_is_found(tmp_path, mode):
    harness = HOLD_HARNESS.replace("HELD", "1'b0" if mode == "released" else "1'b1")
    if mode == "tied":  # the same hold as a constant: `q` is no register at all once bound
        harness = harness.replace("dut d(clk, rst, warm,", "dut d(clk, rst, 1'b1,")
    cfg, db = _setup(tmp_path, harness, "a && q && r", dut=HOLD_DUT)
    r = prove(cfg, db, tmp_path / "w", timeout=60)
    point, sanity = r["points"][0], r["sanity"]
    excluded = apply_exclusions(json.loads(db.read_text()), tmp_path / "w" / "exclusions.json")["points"][0]
    assert "exclusion" not in excluded and not point["unreachable"], (sanity, point)
    if mode == "held":
        assert point["jobs"]["prove"]["status"] == "PASS"  # the vacuous proof the guard must refuse
        assert {"expression": "warm", "active_low": False} in sanity["resets"], sanity
        assert sanity["status"] == "FAIL" and "vacuous" in point["refused"], sanity
    elif mode == "tied":
        assert point["jobs"]["prove"]["status"] == "PASS"
        assert sanity["pinned"] and "pins design state" in point["refused"], sanity
    else:  # released: the guard still lets the harness run, and the point is reachable
        assert sanity["passed"] and not sanity["pinned"], sanity
        assert point["jobs"]["cover"]["status"] == "PASS" and point["jobs"]["prove"]["status"] == "FAIL"


@needs_yosys
def test_bound_resets_and_pinned_state(tmp_path):
    cfg = {"points": [{"expression": "a && q && r"}]}
    harness = HOLD_HARNESS.replace("HELD", "1'b0")
    p = _plan(tmp_path, cfg, harness, dut=HOLD_DUT)
    assert p["resets"] == [{"expression": "rst", "active_low": False}, {"expression": "warm", "active_low": False}], p
    assert [b["expression"] for b in p["bound"]["resets"]] == ["rst", "warm"] and not p["pinned"], p
    # Inverted on the way, through the harness: active low.
    p = _plan(tmp_path, cfg, harness.replace("dut d(clk, rst, warm,", "dut d(clk, rst, !warm,"), dut=HOLD_DUT)
    assert {"expression": "warm", "active_low": True} in [{k: v for k, v in b.items() if k != "registers"}
                                                           for b in p["bound"]["resets"]], p
    # Through harness logic that reads an input: no harness net to release, refused.
    p = _plan(tmp_path, cfg, harness.replace("module h(input clk, input a, input warm);",
                                             "module h(input clk, input a, input warm, input w2);")
              .replace("dut d(clk, rst, warm,", "dut d(clk, rst, warm & w2,"), dut=HOLD_DUT)
    assert p["expression"] is None and "once the harness is bound" in p["error"], p
    # A tie that removes a register: pinned, whatever the reset ports say.
    p = _plan(tmp_path, cfg, harness.replace("dut d(clk, rst, warm,", "dut d(clk, rst, 1'b1,"), dut=HOLD_DUT)
    assert p["pinned"] and "1 register bit(s)" in p["pinned"][0], p
    # A design constant (a register that never changes in the module itself) is not pinned by the harness.
    p = _plan(tmp_path, cfg, harness, dut=HOLD_DUT.replace("output reg r = 0);", "output reg r = 0); reg k = 0;\n"
                                                           " always @(posedge clk) k <= k;"))
    assert not p["pinned"], p


# Round 14 (/tmp/review14-a/proof-assumed-seed.py): the hold is an assumption on a harness input
# (`assume(seed == 0)` with `if (hold) q <= seed`), so no reset cell shows it, and `r` toggling passed
# the global sanity cover: the point `a && q && r`, reachable once the hold is released, was excluded.
# Since then each excluded point's own cone (every bit it reads) must change under the harness.
SEED_DUT = HOLD_DUT.replace("output reg r = 0);", "output reg r = 0, output reg c = 0,\n"
                            "  output [1:0] w, output o);\n reg [5:4] v = 0; reg b = 0;\n"
                            " assign w = {b, v[4]}; assign o = seed & a;\n").replace(
    "  if (hold) q <= seed;", "  c <= q; b <= !b; v[4] <= seed;\n  if (hold) q <= seed;")
SEED_HARNESS = """module h(input clk, input a, input warm, input seed);
 always @* begin assume(warm == HELD); assume(seed == 0); end
 reg rst = 1; always @(posedge clk) rst <= 0;
 wire q, r, c, o; wire [1:0] w;
 dut d(clk, rst, warm, seed, a, q, r, c, w, o);
 always @(posedge clk) begin
 // RVW_POINT
 end
endmodule
"""


def _prove_seed(tmp_path, name, expression, held, harness=SEED_HARNESS, dut=SEED_DUT):
    sub = tmp_path / name
    sub.mkdir()
    cfg, db = _setup(sub, harness.replace("HELD", "1'b1" if held else "1'b0"), expression, dut=dut)
    r = prove(cfg, db, sub / "w", timeout=60)
    applied = apply_exclusions(json.loads(db.read_text()), sub / "w" / "exclusions.json")["points"][0]
    return r["sanity"], r["points"][0], "exclusion" in applied


@needs_sby
def test_hold_by_assumption_refuses_and_released_control_still_excludes(tmp_path):
    sanity, point, applied = _prove_seed(tmp_path, "held", "a && q && r", held=True)
    assert sanity["passed"] and point["jobs"]["prove"]["status"] == "PASS", (sanity, point)  # the vacuous proof
    assert not point["unreachable"] and not applied and "never changes" in point["refused"], point
    assert point["cone"]["status"] == "FAIL" and "d.q" in point["cone"]["signals"], point["cone"]
    # The same harness with the hold released: `c && !q` is unreachable by design (q only rises, c
    # follows it a cycle later) and every bit it reads changes, so it is still excluded.
    sanity, point, applied = _prove_seed(tmp_path, "released", "c && !q", held=False)
    assert point["unreachable"] and applied, point
    assert point["cone"]["passed"] and sorted(point["cone"]["signals"]) == ["d.c", "d.q"], point["cone"]
    # Held, the same point is unreachable only because q and c never move: refused.
    sanity, point, applied = _prove_seed(tmp_path, "held-c", "c && !q", held=True)
    assert point["jobs"]["prove"]["status"] == "PASS" and not point["unreachable"] and not applied, point


@needs_sby
def test_cone_bits_held_by_assumption_or_tie_refuse(tmp_path):
    # A harness input held by an assumption, read directly.
    sanity, point, applied = _prove_seed(tmp_path, "input", "seed && r", held=False)
    assert point["jobs"]["prove"]["status"] == "PASS" and not point["unreachable"] and not applied, point
    assert "seed" in point["cone"]["signals"] and point["cone"]["status"] == "FAIL", point["cone"]
    # One bit of a wider register held (w[0] is v[4] <= seed, bit position 0 of `reg [5:4] v`), the
    # other toggling: per bit, refused.
    sanity, point, applied = _prove_seed(tmp_path, "bit", "w == 2'd3", held=False)
    assert point["jobs"]["prove"]["status"] == "PASS" and not point["unreachable"] and not applied, point
    assert sorted(point["cone"]["signals"]) == ["d.b", "d.v[0]"] and point["cone"]["status"] == "FAIL", point["cone"]
    # A harness tie in the point's combinational cone (`o = seed & a` with `.seed(1'b0)`): refused
    # (here `pinned_state` sees the tie first, as it also makes v[4] constant; `test_point_cone`
    # shows the cone refusing it alone).
    sanity, point, applied = _prove_seed(tmp_path, "tie", "o && r", held=False, harness=TIED_SEED)
    assert point["jobs"]["prove"]["status"] == "PASS" and not point["unreachable"] and not applied, point
    # A toggling harness register named `\d.q ` takes the flattened name of the held `d.q`: without
    # the clash check the cone cover bound it and the held point was excluded.
    decoy = SEED_HARNESS.replace("wire q, r, c, o;", "wire q, r, c, o; reg \\d.q  = 0;\n"
                                 " always @(posedge clk) \\d.q  <= !\\d.q ;")
    sanity, point, applied = _prove_seed(tmp_path, "decoy", "a && q && r", held=True, harness=decoy)
    assert point["jobs"]["prove"]["status"] == "PASS" and not point["unreachable"] and not applied, point
    assert "ambiguous" in point["refused"], point


TIED_SEED = SEED_HARNESS.replace("dut d(clk, rst, warm, seed,", "dut d(clk, rst, warm, 1'b0,")


@needs_yosys
def test_point_cone(tmp_path):
    def cone(expression, harness=SEED_HARNESS.replace("HELD", "1'b0"), dut=SEED_DUT):
        work = tmp_path / f"c{len(list(tmp_path.glob('c*')))}"
        work.mkdir()
        (work / "dut.v").write_text(dut)
        return point_cone(elaborate(work / "out", [work / "dut.v"], harness, "h"), "h", expression)
    signals, problems = cone("a && q && r")
    assert sorted(signals) == ["a", "d.q", "d.r"] and not problems, (signals, problems)
    assert sorted(cone("o")[0]) == ["a", "seed"] and not cone("o")[1]
    # A constant tie made inside the design's own module is the design's, not the harness's.
    gate = "module orgate(input x, input y, output o); assign o = x | y; endmodule\n"
    signals, problems = cone("o", dut=gate + SEED_DUT.replace("assign o = seed & a;", "orgate g(1'b0, a, o);"))
    assert signals == ["a"] and not problems, problems
    signals, problems = cone("o && r", harness=TIED_SEED.replace("HELD", "1'b0"))
    assert any("ties input seed of instance d to the constant 0" in p for p in problems), problems
    assert "not a net of the harness top" in cone("d.q")[1][0]
    assert "nothing shows" in cone("1'b0 && 1'b1")[1][0]
    held = SEED_HARNESS.replace("HELD", "1'b0").replace("wire q, r, c, o;", "wire q, r, c, o; wire z = 1'b0;")
    assert "holds at a constant" in cone("z && q", harness=held)[1][0]
    # A harness net with the flattened name of a design net (`\d.q `) would take that name after
    # `flatten` and be bound instead: refused.
    decoy = SEED_HARNESS.replace("HELD", "1'b0").replace("wire q, r, c, o;", "wire q, r, c, o; reg \\d.q  = 0;\n"
                                                         " always @(posedge clk) \\d.q  <= !\\d.q ;")
    assert any("flattened name is ambiguous" in p for p in cone("a && q", harness=decoy)[1]), cone("q", harness=decoy)
    clash = SEED_HARNESS.replace("HELD", "1'b0").replace("wire q, r, c, o;", "wire q, r, c, o, rvw_cone_0;")
    assert any("rvw_cone_" in p for p in cone("q", harness=clash)[1])


# Round 15 (/tmp/review15-proof/path-probe.py): a source basename with a newline and `!cmd` was
# written into the guard's Yosys script and ran before the path check.
@pytest.mark.parametrize("name", ["empty.v\n!touch PWNED", "a b.v", "-p.v", "x;y.v", "q\"x.v", "!touch PWNED"])
def test_unsafe_source_names_refuse_before_any_tool(tmp_path, monkeypatch, name):
    monkeypatch.setattr("rvw.cov.proof.run_job", lambda *a, **k: pytest.fail("tool ran before path validation"))
    monkeypatch.setattr("rvw.cov.proof.Toolchain", lambda *a: pytest.fail("tool ran before path validation"))
    dut, harness = TINY.split("module h")
    cfg, db = _setup(tmp_path, "module h" + harness, "s == 2'd3", dut=dut, extra={"reset": None})
    (tmp_path / name).write_text("// empty\n")
    c = json.loads(cfg.read_text())
    c["sources"] = [name, "dut.v"]
    cfg.write_text(json.dumps(c))
    with pytest.raises(ValueError, match="source"):
        prove(cfg, db, tmp_path / "w", timeout=10)
    assert not (tmp_path / "w").exists() and not list(tmp_path.rglob("PWNED"))


def test_unsafe_work_dir_refuses_before_any_tool(tmp_path):
    dut, harness = TINY.split("module h")
    cfg, db = _setup(tmp_path, "module h" + harness, "s == 2'd3", dut=dut, extra={"reset": None})
    with pytest.raises(ValueError, match="work"):
        prove(cfg, db, tmp_path / "w\n!touch PWNED", timeout=10)
    assert not list(tmp_path.rglob("PWNED")) and len(list(tmp_path.iterdir())) == 4


def test_script_writers_validate_before_writing(tmp_path, monkeypatch):
    from rvw.cov.proof import _run, _sby
    monkeypatch.setattr("rvw.cov.proof.run_job", lambda *a, **k: pytest.fail("tool ran"))
    source = tmp_path / "x.v\n!touch PWNED"
    source.write_text("// empty")
    with pytest.raises(ValueError, match="source"):
        elaborate(tmp_path / "guard", [source], "", "h")
    with pytest.raises(ValueError, match="top"):
        elaborate(tmp_path / "guard", [], "", "h\n!touch PWNED")
    with pytest.raises(ValueError, match="cone"):
        _sby(tmp_path, "job", "cover", 8, 10, [], "h", ["x\n!touch PWNED"])
    with pytest.raises(ValueError, match="source"):
        _run(tmp_path, "job", "cover", "", "", [source], {"top": "h"}, 10)
    assert list(tmp_path.iterdir()) == [source]


# Round 15 (/tmp/review15-proof/clock-probe.py): SBY runs with `multiclock off`, so every clock steps
# together. Two independent clocks made `q != r` "unreachable" (sanity and cone covers passed).
TWO_CLOCK_DUT = """module dut(input clk, input other_clk, output reg q = 0, output reg r = 0);
  always @(posedge clk) q <= !q;
  always @(posedge other_clk) r <= !r;
endmodule
"""
TWO_CLOCK_HARNESS = """module h(input clk, input other_clk);
  wire q, r;
  dut d(clk, other_clk, q, r);
  always @(posedge clk) begin
    // RVW_POINT
  end
endmodule
"""


@needs_sby
def test_two_independent_clocks_exclude_nothing(tmp_path):
    cfg, db = _setup(tmp_path, TWO_CLOCK_HARNESS, "q != r", dut=TWO_CLOCK_DUT, extra={"reset": None})
    r = prove(cfg, db, tmp_path / "w", timeout=60)
    point = r["points"][0]
    assert not r["sanity"]["passed"] and not point["unreachable"], point
    assert "clock" in r["sanity"]["error"] and "other_clk" in r["sanity"]["error"], r["sanity"]["error"]
    assert "exclusion" not in apply_exclusions(json.loads(db.read_text()), tmp_path / "w" / "exclusions.json")["points"][0]


@needs_yosys
def test_clock_guard(tmp_path):
    def plan(harness, dut=TINY.split("module h")[0], **extra):
        return _plan(tmp_path, {"points": [{"expression": "s == 2'd3"}], "reset": None, **extra}, harness, dut=dut)
    one = "module h" + TINY.split("module h")[1]
    ok = plan(one)
    assert ok["expression"] and ok["clock"] == {"clock": "clk", "problems": []}, ok
    assert plan(one, clock="clk")["expression"]
    assert plan(one.replace('clk', 'tick'), dut=TINY.split('module h')[0].replace('clk', 'tick'),
                clock='tick')['expression']
    assert 'clock' in plan(one.replace('.clk(clk)', ".clk(1'b0)"))['error']
    # The marker under the falling edge: the point's own check is on another edge.
    assert "falling edge" in plan(one.replace("always @(posedge clk) begin", "always @(negedge clk) begin"))["error"]
    # A clock derived inside the design (a divider) is not the harness clock.
    divided = ("module tiny(input clk, input a, output reg [1:0] s = 0); reg half = 0;\n"
               "  always @(posedge clk) half <= !half;\n"
               "  always @(posedge half) s <= (s == 2) ? 0 : s + 1;\nendmodule\n")
    assert "clock" in plan(one, dut=divided)["error"]
    # A stated clock that is not the one the design uses.
    assert "clock" in plan(one.replace("module h(input clk, input a)", "module h(input clk, input a, input b)"),
                           clock="b")["error"]
    # A `$global_clock` register beside a clocked one.
    glob = one.replace("  always @(posedge clk) begin", "  reg g = 0; always @($global_clock) g <= !g;\n"
                       "  always @(posedge clk) begin")
    assert "global clock" in plan(glob)["error"]
    # No clock record (a netlist from before the guard): refused, not taken as one clock.
    netlist = elaborate(tmp_path / "noclock", [], one.replace("tiny t(", "// ").replace("wire [1:0] s;", "reg [1:0] s = 0; always @(posedge clk) s <= s + 1;"), "h")
    netlist.pop("clock")
    assert "clock" in sanity_plan({"top": "h", "reset": None, "points": [{"expression": "s == 2'd3"}]}, netlist)["error"]



# Round 15 (/tmp/review15-proof/tamper-probe.py): changing only a row's `point_id` moved a valid
# exclusion onto another (reachable) point; nothing hashed bound the row to the plan.
@needs_sby
def test_exclusion_rows_are_bound_to_the_plan(tmp_path):
    dut, harness = TINY.split("module h")
    cfg, db = _setup(tmp_path, "module h" + harness, "s == 2'd3", dut=dut, extra={"reset": None})
    data = json.loads(db.read_text())
    data["points"].append({**data["points"][0], "id": "p2", "key": "k2"})
    db.write_text(json.dumps(data))
    config = json.loads(cfg.read_text())
    config['points'].append({'point_id': 'p2', 'expression': "s == 2'd2", 'reason': 'reachable control'})
    cfg.write_text(json.dumps(config))
    r = prove(cfg, db, tmp_path / "w", timeout=60)
    assert r["points"][0]["unreachable"], r["points"][0]
    assert not r["points"][1]["unreachable"]
    good = tmp_path / "w" / "exclusions.json"
    assert apply_exclusions(data, good)["points"][0]["exclusion"]

    def rejected(edit):
        obj = json.loads(good.read_text())
        edit(obj)
        bad = tmp_path / "edited.json"
        bad.write_text(json.dumps(obj))
        with pytest.raises(ValueError, match="plan|proof evidence"):
            apply_exclusions(data, bad)

    rejected(lambda o: o["points"][0].update(point_id="p2"))
    rejected(lambda o: o["points"][0].update(expression="s == 2'd2"))
    rejected(lambda o: o["points"][0]["cone"].update(signals=["t.s[0]"]))
    rejected(lambda o: o.update(config=str(tmp_path / "db.json")))
    rejected(lambda o: o["sanity"].update(expression="1'b1"))

    def swap(o):  # another job's (passing) status for this point's proof
        job, cone = o["points"][0]["jobs"]["prove"], o["points"][0]["cone"]
        job.update(directory=cone["directory"], status_sha256=cone["status_sha256"])
    rejected(swap)

    def copy_job(o):  # the cone job's files under the prove job's name
        o["points"][0]["jobs"]["prove"].update({k: o["points"][0]["cone"][k] for k in
                                                ("directory", "status_sha256", "sby", "sby_sha256", "harness",
                                                 "harness_sha256")})
    rejected(copy_job)
    rejected(lambda o: o['points'][1]['jobs'].update(prove=o['points'][0]['jobs']['prove']))
    rejected(lambda o: o['inputs'].pop(o['config']))
    rejected(lambda o: o.update(files={}))
    from rvw.cov.proof import file_record
    source = str(tmp_path / 'dut.v')
    rejected(lambda o: o.update(dependencies={source: file_record(source)}))
    rejected(lambda o: o['points'][0].update(reason='unreviewed reason'))
    rejected(lambda o: o['points'][0].update(assumptions='different assumptions'))
    rejected(lambda o: o['sanity']['clock'].update(problems=['other clock']))

    # Updating the row's self-reported hashes cannot make another property or SBY script valid.
    from rvw.common.capture import sha256_file
    for field, suffix in [('harness', ' // changed property'), ('sby', '\n# changed job')]:
        obj = json.loads(good.read_text())
        job = obj['points'][0]['jobs']['prove']
        path = Path(job[field])
        original = path.read_text()
        path.write_text(original + suffix)
        job[field + '_sha256'] = sha256_file(path)
        bad = tmp_path / 'edited.json'
        bad.write_text(json.dumps(obj))
        with pytest.raises(ValueError, match='plan|proof evidence'):
            apply_exclusions(data, bad)
        path.write_text(original)

    obj = json.loads(good.read_text())
    snapshot = Path(obj['elaboration']['path'])
    original = snapshot.read_text()
    snapshot.write_text('{}')
    with pytest.raises(ValueError, match='plan|proof evidence'):
        apply_exclusions(data, good)
    snapshot.write_text(original)
    assert apply_exclusions(data, good)['points'][0]['exclusion']


def test_duplicate_plan_points_refuse_before_tools(tmp_path, monkeypatch):
    cfg, db = _setup(tmp_path, GOOD, 'q')
    config = json.loads(cfg.read_text())
    config['points'] *= 2
    cfg.write_text(json.dumps(config))
    monkeypatch.setattr('rvw.cov.proof.run_job', lambda *a, **k: pytest.fail('tool ran'))
    with pytest.raises(ValueError, match='duplicate point ids'):
        prove(cfg, db, tmp_path / 'w')


@needs_sby
def test_guard_harness_paths_remain_unique_when_sources_use_default_names(tmp_path):
    dut, harness = TINY.split('module h')
    cfg, db = _setup(tmp_path, 'module h' + harness, "s == 2'd3", dut=dut, extra={'reset': None})
    (tmp_path / 'dut.v').rename(tmp_path / 'guard.sv')
    names = ['guard.sv', '_guard.sv', 'clock-guard.sv', '_clock-guard.sv']
    for name in names[1:]:
        (tmp_path / name).write_text('// Listed source reserves this basename.\n')
    config = json.loads(cfg.read_text())
    config['sources'] = names
    cfg.write_text(json.dumps(config))
    data = json.loads(db.read_text())
    data['sources']['dut.v']['path'] = str(tmp_path / 'guard.sv')
    db.write_text(json.dumps(data))
    result = prove(cfg, db, tmp_path / 'proof')
    netlist = json.loads(Path(result['elaboration']['path']).read_text())['netlist']
    assert Path(netlist['harness']).name == '__guard.sv'
    assert Path(netlist['clock_harness']).name == '__clock-guard.sv'
    assert result['points'][0]['unreachable']
    assert apply_exclusions(data, tmp_path / 'proof/exclusions.json')['points'][0]['exclusion']
