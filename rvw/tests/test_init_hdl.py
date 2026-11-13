"""`rvw init --hdl`: non-Spinal core projects whose query build and Verilator build work."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from rvw.cli import main
from rvw.init.hdl import scaffold_hdl

YOSYS, VERILATOR = shutil.which('yosys'), shutil.which('verilator')
RVW = str(Path(sys.executable).parent / 'rvw')
DATA = Path(__file__).parent / 'data/chisel'
SV = '''`include "defs.svh"
package p; typedef logic [7:0] byte_t; endpackage
module leaf import p::*; (input logic clk_i, input byte_t d_i, output byte_t q_o);
  always_ff @(posedge clk_i) q_o <= `NEXT(d_i);
endmodule
module top (input logic clk_i, input p::byte_t a_i, output p::byte_t y_o);
  leaf u (.clk_i, .d_i(a_i), .q_o(y_o));
endmodule
'''


def _sv(tmp_path):
    (tmp_path / 'rtl').mkdir()
    (tmp_path / 'rtl/top.sv').write_text(SV)
    (tmp_path / 'inc').mkdir()
    (tmp_path / 'inc/defs.svh').write_text("`define NEXT(x) ((x) + 1'b1)\n")
    (tmp_path / 'tb').mkdir()
    (tmp_path / 'tb/tb_top.sv').write_text('module tb_top; endmodule\n')
    return tmp_path


def _query_build(root, monkeypatch, capfd):
    monkeypatch.setenv('RVW', RVW)
    monkeypatch.chdir(root)
    assert main(['query', 'build', '--config', 'default', '--json']) == 0
    info = json.loads(capfd.readouterr().out)
    assert 'error' not in info
    return info


def test_scaffold_files(tmp_path, capfd):
    root = _sv(tmp_path)
    assert main(['init', str(root), '--hdl', 'sv', '--top', 'top', '--isa', 'rv32i', '-I', 'inc',
                 '--dry-run', '--json']) == 0
    r = json.loads(capfd.readouterr().out)
    assert r['frontend'] == 'slang' and r['sources'] == ['rtl/top.sv'] and r['candidate_tops'] == ['leaf', 'top']
    assert set(r['files']) == {'rvw.toml', 'rvw/run.sh', 'rvw/build-db.sh', 'rvw/sim/harness.cpp',
                               'rvw/.gitignore', 'rvw/README.md'}
    assert 'build = ["./rvw/build-db.sh"]' in r['files']['rvw.toml']
    assert '--frontend slang' in r['files']['rvw/build-db.sh'] and '-I inc' in r['files']['rvw/build-db.sh']
    assert not (root / 'rvw.toml').exists()
    with pytest.raises(ValueError, match='not declared'):
        scaffold_hdl(root, hdl='sv', top='nosuch', isa='rv32i')
    with pytest.raises(ValueError, match='--fir'):
        scaffold_hdl(root, hdl='chisel', top='Top', isa='rv32i')
    scaffold_hdl(root, hdl='sv', top='top', isa='rv32i')
    with pytest.raises(ValueError, match='Refusing to overwrite'):
        scaffold_hdl(root, hdl='sv', top='top', isa='rv32i')
    out = subprocess.run([str(root / 'rvw/run.sh'), 'info', '--json'], capture_output=True, text=True)
    assert json.loads(out.stdout)['isa'] == {'default': 'rv32i'}
    refused = subprocess.run([str(root / 'rvw/run.sh'), 'run', '--elf', 'x', '--out', 'y'], capture_output=True)
    assert refused.returncode == 2


@pytest.mark.skipif(not YOSYS, reason='native Yosys required')
def test_sv_project_query_and_build(tmp_path, monkeypatch, capfd):
    from test_query_slang import _has_slang
    if not _has_slang():
        pytest.skip('yosys-slang plugin required')
    root = _sv(tmp_path)
    scaffold_hdl(root, hdl='sv', top='top', isa='rv32i', include_dirs=['inc'])
    info = _query_build(root, monkeypatch, capfd)
    assert info['meta']['frontend'] == 'yosys-slang' and info['counts']['components'] == 2
    assert main(['query', 'where', 'u.q_o', '--db', 'rvw/out/design.db', '--json']) == 0
    assert json.loads(capfd.readouterr().out)['signal']['loc'].endswith('rtl/top.sv:3')
    if VERILATOR:
        built = subprocess.run(['nice', '-n', '10', str(root / 'rvw/run.sh'), 'build'], capture_output=True,
                               text=True, timeout=300)
        assert built.returncode == 0, built.stderr[-2000:]
        assert json.loads(built.stdout)['status'] == 'built'
        assert subprocess.run([str(root / 'rvw/out/obj_dir/sim')]).returncode == 2  # harness not mapped


@pytest.mark.skipif(not YOSYS, reason='native Yosys required')
def test_chisel_project_query(tmp_path, monkeypatch, capfd):
    from test_query_chisel import FIRTOOL
    if not FIRTOOL:
        pytest.skip('firtool required')
    monkeypatch.setenv('RVW_FIRTOOL', FIRTOOL)
    (tmp_path / 'src/main/scala').mkdir(parents=True)
    shutil.copy(DATA / 'Gen.scala', tmp_path / 'src/main/scala/Gen.scala')
    (tmp_path / 'out').mkdir()
    shutil.copy(DATA / 'Top.fir', tmp_path / 'out/Top.fir')
    r = scaffold_hdl(tmp_path, hdl='chisel', top='Top', isa='rv32i', fir='out/Top.fir')
    assert '--source-root src/main/scala' in r['files']['rvw/build-db.sh']
    info = _query_build(tmp_path, monkeypatch, capfd)
    assert info['meta']['frontend'] == 'yosys-firtool'
    assert main(['query', 'where', 'io.a.valid', '--db', 'rvw/out/design.db', '--json']) == 0
    assert json.loads(capfd.readouterr().out)['signal']['loc'].endswith('src/main/scala/Gen.scala:21')


@pytest.mark.skipif(not (YOSYS and shutil.which('ghdl')), reason='native Yosys and GHDL required')
def test_vhdl_project_query(tmp_path, monkeypatch, capfd):
    from test_query_ghdl import PKG, TOP, _has_plugin
    if not _has_plugin():
        pytest.skip('GHDL Yosys plugin required')
    (tmp_path / 'hdl').mkdir()
    (tmp_path / 'hdl/top.vhd').write_text(TOP)
    (tmp_path / 'hdl/defs.vhd').write_text(PKG)
    r = scaffold_hdl(tmp_path, hdl='vhdl', top='top', isa='rv32i')
    assert r['sources'] == ['hdl/defs.vhd', 'hdl/top.vhd']  # the package goes first
    info = _query_build(tmp_path, monkeypatch, capfd)
    assert info['meta']['frontend'] == 'yosys-ghdl' and info['counts']['components'] == 3
