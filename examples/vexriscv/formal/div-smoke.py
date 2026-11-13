#!/usr/bin/env python3
"""Check an extracted real DivPlugin under a single-transaction stage adapter."""
import argparse
import hashlib
import json
from pathlib import Path
import re
from rvw.common.proc import run_group

INPUTS={'clk':1,'reset':1,'execute_RS1':32,'execute_RS2':32,'execute_INSTRUCTION':32,
        'execute_IS_RS1_SIGNED':1,'execute_IS_RS2_SIGNED':1,'execute_IS_DIV':1,
        'memory_INSTRUCTION':32,'memory_IS_DIV':1,'memory_arbitration_isValid':1,'memory_arbitration_isStuck':1}
OUTPUTS={'memory_DivPlugin_div_result':32,'memory_DivPlugin_div_done':1}


def operand(name,bits,signed):
    if bits==32: return name
    fill=f"{name}[{bits-1}]" if signed else "1'b0"
    return "{{"+str(32-bits)+"{"+fill+"}},"+name+f"[{bits-1}:0]"+"}"


def adapter(operation,divisor):
    funct3={'div':4,'divu':5,'rem':6,'remu':7}[operation]
    signed=int(operation in ('div','rem'))
    values={'clk':'clk','reset':'reset','execute_RS1':'a','execute_RS2':"32'h0" if divisor=='zero' else "32'hffffffff" if divisor=='minus-one' else 'b',
            'execute_INSTRUCTION':f"32'h{funct3<<12:08x}",'execute_IS_RS1_SIGNED':f"1'b{signed}",
            'execute_IS_RS2_SIGNED':f"1'b{signed}",'execute_IS_DIV':"1'b1",
            'memory_INSTRUCTION':f"32'h{funct3<<12:08x}",'memory_IS_DIV':"1'b1",
            'memory_arbitration_isValid':'active','memory_arbitration_isStuck':'active && !raw_done',
            'memory_DivPlugin_div_result':'y','memory_DivPlugin_div_done':'raw_done'}
    return '''module dut(input clk,reset,start,input [31:0] a,b,output [31:0] y,output done);
reg active;
always @(posedge clk) if(reset) active<=0;else if(start) active<=1;
wire raw_done;
assign done=active && raw_done;
VexTop unit0('''+', '.join(f'.{n}({v})' for n,v in values.items())+');\nendmodule\n'


def closed_cone(module):
    """Keep every driver in the declared output cone, including register D inputs."""
    live={bit for name,port in module['ports'].items() if port['direction']=='output' for bit in port['bits'] if isinstance(bit,int)}
    selected=set()
    while True:
        previous=len(selected)
        for name,cell in module['cells'].items():
            if name in selected:continue
            directions=cell.get('port_directions',{})
            outputs={bit for port,bits in cell['connections'].items() if directions.get(port)=='output' for bit in bits if isinstance(bit,int)}
            if outputs & live:
                selected.add(name)
                live.update(bit for bits in cell['connections'].values() for bit in bits if isinstance(bit,int))
        if len(selected)==previous:break
    module['cells']={name:cell for name,cell in module['cells'].items() if name in selected}
    module['netnames']={name:net for name,net in module['netnames'].items() if set(net['bits']) & live}
    return module


