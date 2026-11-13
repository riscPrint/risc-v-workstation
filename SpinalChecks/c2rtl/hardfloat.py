#!/usr/bin/env python3
"""Export real HardFloat binary16/binary32 units and compare them with pinned SoftFloat."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
from pathlib import Path

from rvw.common.proc import run_group

MODELS={'add':'f32_add','mul':'f32_mul','fma':'f32_fma','div':'f32_div','sqrt':'f32_sqrt',
        'to-int':'f32_to_i32','from-int':'i32_to_f32'}


def wrapper(op,fmt=32):
    if op not in MODELS:raise ValueError('unsupported operation')
    if fmt not in (16,32):raise ValueError('format must be binary16 or binary32')
    exp,sig=(5,11) if fmt==16 else (8,24)
    iw,ow=(32 if op=='from-int' else fmt),(32 if op=='to-int' else fmt)
    sequential=op in ('div','sqrt')
    ports=f'input [{iw-1}:0] a,b,c, input [2:0] rm, output [{ow-1}:0] y, output [4:0] flags'
    if sequential:ports+=',input clk,reset,start,output done'
    lines=['module dut('+ports+');',f'wire [{fmt}:0] ar,br,cr,rr;', f'wire [{fmt-1}:0] raw_result;']
    for source in ('a','b','c'):
        lines.append(f'fNToRecFN #({exp},{sig}) recode_{source}(.in({source}),.out({source}r));')
    common=".control(1'b1),.roundingMode(rm)"
    if op in ('add','mul','fma'):
        module={'add':'addRecFN','mul':'mulRecFN','fma':'mulAddRecFN'}[op]
        extra=",.subOp(1'b0)" if op=='add' else ",.op(2'b00),.c(cr)" if op=='fma' else ''
        lines.append(f'{module} #({exp},{sig}) unit0({common},.a(ar),.b(br),.out(rr),.exceptionFlags(flags){extra});')
    elif sequential:
        lines.append(f"divSqrtRecFN_small #({exp},{sig},0) unit0({common},.nReset(!reset),.clock(clk),.inReady(),.inValid(start),.sqrtOp(1'b{int(op=='sqrt')}),.a(ar),.b(br),.outValid(done),.sqrtOpOut(),.out(rr),.exceptionFlags(flags));")
    elif op=='from-int':
        lines.append(f"iNToRecFN #(32,{exp},{sig}) unit0({common},.signedIn(1'b1),.in(a),.out(rr),.exceptionFlags(flags));")
    else:
        lines += ['wire [2:0] integer_flags;',
          f"recFNToIN #({exp},{sig},32) unit0({common},.in(ar),.signedOut(1'b1),.out(y),.intExceptionFlags(integer_flags));",
          "assign flags = {integer_flags[2] | integer_flags[1],3'b000,integer_flags[0]};",'endmodule']
        return '\n'.join(lines)+'\n'
    lines += [f'recFNToFN #({exp},{sig}) decode(.in(rr),.out(raw_result));',
              f"assign y=(&raw_result[{fmt-2}:{sig-1}]) && (|raw_result[{sig-2}:0]) ? {fmt}'h{0x7e00 if fmt==16 else 0x7fc00000:x} : raw_result;",'endmodule']
    return '\n'.join(lines)+'\n'


def reference_source(op,fmt=32):
    root=Path(__file__).resolve().parents[2]
    reference=(root/'SpinalChecks/c2rtl/models'/(MODELS[op]+'.c')).read_text()
    if fmt==16:
        reference=reference.replace('float32_t','float16_t').replace('f32_','f16_').replace('_to_f32','_to_f16')
        for old,new in [('2139095040ULL','31744ULL'),('8388607ULL','1023ULL'),('2143289344ULL','32256ULL')]:
            reference=reference.replace(old,new)
    return reference


def run(hardfloat,softfloat,out,operations,cases,roundings,timeout,jobs=3,max_latency=64,fmt=32):
    root=Path(__file__).resolve().parents[2]
    if not 1<=jobs<=3:raise ValueError('jobs must be in 1..3')
    source=hardfloat/'source'
    out.mkdir(parents=True,exist_ok=False)
    spec=importlib.util.spec_from_file_location('softfloat_dependencies',Path(__file__).with_name('softfloat.py'))
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    deps={op:helper.prepare(softfloat,f'f{fmt}_mulAdd' if op=='fma' else MODELS[op].replace('f32',f'f{fmt}')) for op in operations}
    files=sorted(source.glob('*.v'))+sorted((source/'RISCV').glob('*.v'))
    manifest={'schema':'rvw.hardfloat-campaign/1','format':fmt,'hardfloat_files':{str(p.relative_to(hardfloat)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(source.rglob('*')) if p.is_file()},
      'softfloat_revision':helper.REVISION,'operations':operations,'cases':cases,'roundings':roundings,
      'scope':f'binary{fmt} units; first operand case split only; canonical NaN; tininess after rounding; all result bits and flags',
      'jobs':jobs,'max_latency':max_latency,'timeout_per_proof':timeout,'exports':{},'results':[]}
    # Export once per operation. Native proof runs then own isolated output trees.
    for op in operations:
        directory=out/op;directory.mkdir()
        (directory/'wrapper.v').write_text(wrapper(op,fmt))
        (directory/'reference.c').write_text(reference_source(op,fmt))
        if fmt==16 and op in ('to-int','from-int'):
            binding={'top':'dut','ports':{name:name for name in ('a','b','c','rm','y','flags')}}
            if op=='to-int':binding['input_widths']={name:32 for name in ('a','b','c')}
            else:binding['output_widths']={'y':32}
            (directory/'binding.json').write_text(json.dumps(binding)+'\n')
        script='\n'.join('read_verilog -I'+str(source)+' -I'+str(source/'RISCV')+' '+json.dumps(str(p)) for p in files)
        script+='\nread_verilog '+str(directory/'wrapper.v')+'\nhierarchy -check -top dut\nproc\nflatten\nopt_clean\ncheck -assert\nwrite_verilog -noattr '+str(directory/'dut.v')+'\n'
        (directory/'export.ys').write_text(script)
        process=run_group(['nice','-n','10','yosys','-Q','-s',str(directory/'export.ys')],timeout=timeout,capture=True)
        (directory/'export.log').write_text((process.stdout or '')+(process.stderr or ''))
        manifest['exports'][op]={'exit':process.returncode,'timed_out':process.timed_out}
    work=[(op,case,rm) for op in operations if manifest['exports'][op]['exit']==0
          for case in (['all'] if op=='from-int' else cases) for rm in roundings]
    def prove(item):
        op,case,rm=item;directory=out/op/f'{case}-rm{rm}'
        word_width=32 if op in ('to-int','from-int') else fmt
        model=out/op/'reference.c'
        command=[str(root/'rvw/.venv/bin/rvw'),'formal','datapath','--rtl',str(out/op/'dut.v'),
                 '--model',str(model),'--width',str(word_width),
                 '--rounding',str(rm),'--case',case,'--timeout',str(timeout),'--out',str(directory),'--json',*deps[op]]
        if fmt==16:
            command+=['--case-width',str(32 if op=='from-int' else 16)]
            if op in ('to-int','from-int'):
                command+=['--binding',str(out/op/'binding.json')]
        if op in ('div','sqrt'):command+=['--max-latency',str(max_latency)]
        process=run_group(['nice','-n','10',*command],timeout=timeout+10,capture=True)
        (out/op/(case+f'-rm{rm}.log')).write_text((process.stdout or '')+(process.stderr or ''))
        report=json.loads((directory/'result.json').read_text()) if (directory/'result.json').exists() else {}
        return {'operation':op,'case':case,'rounding':rm,'status':report.get('status','inconclusive'),
                'reason':report.get('reason'),'wall_s':report.get('wall_s'),'max_latency':max_latency if op in ('div','sqrt') else None,'result':str((directory/'result.json').relative_to(out))}
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        for record in pool.map(prove,work):
            manifest['results'].append(record)
            (out/'summary.json').write_text(json.dumps(manifest,indent=2)+'\n')
            print(json.dumps(record),flush=True)
    (out/'summary.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--hardfloat',type=Path,required=True)
    p.add_argument('--softfloat',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--operations',default='add,mul,fma,div,sqrt,to-int,from-int')
    p.add_argument('--cases',default='zero,nan')
    p.add_argument('--roundings',default='0,1,2,3,4')
    p.add_argument('--timeout',type=float,default=90)
    p.add_argument('--jobs',type=int,choices=[1,2,3],default=3)
    p.add_argument('--max-latency',type=int,default=64)
    p.add_argument('--format',type=int,choices=[16,32],default=32)
    a=p.parse_args()
    run(a.hardfloat.resolve(),a.softfloat.resolve(),a.out.resolve(),a.operations.split(','),a.cases.split(','),[int(x) for x in a.roundings.split(',')],a.timeout,a.jobs,a.max_latency,a.format)
