"""Every formal probe and proof must consume the same copied inputs."""
import hashlib
import json
import re
import shutil
from types import SimpleNamespace

import pytest

from rvw.cli import main
from rvw.formal import common, snapshot as snapshot_module

TRACE = '''$timescale 1ns $end
$scope module top $end
$var wire 1 ! clk $end
$var wire 1 " q $end
$upscope $end
$enddefinitions $end
#0
0!
1"
#5
1!
#10
0!
'''

needs_tools = pytest.mark.skipif(
    not all(shutil.which(t) for t in ("yosys", "sby", "yices-smt2")),
    reason="needs yosys, sby and yices-smt2",
)


@needs_tools
@pytest.mark.parametrize("flow", ["bmc", "xprop"])
@pytest.mark.parametrize("included", [False, True])
def test_live_width_edit_cannot_change_the_proven_design(tmp_path, monkeypatch, flow, included):
    # Round-18 reproductions: the old wrapper ties the new high input bit to zero.
    rtl = tmp_path / "top.sv"
    declaration = "input d"
    if included:
        changing = tmp_path / "port.vh"
        changing.write_text(declaration)
        declaration = '`include "port.vh"\n'
    else:
        changing = rtl
    tail = ("always @(posedge clk) assert(d<2);" if flow == "bmc"
            else "reg q; assign y=(d>=2)?q:0;")
    rtl.write_text(f"module top(input clk,\n{declaration}"
                   + (",output y" if flow == "xprop" else "") + f"); {tail} endmodule\n")
    old = changing.read_bytes()
    new = old.replace(b"input d", b"input [1:0] d")
    run = common.run
    edited = False

    def race(cmd, *args, **kwargs):
        nonlocal edited
        if ("clock_probe.ys" if flow == "bmc" else "probe.ys") in cmd:
            changing.write_bytes(new)
            edited = True
        return run(cmd, *args, **kwargs)

    monkeypatch.setattr(common, "run", race)
    out = tmp_path / "race"
    argv = ["formal", flow, "--verilog", str(rtl), "--top", "top", "--depth", "6",
            "--timeout", "30", "--out", str(out)]
    if flow == "xprop":
        argv += ["--outputs"]
    assert main(argv) == 0
    assert edited
    result = json.loads((out / "result.json").read_text())
    snapshot = result["input_snapshot"]
    assert not snapshot["problems"]
    record = next(r for r in snapshot["files"] if r["original"] == str(changing))
    assert record["sha256"] == hashlib.sha256(old).hexdigest()
    assert (out / record["path"]).read_bytes() == old
    proof = (out / ("bmc.sby" if flow == "bmc" else "xprop.sby")).read_text()
    assert f"read_rtlil {out / 'module_ports.il'}" in proof
    assert str(rtl) not in proof
    # The edited design really fails when elaborated with the complete new interface.
    monkeypatch.setattr(common, "run", run)
    argv[argv.index(str(out))] = str(tmp_path / "fresh")
    assert main(argv) == 1
    assert json.loads((tmp_path / "fresh" / "result.json").read_text())["status"] == "fail"


@needs_tools
def test_replay_copies_rtl_trace_and_checks_before_the_first_probe(tmp_path, monkeypatch):
    rtl = tmp_path / 'top.sv'
    rtl.write_text('module top(input clk, output reg q); always @(posedge clk) begin '
                   'q<=q; assert(q==0); end endmodule')
    trace = tmp_path / 'trace.vcd'
    trace.write_text(TRACE)
    checks = tmp_path / 'checks.json'
    checks.write_text('{"checks": [], "channels": []}')
    originals = {p: p.read_bytes() for p in (rtl, trace, checks)}
    run = common.run

    def race(cmd, *args, **kwargs):
        if 'module_ports.ys' in cmd:
            rtl.write_text('module top(input clk); always @(posedge clk) assert(1); endmodule')
            trace.write_text(TRACE.replace('1"', '0"'))
            checks.write_text('invalid edited JSON')
        return run(cmd, *args, **kwargs)

    monkeypatch.setattr(common, 'run', race)
    out = tmp_path / 'replay'
    assert main(['formal', 'from-sim', '--verilog', str(rtl), '--top', 'top', '--trace', str(trace),
                 '--checks', str(checks), '--scope', 'top', '--time', '5', '--depth', '4',
                 '--out', str(out)]) == 1
    result = json.loads((out / 'result.json').read_text())
    assert result['status'] == 'fail'
    assert result['state']['ff_bits_from_trace'] == 1
    snapshot = result['input_snapshot']
    assert not snapshot['problems']
    for path, data in originals.items():
        record = next(r for r in snapshot['files'] if r['original'] == str(path))
        assert (out / record['path']).read_bytes() == data
        assert record['sha256'] == hashlib.sha256(data).hexdigest()


