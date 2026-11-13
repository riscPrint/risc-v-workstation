#!/usr/bin/env python3
"""Check the exported MulSimplePlugin product cell against the RV32 MUL model.

This isolates one real arithmetic cell. It does not check plugin control.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
from rvw.common.proc import run_group


def extract(module):
    product=module['netnames']['_zz_memory_MUL_1']['bits']
    matches=[(name,cell) for name,cell in module['cells'].items() if cell['type']=='$mul' and cell['connections']['Y']==product]
    if len(matches)!=1:
        raise ValueError('expected exactly one real MulSimplePlugin product cell')
    name,cell=matches[0]
    opa=module['netnames']['memory_MUL_OPA']['bits']
    opb=module['netnames']['memory_MUL_OPB']['bits']
    if (len(opa)!=33 or len(opb)!=33 or len(product)<32
        or cell['connections']['A'] != opa + [opa[-1]]*(len(cell['connections']['A'])-33)
        or cell['connections']['B'] != opb + [opb[-1]]*(len(cell['connections']['B'])-33)):
        raise ValueError('unexpected product interface; inspect the export')
    sub={'attributes':{},'ports':{},'cells':{name:copy.deepcopy(cell)},'netnames':{}}
    for port,direction,bits in [('a33','input',opa),('b33','input',opb),('p','output',product)]:
        sub['ports'][port]={'direction':direction,'bits':bits}
        sub['netnames'][port]={'hide_name':0,'bits':bits,'attributes':{}}
    return sub,name,cell,product


def main():
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--rtl',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--timeout',type=float,default=120)
    p.add_argument('--width',type=int,choices=[8,16,32],default=32,help='symbolic low operand/result bits; upper input bits are zero')
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    root=Path(__file__).resolve().parents[3]
    raw=a.rtl.read_bytes();(out/'core.v').write_bytes(raw)
    def execute(cmd,name):
        result=run_group([str(root/'scripts/with-lock.sh'),'vex-equiv','nice','-n','10',*cmd],cwd=out,timeout=a.timeout+10,capture=True)
        (out/(name+'.log')).write_text((result.stdout or '')+(result.stderr or ''))
        if result.returncode:
            raise ValueError(name+' failed; see log')
    (out/'map.ys').write_text('read_verilog core.v\nhierarchy -check -top VexTop\nproc\nflatten\nwrite_json core.json\n')
    execute(['yosys','-Q','-s','map.ys'],'map')
    module=json.loads((out/'core.json').read_text())['modules']['VexTop']
    sub,name,cell,product=extract(module)
    (out/'product.json').write_text(json.dumps({'modules':{'RealProduct':sub}},indent=2)+'\n')
    (out/'export.ys').write_text('read_json product.json\nwrite_verilog -noattr product.v\n')
    execute(['yosys','-Q','-s','export.ys'],'export')
    padding = 33-a.width
    wrapper=f'''module dut(input [{a.width-1}:0] a,b, output [{a.width-1}:0] y);
wire [{len(product)-1}:0] p;
RealProduct real_product(.a33({{{padding}'b0,a}}),.b33({{{padding}'b0,b}}),.p(p));
assign y=p[{a.width-1}:0]; endmodule
'''
    (out/'dut.v').write_text((out/'product.v').read_text()+wrapper)
    models=root/'SpinalChecks/c2rtl/models'
    header=(models/'riscv_m.h').read_text();body=(models/'mul32.c').read_text().replace('#include "riscv_m.h"','')
    body=body.replace('return rvw_m(0, 32, a, b);',f'return rvw_m(0, 32, a, b) & {(1<<a.width)-1}ULL;')
    (out/'model.c').write_text(header+body)
    command=[str(root/'rvw/.venv/bin/rvw'),'formal','datapath','--rtl',str(out/'dut.v'),'--model',str(out/'model.c'),
             '--width',str(a.width),'--timeout',str(a.timeout),'--out',str(out/'proof'),'--json']
    result=run_group([str(root/'scripts/with-lock.sh'),'vex-equiv','nice','-n','10',*command],cwd=out,timeout=a.timeout+10,capture=True)
    (out/'proof.log').write_text((result.stdout or '')+(result.stderr or ''))
    report=json.loads((out/'proof/result.json').read_text()) if (out/'proof/result.json').exists() else {}
    summary={'rtl_sha256':hashlib.sha256(raw).hexdigest(),'fresh_elaboration':False,
             'symbolic_operand_bits':a.width,'observed_result_bits':a.width,
             'cell':name,'cell_type':cell['type'],'cell_attributes':cell.get('attributes',{}),
             'status':report.get('status','inconclusive'),'reason':report.get('reason'),
             'scope':'RV32 product cell with restricted zero-extended operands and low result bits; no plugin decode, pipeline or core proof',
             'remaining':['mulh signed modes','divider plugin transactions','VexiiRiscv units','FPU versus SoftFloat']}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
