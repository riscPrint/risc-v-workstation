"""Build the HDL scaffold before any query creates its output directory."""
import json
import os
from pathlib import Path
import subprocess
import sys
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
if '-E' in args:
    print('module top; endmodule')
    sys.exit(0)
out = pathlib.Path(args[args.index('-Mdir') + 1])
assert out.is_dir()
harness = pathlib.Path(args[args.index('-o') - 1])
assert harness.is_absolute() and harness.is_file()
""")
    verilator.chmod(0o755)
    result = subprocess.run([str(tmp_path / "rvw/run.sh"), "build"],
                            env={**os.environ, "RVW_PYTHON": sys.executable, "PATH": str(tools) + os.pathsep + os.environ["PATH"]},
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "built"


def test_build_recompiles_when_native_flags_change(tmp_path):
    """Make does not include command-line compiler flags in object dependencies."""
    (tmp_path / 'top.v').write_text('module top; endmodule\n')
    scaffold_hdl(tmp_path, hdl='sv', top='top', isa='rv32i')
    tools=tmp_path/'bin';tools.mkdir()
    verilator=tools/'verilator'
    verilator.write_text('''#!/usr/bin/env python3
import pathlib,sys
args=sys.argv[1:]
if '-E' in args:
    print('module top; endmodule');sys.exit(0)
if '-Mdir' not in args: sys.exit(1)
model=pathlib.Path(args[args.index('-Mdir')+1])/'sim'
# Model GNU make: flags alone do not invalidate an existing output.
if not model.exists() or '-B' in args:
    model.write_text(args[args.index('-CFLAGS')+1])
''')
    verilator.chmod(0o755)
    manifest=tmp_path/'rvw/hdl.json'
    spec=json.loads(manifest.read_text())
    for flag in ('-DVALUE=1','-DVALUE=2'):
        spec['verilator_flags']=['-CFLAGS',flag];manifest.write_text(json.dumps(spec))
        result=subprocess.run([str(tmp_path/'rvw/run.sh'),'build'],
             env={**os.environ,'RVW_PYTHON':sys.executable,'PATH':str(tools)+os.pathsep+os.environ['PATH']},
             capture_output=True,text=True)
        assert result.returncode==0,result.stderr
        assert (tmp_path/'rvw/out/obj_dir/sim').read_text()==flag
