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


def operand(name,bits,signed):
    if bits==32: return name
    fill=f"{name}[{bits-1}]" if signed else "1'b0"
    return "{{"+str(32-bits)+"{"+fill+"}},"+name+f"[{bits-1}:0]"+"}"


def product_adapter(op,bits,product_bits):
    sa=op in ('mulh','mulhsu');sb=op=='mulh'
    left=operand('a',bits,sa);right=operand('b',bits,sb)
    return f"""module dut(input [31:0] a,b,output [31:0] y);
wire [31:0] aa={left}, bb={right};
wire [{product_bits-1}:0] p;
RealProduct unit0(.a33({{{'aa[31]' if sa else "1'b0"},aa}}),.b33({{{'bb[31]' if sb else "1'b0"},bb}}),.p(p));
assign y=p[{'31:0' if op=='mul' else '63:32'}]; endmodule
"""


def reference(op,bits):
    def extend(name,signed):
        mask=(1<<bits)-1
        low=f"({name} & {mask}ULL)"
        return f"(({low} ^ {1<<(bits-1)}ULL) - {1<<(bits-1)}ULL) & 0xffffffffULL" if signed else low
    idx=['mul','mulh','mulhsu','mulhu'].index(op)
    return f"\nuint64_t reference(uint64_t a,uint64_t b,uint64_t c,uint8_t rm,uint8_t *flags){{*flags=0; a={extend('a',op in ('mulh','mulhsu'))}; b={extend('b',op=='mulh')}; return rvw_m({idx},32,a,b);}}\n"


def main():
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--rtl',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--timeout',type=float,default=120)
    p.add_argument('--top',default='VexTop')
    p.add_argument('--operation',choices=['mul','mulh','mulhsu','mulhu'],default='mul')
    p.add_argument('--width',type=int,choices=[8,16,32],default=32,help='symbolic low operand/result bits; upper input bits are zero')
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    root=Path(__file__).resolve().parents[3]
    raw=a.rtl.read_bytes();(out/'core.v').write_text(raw.decode().replace('module '+a.top+' (','module VexTop ('))
    def execute(cmd,name):
        result=run_group([str(root/'scripts/with-lock.sh'),'vex-conn','nice','-n','15',*cmd],cwd=out,timeout=a.timeout+10,capture=True)
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
    (out/'dut.v').write_text((out/'product.v').read_text()+product_adapter(a.operation,a.width,len(product)))
    models=root/'SpinalChecks/c2rtl/models'
    (out/'model.c').write_text((models/'riscv_m.h').read_text()+reference(a.operation,a.width))
    command=[str(root/'rvw/.venv/bin/rvw'),'formal','datapath','--rtl',str(out/'dut.v'),'--model',str(out/'model.c'),
             '--width','32','--timeout',str(a.timeout),'--out',str(out/'proof'),'--json']
    result=run_group([str(root/'scripts/with-lock.sh'),'vex-conn','nice','-n','15',*command],cwd=out,timeout=a.timeout+10,capture=True)
    (out/'proof.log').write_text((result.stdout or '')+(result.stderr or ''))
    report=json.loads((out/'proof/result.json').read_text()) if (out/'proof/result.json').exists() else {}
    summary={'rtl_sha256':hashlib.sha256(raw).hexdigest(),'fresh_elaboration':False,
             'symbolic_operand_bits':a.width,'observed_result_bits':32,'operation':a.operation,
             'cell':name,'cell_type':cell['type'],'cell_attributes':cell.get('attributes',{}),
             'status':report.get('status','inconclusive'),'reason':report.get('reason'),
             'scope':'RV32 product cell with reduced operand domain; full selected RV32 result; no plugin control or core proof',
             'remaining':['unrestricted RV32 arithmetic','plugin control composition','whole-core Sail instruction checks']}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
