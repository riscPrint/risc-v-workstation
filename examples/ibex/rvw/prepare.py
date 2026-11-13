"""Resolve upstream FuseSoC files into an external Verilator manifest."""
import json, os, subprocess, sys
from pathlib import Path
import yaml
PIN = "38c070939183cc10940b66c8e9e04eeca6b65470"
project = Path(__file__).resolve().parent.parent
source = Path(os.environ["IBEX_SOURCE"]).resolve()
work = Path(os.environ["IBEX_WORK"]).resolve()
if source.is_relative_to(project) or work.is_relative_to(project):
    raise SystemExit("IBEX_SOURCE and IBEX_WORK must be outside the project")
if subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip() != PIN:
    raise SystemExit("wrong Ibex revision")
work.mkdir(parents=True, exist_ok=True)
subprocess.run(["fusesoc", "--cores-root", str(source), "run", "--setup", "--build-root", str(work / "files"), "--target=lint", "lowrisc:ibex:ibex_top"], check=True)
edam = next((work / "files").rglob("*.eda.yml"))
data = yaml.safe_load(edam.read_text())
files = [str((edam.parent / f["name"]).resolve()) for f in data["files"] if f.get("file_type") == "systemVerilogSource" and not f.get("is_include_file")]
incs = sorted({str((edam.parent / Path(f["name"]).parent).resolve()) for f in data["files"] if f.get("is_include_file")})
spec = dict(top="ibex_top", sources=files, include_dirs=incs, defines=["RVFI", "SYNTHESIS"],
            verilator_flags=["-O1", "-Wno-fatal", "-GRV32M=1", "--coverage", "-j", "2"],
            harness_sources=[str(project / "rvw/harness.cpp")],
            harness_inputs=[str(project / "rvw/devices.h")], build_dir=str(work / "obj"))
(work / "hdl.json").write_text(json.dumps(spec, indent=2))
print(work / "hdl.json")
