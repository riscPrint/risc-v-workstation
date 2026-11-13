"""Operand-paired latency sampling on a declared synchronous RTL unit."""
import json
from pathlib import Path
import re
from .common import native, publish


def run(manifest,out):
    manifest=Path(manifest).resolve(); plan=json.loads(manifest.read_text())
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    (out/'manifest.json').write_bytes(manifest.read_bytes())
    top=plan['top']
    if not re.fullmatch('[A-Za-z_][A-Za-z0-9_]*',top): raise ValueError('simple top required')
    rtl=Path(plan['rtl']);rtl=rtl if rtl.is_absolute() else manifest.parent/rtl
    (out/'unit.sv').write_bytes(rtl.read_bytes())
    native(['yosys','-Q','-p',f'read_verilog -sv unit.sv; hierarchy -check -top {top}; proc; write_json unit.json'],out)
    ports=json.loads((out/'unit.json').read_text())['modules'][top]['ports']
    if any(not re.fullmatch('[A-Za-z_][A-Za-z0-9_]*',n) or p['direction'] not in ('input','output') for n,p in ports.items()):
        raise ValueError('simple input/output ports required')
    clock,reset,start,done=(plan[k] for k in ('clock','reset','start','done'))
    if len({clock,reset,start,done})!=4: raise ValueError('distinct timing control ports required')
    for n in (clock,reset,start,done):
        if n not in ports or len(ports[n]['bits'])!=1 or ports[n]['direction']!=('output' if n==done else 'input'):
            raise ValueError('scalar timing ports with correct directions required')
    inputs={n:len(p['bits']) for n,p in ports.items() if p['direction']=='input' and n not in (clock,reset,start)}
    operands=plan['operands']
    if not operands or set(operands)-inputs.keys(): raise ValueError('declare operand input ports')
    cycles=plan.get('max_cycles',100)
    if type(cycles) is not int or not 1<=cycles<=10000: raise ValueError('max_cycles must be 1..10000')
    pairs=plan['pairs']
    if not pairs: raise ValueError('nonempty operand pairs required')
    lines=['module tb;']
    for n,p in ports.items():
        lines.append(f'{"reg" if p["direction"]=="input" else "wire"} [{len(p["bits"])-1}:0] {n};')
    lines += [f'{top} dut('+','.join(f'.{n}({n})' for n in ports)+');','integer measured;','initial begin']
    for i,pair in enumerate(pairs):
        if not pair.get('operation'): raise ValueError('each pair must declare an operation')
        a,b=pair['a'],pair['b']
        if set(a)!=set(inputs) or set(b)!=set(inputs): raise ValueError('bind every data input')
        if not any(a[n]!=b[n] for n in operands) or any(a[n]!=b[n] for n in inputs if n not in operands):
            raise ValueError('vary operands only; keep public inputs equal')
        for j,values in enumerate((a,b)):
            if any(type(v) is not int or not 0<=v<1<<inputs[n] for n,v in values.items()):
                raise ValueError('input value outside port width')
            lines += [f'{clock}=0; {reset}=1; {start}=0; measured=0;']
            lines += [f"{n}={inputs[n]}'d{v};" for n,v in values.items()]
            lines += [f'repeat(2) begin #1; {clock}=1; #1; {clock}=0; end',
                      f'{reset}=0; {start}=1;']
            for cycle in range(1,cycles+1):
                lines += [f'#1; {clock}=1; #1;',
                          f'if ({done} && !measured) begin measured=1; $display("LAT {i} {j} {cycle}"); end',
                          f'{clock}=0; {start}=0;']
    lines += ['$display("LAT_END"); $finish; end endmodule']
    (out/'tb.sv').write_text('\n'.join(lines))
    native(['verilator','--binary','--timing','-Wno-fatal','--top-module','tb','unit.sv','tb.sv'],out)
    log=native([str(out/'obj_dir/Vtb')],out);(out/'simulation.log').write_text(log)
    measured={(int(i),int(j)):int(c) for i,j,c in re.findall(r'^LAT (\d+) (\d+) (\d+)$',log,re.M)}
    findings=[];samples=[]
    for i,pair in enumerate(pairs):
        a,b=measured.get((i,0)),measured.get((i,1))
        samples.append(dict(operation=pair['operation'],latencies=[a,b]))
        if a is not None and b is not None and a!=b:
            findings.append(dict(pair=i,operation=pair['operation'],latencies=[a,b]))
    complete='LAT_END' in log and len(measured)==2*len(pairs)
    return publish(out,'latency',findings,complete,samples=samples,
                   binding='start pulse to first done sample after reset',declaration=plan.get('declaration','crypto-unit'))
