"""Build the HDL scaffold before any query creates its output directory."""
import json
import os
from pathlib import Path
import subprocess
import pytest
from rvw.init.hdl import scaffold_hdl

pytestmark = pytest.mark.fast


def test_build_creates_output_and_uses_absolute_harness(tmp_path):
    (tmp_path / "top.v").write_text("module top; endmodule\n")
    scaffold_hdl(tmp_path, hdl="sv", top="top", isa="rv32i")
    tools = tmp_path / "bin"
    tools.mkdir()
    verilator = tools / "verilator"
    verilator.write_text("""#!/usr/bin/env python3
import pathlib, sys
args = sys.argv[1:]
out = pathlib.Path(args[args.index('-Mdir') + 1])
assert out.is_dir()
harness = pathlib.Path(args[args.index('-o') - 1])
assert harness.is_absolute() and harness.is_file()
""")
    verilator.chmod(0o755)
    result = subprocess.run([str(tmp_path / "rvw/run.sh"), "build"],
                            env={**os.environ, "PATH": str(tools) + os.pathsep + os.environ["PATH"]},
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "built"
