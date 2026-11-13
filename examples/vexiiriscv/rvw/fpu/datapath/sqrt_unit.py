#!/usr/bin/env python3
"""Run the isolated VexiiRiscv mantissa sqrt harness against SoftFloat.

The IEEE adapter accepts absolute normal inputs only. This is not a check of
VexiiRiscv's unpacker, packer, other FP operations, or complete FSQRT instruction.
"""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--width',type=int,choices=(32,64),required=True)
    p.add_argument('--rtl',type=Path,required=True)
    p.add_argument('--softfloat',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--formal',action='store_true')
    p.add_argument('--timeout',type=int,default=60)
    args=p.parse_args()
    here=Path(__file__).resolve().parent
    root=Path(os.environ['RVW_HOME']).resolve()
    spec=importlib.util.spec_from_file_location('softfloat_dependencies',root/'SpinalChecks/c2rtl/softfloat.py')
    sf=importlib.util.module_from_spec(spec);spec.loader.exec_module(sf)
    dependencies=sf.prepare(args.softfloat,'f32_sqrt' if args.width==32 else 'f64_sqrt')
    sources=[args.softfloat/dependencies[i+1] for i,v in enumerate(dependencies) if v=='--reference-source']
    includes=[args.softfloat/dependencies[i+1] for i,v in enumerate(dependencies) if v=='--reference-include']
    args.out.mkdir(parents=True,exist_ok=False)
    reference=args.out/'reference.c'
    reference.write_text(f'#define FP_WIDTH {args.width}\n'+(here/'sqrt_reference.c').read_text())
    def run(argv,log):
        with (args.out/log).open('w') as out:
            subprocess.run([str(a) for a in argv],stdout=out,stderr=subprocess.STDOUT,check=True)
    objects=[]
    for index,source in enumerate([reference,*sources]):
        obj=args.out/f'reference-{index}.o';objects.append(obj)
        run(['cc','-O2','-std=c11',*[a for path in includes for a in ('-I',path)],'-c',source,'-o',obj],f'cc-{index}.log')
    archive=args.out/'reference.a';run(['ar','rcs',archive,*objects],'archive.log')
    run(['verilator','--cc','--exe','--build','-j','2','-Wno-fatal','--top-module','FpuSqrtHarness',
         '--Mdir',args.out/'model','-CFLAGS',f'-DFP_WIDTH={args.width}','-LDFLAGS',str(archive),
         args.rtl,here/'sqrt_vectors.cpp'],'verilator.log')
    run([args.out/'model/VFpuSqrtHarness'],'vectors.json')
    print((args.out/'vectors.json').read_text().strip(),flush=True)
    binding=args.out/'binding.json'
    binding.write_text(json.dumps(dict(top='FpuSqrtHarness',ports={
        'clk':'clk','reset':'reset','start':'io_start','done':'io_done',
        'a':'io_a','rm':'io_rm','y':'io_y','flags':'io_flags'},unused_inputs={'b':args.width,'c':args.width}),indent=2)+'\n')
    if args.formal:
        # Normal source exponents only; both signs map to the same positive operand.
        for rounding in range(5):
            argv=[sys.executable,'-m','rvw','formal','datapath','--rtl',str(args.rtl),
                  '--binding',str(binding),'--model',str(reference),'--width',str(args.width),
                  '--max-latency',str((23 if args.width==32 else 52)+7),'--case','normal',
                  '--rounding',str(rounding),'--timeout',str(args.timeout),*dependencies,
                  '--out',str(args.out/f'normal-rm{rounding}'),'--json']
            result=subprocess.run(argv,capture_output=True,text=True)
            (args.out/f'normal-rm{rounding}.json').write_text(result.stdout)
            (args.out/f'normal-rm{rounding}.err').write_text(result.stderr)
            print(f'normal rm{rounding} exit {result.returncode}',flush=True)


if __name__=='__main__':main()
