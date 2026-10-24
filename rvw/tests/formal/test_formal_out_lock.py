"""Round 12 (formal): a run owns its --out directory. A second run on the same directory (another
process, or a nested call in the same process) must stop before it removes or writes anything, so it
can never substitute its wrapper, script or solver directory into the first run's proof."""
import fcntl
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from rvw.cli import main
from rvw.formal import common, flows

TOOLS = all(shutil.which(t) for t in ("yosys", "sby"))
needs_tools = pytest.mark.skipif(not TOOLS, reason="needs yosys and sby (source spinal-boom/env.sh)")

# Fails when a is tied to 1, passes when a is tied to 0.
DUT = "module dut(input clk, input a);\n  always @(posedge clk) assert(!a);\nendmodule\n"
# Too hard for a few seconds of BMC: keeps the solver busy.
HARD = """\
module h(input clk, input reset, input [47:0] a, input [47:0] b, output reg [95:0] p);
  always @(posedge clk) p <= a * b;
  always @(posedge clk) if (!reset) assert(!(p == 96'd4611685975477714963 && a > 1 && b > 1));
endmodule
"""


def _rc(argv):
    try:
        return main(argv)
    except SystemExit as e:
        return e.code


def _bmc(rtl, out, value):
    return ["formal", "bmc", "--verilog", str(rtl), "--top", "dut", "--tie", f"a={value}", "--depth", "4",
            "--out", str(out), "--json"]


def _result(out):
    return json.loads((Path(out) / "result.json").read_text())


@needs_tools
def test_nested_run_on_the_same_out_cannot_substitute_the_wrapper(tmp_path, monkeypatch, capsys):
    """The reviewer's probe (probe_formal_race.py): run B on the same --out is scheduled after run A wrote
    its wrapper (a=1, fails) and before A starts its solver. Before the fix B (a=0) replaced the wrapper
    and A reported pass. Now B stops with an input error and A proves its own wrapper."""
    rtl = tmp_path / "dut.sv"
    rtl.write_text(DUT)
    out = tmp_path / "shared"
    original = flows._sby
    nested = []

    def interleave(o, name, text):
        monkeypatch.setattr(flows, "_sby", original)
        nested.append(_rc(_bmc(rtl, o, 0)))
        return original(o, name, text)
    monkeypatch.setattr(flows, "_sby", interleave)
    rc = _rc(_bmc(rtl, out, 1))
    assert nested == [2]
    assert "another rvw formal run is using --out" in capsys.readouterr().err
    r = _result(out)
    assert rc == 1 and r["status"] == "fail" and r["ties"] == {"a": 1}
    assert "1'd1" in (out / "rvw_formal_top.sv").read_text()


def test_held_lock_refuses_the_run_and_keeps_its_files(tmp_path, capsys):
    """While another run holds the directory, a new run removes nothing (not even result.json)."""
    rtl = tmp_path / "dut.sv"
    rtl.write_text(DUT)
    out = tmp_path / "o"
    out.mkdir()
    (out / "result.json").write_text('{"status": "fail"}\n')
    (out / "rvw_formal_top.sv").write_text("// the other run's wrapper\n")
    fd = os.open(out / common.LOCK_NAME, os.O_RDWR | os.O_CREAT)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert _rc(_bmc(rtl, out, 0)) == 2
    finally:
        os.close(fd)
    assert "another rvw formal run is using --out" in capsys.readouterr().err
    assert (out / "result.json").read_text() == '{"status": "fail"}\n'
    assert (out / "rvw_formal_top.sv").read_text() == "// the other run's wrapper\n"


def test_lock_is_released_after_an_input_error(tmp_path):
    """A run that stops after taking the lock (here: too shallow a depth) releases it."""
    rtl = tmp_path / "dut.sv"
    rtl.write_text("module dut(input clk, input reset, input a);\n  always @(posedge clk) assert(!a);\nendmodule\n")
    out = tmp_path / "o"
    argv = ["formal", "bmc", "--verilog", str(rtl), "--top", "dut", "--depth", "1", "--out", str(out)]
    assert _rc(argv) == 2
    fd = os.open(out / common.LOCK_NAME, os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)   # raises if the run still held it
    finally:
        os.close(fd)


@needs_tools
def test_sequential_runs_on_the_same_out(tmp_path):
    rtl = tmp_path / "dut.sv"
    rtl.write_text(DUT)
    out = tmp_path / "o"
    assert _rc(_bmc(rtl, out, 1)) == 1 and _result(out)["status"] == "fail"
    assert _rc(_bmc(rtl, out, 0)) == 0 and _result(out)["status"] == "pass"


@needs_tools
def test_concurrent_process_on_the_same_out_is_refused(tmp_path):
    """Two real processes: while the first one's solver runs, the second exits 2 and the first one's
    result is its own."""
    hard = tmp_path / "h.v"
    hard.write_text(HARD)
    out = tmp_path / "o"
    first = subprocess.Popen([sys.executable, "-m", "rvw", "formal", "bmc", "--verilog", str(hard), "--top", "h",
                              "--depth", "30", "--timeout", "6", "--out", str(out)],
                             start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        end = time.time() + 60
        while time.time() < end and not (out / "sby").is_dir():
            time.sleep(0.1)
        assert (out / "sby").is_dir(), "the first run never started its solver"
        rtl = tmp_path / "dut.sv"
        rtl.write_text(DUT)
        second = subprocess.run([sys.executable, "-m", "rvw", *_bmc(rtl, out, 0)], capture_output=True, text=True,
                                timeout=60)
        assert second.returncode == 2, second.stderr
        assert "another rvw formal run is using --out" in second.stderr
        assert first.wait(timeout=60) == 1
    finally:
        if first.poll() is None:
            os.killpg(first.pid, 9)
    r = _result(out)
    assert r["top"] == "h" and r["status"] == "timeout" and r["ties"] == {}


def test_invalid_out_preserves_existing_result(tmp_path):
    out = tmp_path / 'invalid output'
    out.mkdir()
    result = out / 'result.json'
    result.write_text('existing evidence\n')
    rtl = tmp_path / 'top.sv'
    rtl.write_text('module top(input clk); endmodule\n')
    with pytest.raises(SystemExit):
        main(['formal', 'bmc', '--verilog', str(rtl), '--top', 'top', '--out', str(out)])
    assert result.read_text() == 'existing evidence\n'
    assert list(out.iterdir()) == [result]
