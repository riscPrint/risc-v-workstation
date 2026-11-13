"""Ibex project-owned C1 adapter. The native harness serves both memory ports."""
import argparse, hashlib, json, os, shutil, struct, sys, time, subprocess
from pathlib import Path
from rvw.common.proc import run_group
from rvw.init.hdl_identity import collect
from rvw.cosim.elf import Elf

ISA = "rv32imc_zicsr_zifencei"
PROJECT = Path(__file__).resolve().parent.parent
# Regression selects the source checkout for committed gate runs.
if os.environ.get("IBEX_PROJECT_SOURCE"):
    PROJECT = Path(os.environ["IBEX_PROJECT_SOURCE"]) / "examples/ibex"

def image(elf):
    if elf[:6] != b"\x7fELF\x01\x01":
        raise ValueError("expected little-endian ELF32")
    entry, phoff = struct.unpack_from("<II", elf, 24)
    size, count = struct.unpack_from("<HH", elf, 42)
    ram = bytearray(0x100000)
    for i in range(count):
        typ, off, va, pa, fs, ms, flags, align = struct.unpack_from("<8I", elf, phoff+i*size)
        if typ != 1: continue
        pos = pa - 0x80000000
        if not 0 <= pos <= len(ram)-ms or fs > ms or off+fs > len(elf):
            raise ValueError("ELF segment outside RAM")
        ram[pos:pos+fs] = elf[off:off+fs]
    if entry != 0x80000080: raise ValueError("entry must be 0x80000080 (Ibex boot vector)")
    return ram

def main(captured=None):
    if sys.argv[1:2] == ["info"]:
        print(json.dumps(dict(schema="rvw.adapter/1",core="ibex",configs=["default"],default_config="default",xlen=32,isa={"default":ISA}))); return 0
    if sys.argv[1:2] == ["run-many"]:
        batch=argparse.ArgumentParser()
        batch.add_argument("action"); batch.add_argument("--manifest",required=True); batch.add_argument("--jobs",type=int,default=1)
        b=batch.parse_args()
        captured=collect(Path(os.environ["IBEX_WORK"])/"hdl.json")
        for line in Path(b.manifest).read_text().splitlines():
            job=json.loads(line); args=[]
            for key,value in job.items():
                if value is None or value is False: continue
                flag="--"+key.replace("_","-")
                args += [flag] if value is True else [flag,str(value)]
            sys.argv=[__file__,"run",*args]
            main(captured)
        return 0
    p=argparse.ArgumentParser()
    p.add_argument("action",choices=["build","identity","run"])
    p.add_argument("--options"); p.add_argument("--config",default="default"); p.add_argument("--elf"); p.add_argument("--out")
    p.add_argument("--seed",type=int,default=1); p.add_argument("--max-cycles",type=int,default=200000)
    p.add_argument("--mem-latency",type=int,default=0); p.add_argument("--wall-timeout",type=float,default=120)
    for flag in ["rvfi-trace","rvfi","coverage","json"]: p.add_argument("--"+flag,action="store_true")
    a=p.parse_args()
    if a.config != "default" or a.mem_latency != 0: raise ValueError("only default config and zero added latency are supported")
    work=Path(os.environ["IBEX_WORK"]).resolve()
    doc, command=captured or collect(work/"hdl.json")
    if Path(doc["manifest"]["harness_sources"][0]).resolve() != PROJECT / "rvw/harness.cpp":
        raise ValueError("manifest belongs to another source checkout; rerun prepare.py")
    if a.action == "identity": print(json.dumps(doc)); return 0
    binary=work/"obj/sim"
    saved=work/"obj/identity.json"
    if not binary.exists() or not saved.exists() or json.loads(saved.read_text())["result_claims"] != doc["result_claims"]:
        binary.parent.mkdir(parents=True,exist_ok=True)
        build=run_group(command,capture=True,timeout=120)
        (work/"build.log").write_text((build.stdout or "")+(build.stderr or ""))
        if build.returncode or build.timed_out: raise ValueError("Verilator build failed; see IBEX_WORK/build.log")
        saved.write_text(json.dumps(doc))
    if a.action == "build": print(json.dumps(dict(schema="rvw.build/1",status="built",model=str(binary)))); return 0
    out=Path(a.out).resolve(); out.mkdir(parents=True,exist_ok=True)
    elf=Path(a.elf).resolve(); data=elf.read_bytes()
    (out/"memory.bin").write_bytes(image(data))
    tohost=Elf(elf,data=data).symbols["tohost"]
    start=time.monotonic()
    run=run_group([str(binary),str(out/"memory.bin"),str(tohost),str(a.max_cycles),str(out)],capture=True,timeout=a.wall_timeout)
    (out/"run.log").write_text((run.stdout or "")+(run.stderr or ""))
    if run.timed_out or run.returncode: raise ValueError("native harness failed or exceeded wall time")
    trace=out/"rvfi.jsonl"
    lines=trace.read_text().splitlines()
    header=json.loads(lines[0]); header["elf"]=str(elf)
    lines[0]=json.dumps(header)
    trace.write_text("\n".join(lines)+"\n")
    result=json.loads((out/"native.json").read_text())
    result.update(options={"rvfi_trace":a.rvfi_trace,"max_cycles":a.max_cycles,"mem_latency":a.mem_latency},schema="rvw.run/1",core="ibex",config=a.config,elf=str(elf),elf_sha256=hashlib.sha256(data).hexdigest(),seed=a.seed,max_cycles=a.max_cycles,mem_latency=a.mem_latency,wall_s=time.monotonic()-start,source=doc["source"],tools={"native_build":doc["native_build"]},artifacts={"log":"run.log","rvfi_trace":"rvfi.jsonl","coverage":"coverage.dat"})
    for key,value in doc["result_claims"].items():
        obj=result
        parts=key.split(".")
        for part in parts[:-1]: obj=obj.setdefault(part,{})
        obj[parts[-1]]=value
    target=out/"result.json.part"; target.write_text(json.dumps(result)); target.replace(out/"result.json")
    (out/"memory.bin").unlink()
    print(json.dumps(result)); return 0
if __name__ == "__main__":
    try: sys.exit(main())
    except (ValueError, OSError, StopIteration, KeyError) as exc:
        print(str(exc),file=sys.stderr); sys.exit(2)