def main():
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--rtl',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--top',default='VexTop')
    p.add_argument('--operand-bits',type=int,choices=[8,16,32],default=32)
    p.add_argument('--divisor',choices=['full','zero','minus-one'],default='full')
    p.add_argument('--operations',default='div,divu,rem,remu');p.add_argument('--timeout',type=float,default=90)
    a=p.parse_args()
    operations=a.operations.split(',')
    if not operations or len(set(operations))!=len(operations) or set(operations)-{'div','divu','rem','remu'}:
        raise ValueError('select distinct divider operations')
    root=Path(__file__).resolve().parents[3];out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    raw=a.rtl.read_bytes();(out/'core.v').write_text(raw.decode().replace('module '+a.top+' (','module VexTop ('))
    def execute(cmd,name):
        proc=run_group([str(root/'scripts/with-lock.sh'),'vex-conn','nice','-n','15',*cmd],cwd=out,timeout=a.timeout+10,capture=True)
        (out/(name+'.log')).write_text((proc.stdout or '')+(proc.stderr or ''))
        if proc.returncode:raise ValueError(name+' failed; see log')
    script='read_verilog core.v\nhierarchy -check -top VexTop\nproc\nflatten\n'
    script+='write_json cut.json\n'
    (out/'cut.ys').write_text(script);execute(['yosys','-Q','-s','cut.ys'],'cut')
    design=json.loads((out/'cut.json').read_text());module=design['modules']['VexTop']
    wanted={**INPUTS,**OUTPUTS}
    ports={}
    cutbits=set()
    for name,width in wanted.items():
        net=module['netnames'].get(name)
        if not net or len(net['bits'])!=width:
            raise ValueError('unexpected plugin boundary: '+name)
        ports[name]={'direction':'output' if name in OUTPUTS else 'input','bits':list(net['bits'])}
        if name in INPUTS and name not in ('clk','reset'):
            if any(not isinstance(bit,int) or bit in cutbits for bit in net['bits']):
                raise ValueError('constant or aliased plugin input: '+name)
            cutbits.update(net['bits'])
    module['ports']=ports
    nextbit=max(bit for cell in module['cells'].values() for bits in cell['connections'].values() for bit in bits if isinstance(bit,int))+1
    # Cut all aliases of each boundary bit. Yosys expose by wire name can leave
    # consumers on a merged alias after proc optimization.
    for cell in module['cells'].values():
        for pin,bits in cell['connections'].items():
            if cell.get('port_directions',{}).get(pin)=='output':
                replaced=[]
                for bit in bits:
                    if bit in cutbits:
                        replaced.append(nextbit);nextbit+=1
                    else:replaced.append(bit)
                cell['connections'][pin]=replaced
    for net in module['netnames'].values():
        if set(net['bits']) & cutbits:
            net.get('attributes',{}).pop('init',None)
    closed_cone(module)
    (out/'selected.json').write_text(json.dumps(design)+'\n')
    (out/'export.ys').write_text('read_json selected.json\nopt_clean -purge\ncheck -assert\nwrite_verilog -noattr plugin.v\n')
    execute(['yosys','-Q','-s','export.ys'],'export')
    summary={'rtl_sha256':hashlib.sha256(raw).hexdigest(),'fresh_elaboration':False,'divisor':a.divisor,'operand_bits':a.operand_bits,
       'scope':'isolated real plugin; fixed opcode; stable operands; first transaction; stage validity and stall supplied by the adapter',
       'boundary':wanted,'results':[]}
    for op in operations:
        directory=out/op;directory.mkdir()
        wrapper=adapter(op,a.divisor)
        for name in ('a','b'):
            wrapper=wrapper.replace('.execute_RS'+('1' if name=='a' else '2')+'('+name+')', '.execute_RS'+('1' if name=='a' else '2')+'('+operand(name,a.operand_bits,op in ('div','rem'))+')')
        (directory/'dut.v').write_text((out/'plugin.v').read_text()+wrapper)
        models=root/'SpinalChecks/c2rtl/models'
        body=(models/(op+'32.c')).read_text().replace('#include "riscv_m.h"','')
        if a.operand_bits<32:
            mask=(1<<a.operand_bits)-1; sign=1<<(a.operand_bits-1)
            for name in ('a','b'):
                expr=f'({name} & {mask}ULL)'
                if op in ('div','rem'): expr=f'((({expr} ^ {sign}ULL)-{sign}ULL)&0xffffffffULL)'
                body=body.replace('return rvw_m(',f'{name}={expr}; return rvw_m(')
        if a.divisor!='full':
            literal='0ULL' if a.divisor=='zero' else '4294967295ULL'
            body=re.sub(r'(rvw_m\(\d+, 32, a, )b(\))',lambda m:m[1]+literal+m[2],body)
        (directory/'model.c').write_text((models/'riscv_m.h').read_text()+body)
        cmd=[str(root/'rvw/.venv/bin/rvw'),'formal','datapath','--rtl',str(directory/'dut.v'),'--model',str(directory/'model.c'),
             '--width','32','--max-latency','64','--timeout',str(a.timeout),'--out',str(directory/'proof'),'--json']
        process=run_group([str(root/'scripts/with-lock.sh'),'vex-conn','nice','-n','15',*cmd],cwd=out,timeout=a.timeout+10,capture=True)
        (directory/'proof.log').write_text((process.stdout or '')+(process.stderr or ''))
        report=json.loads((directory/'proof/result.json').read_text()) if (directory/'proof/result.json').exists() else {}
        summary['results'].append({'operation':op,'status':report.get('status','inconclusive'),'reason':report.get('reason') or ('process timeout before result capture; inspect proof.log for lock wait or frontend stage' if process.timed_out else 'no native result' if not report else None),'wall_s':report.get('wall_s')})
        (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
        print(json.dumps(summary['results'][-1]),flush=True)


if __name__=='__main__':main()
