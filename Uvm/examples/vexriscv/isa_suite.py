"""Run every built RV32UI/RV32UM machine-mode ELF in one pyuvm build."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from rvw.sim.cocotb import run


def programs(directory):
    directory=Path(directory)
    return sorted(p for pattern in ('rv32ui-p-*','rv32um-p-*') for p in directory.glob(pattern)
        if p.is_file() and p.read_bytes()[:4]==b'\x7fELF')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--programs',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--rtl',type=Path,required=True)
    p.add_argument('--shim',type=Path,required=True)
    p.add_argument('--timeout',type=float,default=1800)
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    selected=programs(a.programs.resolve())
    if not selected: raise ValueError('no built RV32UI/RV32UM ELF programs')
    here=Path(__file__).resolve().parent
    manifest=json.loads((here/'bench.json').read_text())
    manifest['sources']=[str(a.rtl.resolve())]
    manifest['python_paths']=[str(here),str(here.parents[1]/'pyuvm')]
    manifest['test_module']='isa_test'
    (out/'bench.json').write_text(json.dumps(manifest,indent=2)+'\n')
    os.environ['RVW_CPU_ELF']=str(selected[0])
    os.environ['RVW_CPU_SHIM']=str(a.shim.resolve())
    os.environ['RVW_CPU_ISA_PROGRAMS']=json.dumps([p.name for p in selected])
    report=run(out/'bench.json',out/'run',timeout=a.timeout)
    summaries={}
    for file in (out/'run').rglob('cpu-checks-rv32*.json'):
        name=file.name.removeprefix('cpu-checks-').removesuffix('.json')
        if name in summaries: raise ValueError('duplicate program summary: '+name)
        summaries[name]=json.loads(file.read_text())
    rows=[dict(program=p.name,elf_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
        status='checked' if p.name in summaries else 'not established',
        **summaries.get(p.name,{})) for p in selected]
    (out/'isa-results.json').write_text(json.dumps(dict(
        scope='built RV32UI/RV32UM machine-mode riscv-tests; live pyuvm VexRiscv binding',
        programs=rows,selected=len(rows),checked=len(summaries),
        failures=[r for r in report['tests'] if r['status']!='pass']),indent=2)+'\n')
    if len(summaries)!=len(rows) or any(r['status']!='pass' for r in report['tests']):
        raise SystemExit('ISA campaign incomplete; inspect isa-results.json and run logs')
    print(f'{len(rows)} programs checked through live pyuvm')


if __name__=='__main__':main()