@needs_tools
def test_nested_absolute_and_symlink_includes_are_copied(tmp_path):
    width = tmp_path / 'width.vh'
    width.write_text('`define WIDTH 2\n')
    link = tmp_path / 'link.vh'
    link.symlink_to(width)
    header = tmp_path / 'ports.vh'
    header.write_text(f'`include "{link}"\ninput [`WIDTH-1:0] d\n')
    rtl = tmp_path / 'top.sv'
    rtl.write_text('module top(input clk,\n`include "ports.vh"\n); '
                   'always @(posedge clk) assert(d<2); endmodule')
    out = tmp_path / 'out'
    assert main(['formal', 'bmc', '--verilog', str(rtl), '--top', 'top', '--depth', '4',
                 '--out', str(out)]) == 1
    result = json.loads((out / 'result.json').read_text())
    assert result['status'] == 'fail'
    inputs = result['input_snapshot']['files']
    record = next(r for r in inputs if r['original'] == str(link))
    assert record['resolved'] == str(width)
    assert (out / record['path']).read_bytes() == width.read_bytes()
    assert {r['original'] for r in inputs} == {str(p) for p in (rtl, header, link)}


@needs_tools
@pytest.mark.parametrize('text', [
    '`define HEADER "port.vh"\n`include `HEADER\nmodule top(input clk); endmodule',
    'module top(input clk); reg [7:0] mem[0:1]; initial $readmemh("data.hex",mem); endmodule',
])
def test_unknown_file_dependencies_are_refused(tmp_path, text):
    rtl = tmp_path / 'top.sv'
    rtl.write_text(text)
    (tmp_path / 'port.vh').write_text('')
    out = tmp_path / 'out'
    out.mkdir()
    (out / 'result.json').write_text('{"status":"pass"}')
    with pytest.raises(SystemExit) as exc:
        main(['formal', 'bmc', '--verilog', str(rtl), '--top', 'top', '--out', str(out)])
    assert exc.value.code == 2
    assert not (out / 'result.json').exists()


@needs_tools
@pytest.mark.parametrize('decoy', [
    '// $readmemh("data.hex", mem);',
    '/* $fopen("data.hex"); */',
    'initial $display("$readmemh(\\\"data.hex\\\", mem)");',
    '`ifdef UNUSED\ninitial $display("$fopen");\n`endif',
])
def test_file_task_names_in_comments_and_strings_are_allowed(tmp_path, decoy):
    rtl = tmp_path / 'top.sv'
    rtl.write_text('module top(input clk); always @(posedge clk) assert(1); '
                   + decoy + '\nendmodule\n')
    out = tmp_path / 'out'
    assert main(['formal', 'bmc', '--verilog', str(rtl), '--top', 'top',
                 '--depth', '4', '--out', str(out)]) == 0
    assert json.loads((out / 'result.json').read_text())['status'] == 'pass'


@needs_tools
def test_preprocessed_file_task_is_refused(tmp_path, capsys):
    rtl = tmp_path / 'top.sv'
    data = tmp_path / 'data.hex'
    data.write_text('00\n01\n')
    rtl.write_text('`define CAT(a,b) a``b\n'
                   'module top(input clk); reg [7:0] mem[0:1]; '
                   f'initial `CAT($readmem,h)("{data}", mem); endmodule\n')
    assert not snapshot_module._has_file_read(rtl.read_text())
    out = tmp_path / 'out'
    with pytest.raises(SystemExit) as exc:
        main(['formal', 'bmc', '--verilog', str(rtl), '--top', 'top',
              '--depth', '4', '--out', str(out)])
    assert exc.value.code == 2
    assert str(data) in (out / 'module_ports.d').read_text()
    assert 'cannot seal the formal input snapshot' in capsys.readouterr().err
    assert not (out / 'result.json').exists()


@pytest.mark.parametrize('task', [
    '$readmemh', '$readmemb', '$fopen', '$fread', '$fscanf', '$fgets', '$fgetc', '$sreadmem',
])
def test_file_task_scanner_keeps_real_calls_after_decoys(task):
    decoys = f'// {task}\n/* {task} */\n$display("{task} \\"quoted\\"");\n'
    assert not snapshot_module._has_file_read(decoys)
    assert snapshot_module._has_file_read(decoys + f'{task}("file", mem);')


@pytest.mark.parametrize('dependencies', [None, '', 'wrong: source', 'OUTPUTS: ', 'OUTPUTS: /uncaptured'])
def test_frontend_requires_complete_captured_dependencies(tmp_path, dependencies):
    rtl = tmp_path / 'top.sv'
    rtl.write_text('module top(input clk); endmodule')
    out = tmp_path / 'out'
    out.mkdir()
    snapshot = snapshot_module.InputSnapshot(SimpleNamespace(verilog=[rtl], checks=None), out)
    if dependencies is not None:
        outputs = f'{out / "module_ports.json"} {out / "module_ports.il"}'
        (out / 'module_ports.d').write_text(dependencies.replace('OUTPUTS', outputs))
    with pytest.raises(SystemExit) as exc:
        snapshot.check_frontend()
    assert exc.value.code == 2


@needs_tools
def test_frontend_cannot_read_an_include_missed_by_the_scanner(tmp_path, monkeypatch):
    # Simulate an unsupported include spelling: the frontend, not the scanner, is the final guard.
    import rvw.formal.snapshot as module
    monkeypatch.setattr(module, '_TOKENS', re.compile(r'(?!)'))
    header = tmp_path / 'port.vh'
    header.write_text('input d')
    rtl = tmp_path / 'top.sv'
    rtl.write_text(f'module top(input clk,\n`include "{header}"\n); endmodule')
    out = tmp_path / 'out'
    with pytest.raises(SystemExit) as exc:
        main(['formal', 'bmc', '--verilog', str(rtl), '--top', 'top', '--out', str(out)])
    assert exc.value.code == 2
    assert not (out / 'result.json').exists()
