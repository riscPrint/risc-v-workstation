#!/usr/bin/env python3
"""Compile and simulate the real Vexii execution-unit FP path against SoftFloat."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess


def wrapper(rtl,width,instruction=None,rounding=None):
    header=rtl.read_text().split('module VexiiRiscv (',1)[1].split(');',1)[0]
    ports=re.findall(r'^\s*(input|output)\s+wire\s*(?:\[\d+:\d+\])?\s+(\w+)',header,re.M)
    role={f'unit_{name}':name for name in ('a','b','c','instruction','rm','start','y','flags','done')}
    role.update(clk='clk',reset='reset')
    connections=[]
    for direction,name in ports:
        if name=='unit_instruction' and instruction is not None:
            value=f"32'h{instruction:08x}"
        elif name=='unit_rm' and rounding is not None:
            value=f"3'd{rounding}"
        else:
            value=role.get(name,"'0" if direction=='input' else '')
        connections.append(f'.{name}({value})')
    extra='' if instruction is not None else 'input wire [31:0] instruction, '
    extra+='input wire [2:0] rm, ' if rounding is None else ''
    return f'''module FpuLaneUnit(input wire clk, reset, start,
input wire [{width-1}:0] a,b,c, {extra}
output wire [{width-1}:0] y, output wire [4:0] flags, output wire done);
VexiiRiscv core({','.join(connections)});
endmodule
'''


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--width',type=int,choices=(32,64),required=True)
    p.add_argument('--rtl',type=Path,required=True)
    p.add_argument('--softfloat',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--spike-plans',type=Path,nargs='+')
    args=p.parse_args()
    here=Path(__file__).resolve().parent
    root=Path(os.environ['RVW_HOME']).resolve()
    spec=importlib.util.spec_from_file_location('sf',root/'SpinalChecks/c2rtl/softfloat.py')
    sf=importlib.util.module_from_spec(spec);spec.loader.exec_module(sf)
    sources,includes=set(),set()
    for operation in ('add','sub','mul','div','sqrt','to_i32','to_ui32','mulAdd'):
        dep=sf.prepare(args.softfloat,f'f{args.width}_{operation}')
        sources.update(args.softfloat/dep[i+1] for i,v in enumerate(dep) if v=='--reference-source')
        includes.update(args.softfloat/dep[i+1] for i,v in enumerate(dep) if v=='--reference-include')
    dep=sf.prepare(args.softfloat,f'i32_to_f{args.width}')
    sources.update(args.softfloat/dep[i+1] for i,v in enumerate(dep) if v=='--reference-source')
    extra_operations=[f'ui32_to_f{args.width}']
    if args.width==64:extra_operations += ['f64_to_i64','f64_to_ui64','i64_to_f64','ui64_to_f64','f32_to_f64','f64_to_f32']
    for operation in extra_operations:
        dep=sf.prepare(args.softfloat,operation)
        sources.update(args.softfloat/dep[i+1] for i,v in enumerate(dep) if v=='--reference-source')
        includes.update(args.softfloat/dep[i+1] for i,v in enumerate(dep) if v=='--reference-include')
    args.out.mkdir(parents=True,exist_ok=False)
    reference=args.out/'reference.c'
    reference.write_text(f'#define FP_WIDTH {args.width}\n'+(here/'lane_reference.c').read_text())
    def run(argv,log):
        with (args.out/log).open('w') as out:
            subprocess.run([str(a) for a in argv],stdout=out,stderr=subprocess.STDOUT,check=True)
    objects=[]
    for index,source in enumerate([reference,*sorted(sources)]):
        obj=args.out/f'reference-{index}.o';objects.append(obj)
        run(['cc','-O2','-std=c11',*[a for path in sorted(includes) for a in ('-I',path)],'-c',source,'-o',obj],f'cc-{index}.log')
    archive=args.out/'reference.a';run(['ar','rcs',archive,*objects],'archive.log')
    top=args.out/'FpuLaneUnit.v';top.write_text(wrapper(args.rtl,args.width))
    run(['verilator','--cc','--exe','--build','-j','2','-Wno-fatal','--top-module','FpuLaneUnit',
         '--Mdir',args.out/'model','-CFLAGS',f'-DFP_WIDTH={args.width}','-LDFLAGS',str(archive),
         args.rtl,top,here/'lane_vectors.cpp'],'verilator.log')
    vectors=[]
    if args.spike_plans:
        from spike_vectors import export
        path=args.out/'spike-vectors.txt'
        export(args.spike_plans,args.width,path)
        vectors=[path]
    run([args.out/'model/VFpuLaneUnit',*vectors],'vectors.jsonl')
    print((args.out/'vectors.jsonl').read_text(),flush=True)


if __name__=='__main__': main()
