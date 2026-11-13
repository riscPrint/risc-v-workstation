"""VHDL simulation synthesis must not depend on the Yosys plugin ABI."""
import os
import subprocess
import pytest
from rvw.init.hdl import scaffold_hdl

pytestmark = pytest.mark.fast


def test_vhdl_build_uses_standalone_ghdl_and_preserves_paths(tmp_path):
    source = tmp_path / 'core source.vhd'
    source.write_text('entity top is end; architecture rtl of top is begin end;')
    scaffold_hdl(tmp_path, hdl='vhdl', top='top', isa='rv32i', sources=[source.name])
    tools = tmp_path / 'bin'
    tools.mkdir()
    ghdl = tools / 'ghdl'
    ghdl.write_text('#!/usr/bin/env python3\nimport sys\n'
                    'assert sys.argv[1:] == ["--synth", "--std=08", "--work=work", '
                    '"--out=verilog", "core source.vhd", "-e", "top"]\n'
                    'print("module top; endmodule")\n')
    verilator = tools / 'verilator'
    verilator.write_text('#!/usr/bin/env python3\nfrom pathlib import Path\n'
                         'assert Path("rvw/out/top.v").read_text().strip() == "module top; endmodule"\n')
    for tool in (ghdl, verilator):
        tool.chmod(0o755)
    env = {**os.environ, 'PATH': str(tools) + os.pathsep + os.environ['PATH']}
    result = subprocess.run(['bash', 'rvw/run.sh', 'build'], cwd=tmp_path,
                            env=env, capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert '"status":"built"' in result.stdout
    assert 'yosys' not in (tmp_path / 'rvw/run.sh').read_text()
