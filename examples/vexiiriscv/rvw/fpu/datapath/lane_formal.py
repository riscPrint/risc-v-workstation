#!/usr/bin/env python3
"""Bind real execution-unit RTL, specialize the operation, and run case splits."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from lane_unit import wrapper

OPERATIONS={
    'add':(0,0x002082d3,'add'), 'mul':(1,0x102082d3,'mul'),
    'div':(2,0x182082d3,'div'), 'sqrt':(3,0x580082d3,'sqrt'),
    'to-int':(4,0xc00082d3,'to_i32'), 'from-int':(5,0xd00082d3,None),
}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--width',type=int,choices=(32,64),required=True)
    p.add_argument('--rtl',type=Path,required=True)
    p.add_argument('--softfloat',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--timeout',type=int,default=60)
    p.add_argument('--max-latency',type=int,default=128)
    p.add_argument('--operations',nargs='+',choices=OPERATIONS,default=list(OPERATIONS))
    p.add_argument('--cases',nargs='+',choices=['all','finite','normal','nan','infinity','zero','subnormal'],default=['all','normal','zero','subnormal','nan','infinity'])
    p.add_argument('--rounding',type=int,choices=range(5),default=0)
    args=p.parse_args()
    args.out.mkdir(parents=True,exist_ok=False)
    here=Path(__file__).resolve().parent
    root=Path(os.environ['RVW_HOME'])
    spec=importlib.util.spec_from_file_location('sf',root/'SpinalChecks/c2rtl/softfloat.py')
    sf=importlib.util.module_from_spec(spec);spec.loader.exec_module(sf)
    # The reference dispatcher is kept whole. Its operation is a compile-time constant.
    sources,includes=set(),set()
    for op in ('add','sub','mul','div','sqrt','to_i32','to_ui32','mulAdd'):
        dep=sf.prepare(args.softfloat,f'f{args.width}_{op}')
        sources.update(dep[i+1] for i,v in enumerate(dep) if v=='--reference-source')
        includes.update(dep[i+1] for i,v in enumerate(dep) if v=='--reference-include')
    dep=sf.prepare(args.softfloat,f'i32_to_f{args.width}')
    sources.update(dep[i+1] for i,v in enumerate(dep) if v=='--reference-source')
    extra_operations=[f'ui32_to_f{args.width}']
    if args.width==64:extra_operations += ['f64_to_i64','f64_to_ui64','i64_to_f64','ui64_to_f64','f32_to_f64','f64_to_f32']
    for operation in extra_operations:
        dep=sf.prepare(args.softfloat,operation)
        sources.update(dep[i+1] for i,v in enumerate(dep) if v=='--reference-source')
        includes.update(dep[i+1] for i,v in enumerate(dep) if v=='--reference-include')
    dependencies=['--reference-tree',str(args.softfloat)]
    for folder in sorted(includes):dependencies+=['--reference-include',folder]
    for file in sorted(sources):dependencies+=['--reference-source',file]
    (args.out/'load.txt').write_text(subprocess.check_output(['uptime'],text=True))
    for name in args.operations:
        operation,word,_=OPERATIONS[name]
        if args.width==64:word|=1<<25
        out=args.out/name;out.mkdir()
        top=out/'top.v';top.write_text(wrapper(args.rtl,args.width,word,args.rounding))
        rtl=out/'unit.v'
        ys=out/'extract.ys'
        q=lambda path:json.dumps(str(path.resolve()))
        ys.write_text(f'read_verilog {q(args.rtl)} {q(top)}\nhierarchy -check -top FpuLaneUnit\nproc\nflatten\nopt -full\nmemory_map\nopt -full\ncheck -assert\nwrite_verilog -noattr {q(rtl)}\n')
        with (out/'extract.log').open('w') as stream:
            subprocess.run(['yosys','-Q','-s',str(ys)],check=True,stdout=stream,stderr=subprocess.STDOUT,timeout=120)
        reference=out/'reference.c'
        reference.write_text(f'#define FP_WIDTH {args.width}\n#define UNIT_OP {operation}\n'+(here/'lane_reference.c').read_text())
        binding=out/'binding.json'
        binding.write_text(json.dumps(dict(top='FpuLaneUnit',ports={n:n for n in ('a','b','c','start','reset','clk','y','flags','done')}),indent=2)+'\n')
        for case in (['all'] if name=='from-int' else args.cases):
            command=[sys.executable,'-m','rvw','formal','datapath','--rtl',str(rtl),'--binding',str(binding),
                     '--model',str(reference),'--width',str(args.width),'--max-latency',str(args.max_latency),'--case',case,
                     '--rounding',str(args.rounding),'--timeout',str(args.timeout),*dependencies,
                     '--out',str(out/case),'--json']
            result=subprocess.run(command,capture_output=True,text=True)
            (out/(case+'.json')).write_text(result.stdout)
            (out/(case+'.err')).write_text(result.stderr)
            print(name,case,result.returncode,result.stdout[-250:],flush=True)


if __name__=='__main__':main()
