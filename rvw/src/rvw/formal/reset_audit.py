"""Conservative one-clock reset values and bounded initial-state influence."""
from itertools import product
import hashlib
import json
import math
from pathlib import Path
import shutil

from rvw.common.proc import run_group
from .bitc import GATES
from .common import check_ident

# Mask bit 0 means value 0 is possible. Mask bit 1 means value 1 is possible.
ZERO = (1, frozenset())
ONE = (2, frozenset())
FREE = (3, frozenset())


def transfer(kind, arguments):
    def boolean(values):
        a = values[0]
        b = values[1] if len(values)>1 else 0
        if kind == '$_BUF_': return a
        if kind == '$_NOT_': return 1-a
        if kind == '$_AND_': return a & b
        if kind == '$_NAND_': return 1-(a & b)
        if kind == '$_OR_': return a | b
        if kind == '$_NOR_': return 1-(a | b)
        if kind == '$_XOR_': return a ^ b
        if kind == '$_XNOR_': return 1-(a ^ b)
        if kind == '$_MUX_': return b if values[2] else a
        raise ValueError('unsupported gate: '+kind)
    domains = [tuple(v for v in (0,1) if mask & (1<<v)) for mask, _ in arguments]
    combinations = list(product(*domains))
    values = {boolean(row) for row in combinations}
    dependencies = set()
    if len(values)>1:
        for index, (_, sources) in enumerate(arguments):
            if not sources or len(domains[index])<2:
                continue
            for row in combinations:
                flipped = (*row[:index],1-row[index],*row[index+1:])
                if boolean(flipped)!=boolean(row):
                    dependencies.update(sources)
                    break
    return sum(1<<v for v in values), frozenset(dependencies)


def analyse(design, top, clock, reset, active, cycles):
    module = design['modules'][top]
    ports = module['ports']
    if clock==reset or any(name not in ports or ports[name]['direction']!='input' or len(ports[name]['bits'])!=1 for name in (clock,reset)):
        raise ValueError('distinct scalar input clock and reset required')
    clock_bit, reset_bit = ports[clock]['bits'][0], ports[reset]['bits'][0]
    if not isinstance(clock_bit,int) or not isinstance(reset_bit,int) or clock_bit==reset_bit:
        raise ValueError('distinct driven clock and reset bits required')
    registers, pending, driven = [], [], set()
    initial = {'0':ZERO, '1':ONE, 'x':(3,frozenset({'literal_xz'})), 'z':(3,frozenset({'literal_xz'}))}
    for port in ports.values():
        if port['direction']=='inout':raise ValueError('inout ports are unsupported')
        if port['direction']=='input':
            for bit in port['bits']:
                if not isinstance(bit,int) or bit in driven:raise ValueError('aliased input bits are unsupported')
                driven.add(bit);initial[bit]=FREE
    for cell in module.get('cells',{}).values():
        kind=cell['type'];connections=cell['connections']
        if any(len(bits)!=1 for bits in connections.values()):
            raise ValueError('only scalar mapped gate and register connections are supported')
        if kind=='$_DFF_P_':
            if connections['C']!=[clock_bit]:raise ValueError('generated or different clocks are unsupported')
            q,d=connections['Q'][0],connections['D'][0]
            if not isinstance(q,int) or q in driven:raise ValueError('multiple state drivers')
            registers.append((q,d));driven.add(q)
            initial[q]=(3,frozenset({q}))
        elif kind in GATES:
            if any(clock_bit in bits for bits in connections.values()):raise ValueError('clock used as data is unsupported')
            pending.append(cell)
        else:
            raise ValueError('unsupported mapped cell: '+kind)
    if not registers:raise ValueError('no retained register bits')
    if any('init' in net.get('attributes',{}) for net in module.get('netnames',{}).values()):
        raise ValueError('initial attributes are unsupported; use explicit reset')
    # Sort the combinational graph once. Unknown initial values are present for
    # every register, but no undriven bit becomes a free input.
    available=set(initial);ordered=[]
    while pending:
        remaining=[]
        for cell in pending:
            connections=cell['connections']
            arguments=[connections[name][0] for name in ('A','B','S') if name in connections]
            if not all(bit in available for bit in arguments):remaining.append(cell);continue
            y=connections['Y'][0]
            if not isinstance(y,int) or y in driven:raise ValueError('multiple combinational drivers')
            driven.add(y);available.add(y);ordered.append((cell['type'],arguments,y))
        if len(remaining)==len(pending):raise ValueError('combinational loop or undriven input')
        pending=remaining
    if any(bit not in available for port in ports.values() for bit in port['bits']):
        raise ValueError('undriven output bit')
    if any(d not in available for _,d in registers):raise ValueError('undriven state input')
    def evaluate(state, reset_asserted):
        values={**initial,**state}
        values[clock_bit]=ZERO
        values[reset_bit]=ONE if reset_asserted==(active=='high') else ZERO
        for kind,arguments,y in ordered:
            values[y]=transfer(kind,[values[bit] for bit in arguments])
        return values
    values=evaluate({},True)
    after_reset={q:values[d] for q,d in registers}
    labels={}
    groups=[]
    qbits={q for q,_ in registers}
    for name,net in sorted(module.get('netnames',{}).items(),key=lambda item:(item[1].get('hide_name',0),item[0])):
        selected=[(i,b) for i,b in enumerate(net['bits']) if b in qbits and b not in labels]
        if selected:
            for index,bit in selected:labels[bit]=f'{name}[{index}]'
            groups.append({'name':name,'bits':[{'index':i,'bit':bit,
                'reset_value':{1:0,2:1}.get(after_reset[bit][0]),
                'initial_dependencies':sorted(d for d in after_reset[bit][1] if isinstance(d,int)),
                'literal_xz':'literal_xz' in after_reset[bit][1]} for i,bit in selected]})
    for bit in sorted(qbits-set(labels)):
        labels[bit]=f'bit{bit}'
        groups.append({'name':labels[bit],'bits':[{'index':0,'bit':bit,'reset_value':{1:0,2:1}.get(after_reset[bit][0]),
            'initial_dependencies':sorted(d for d in after_reset[bit][1] if isinstance(d,int)),
            'literal_xz':'literal_xz' in after_reset[bit][1]}]})
    observations=[];state=after_reset
    for cycle in range(cycles+1):
        values=evaluate(state,False)
        outputs={}
        for name,port in ports.items():
            if port['direction']!='output':continue
            outputs[name]=[{'index':index,'initial_dependencies':sorted(d for d in values[bit][1] if isinstance(d,int)),
                'literal_xz':'literal_xz' in values[bit][1]} for index,bit in enumerate(port['bits'])]
        observations.append({'clocks_after_reset':cycle,'outputs':outputs})
        state={q:values[d] for q,d in registers}
    fixed=sum(mask in (1,2) for mask,_ in after_reset.values())
    initial_dependent=sum(any(isinstance(d,int) for d in deps) for _,deps in after_reset.values())
    return {'registers':groups,'initial_bit_labels':{str(bit):label for bit,label in labels.items()},
        'reset_coverage':{'retained_register_bits':len(qbits),'constant_reset_bits':fixed,
            'nonconstant_reset_bits':len(qbits)-fixed,'bits_with_initial_dependencies':initial_dependent},
        'output_influence':observations}


def run(args):
    out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=False)
    result={'schema':'rvw.reset-audit/1','status':'inconclusive','analysis_status':'incomplete',
            'scope':'conservative Boolean reset constants and bounded potential initial-state paths; no reachability proof'}
    try:
        check_ident('--top',args.top);check_ident('--clock',args.clock);check_ident('--reset',args.reset)
        if not math.isfinite(args.timeout) or args.timeout<=0 or not 0<=args.cycles<=64:
            raise ValueError('positive finite timeout and cycles in 0..64 required')
        tool=shutil.which('yosys')
        if not tool:raise ValueError('missing tool: yosys')
        raw=Path(args.rtl).read_bytes()
        if b'`include' in raw or b'$readmem' in raw:raise ValueError('self-contained RTL required')
        (out/'dut.v').write_bytes(raw)
        result['inputs']={'rtl_sha256':hashlib.sha256(raw).hexdigest()}
        result['tool']={'path':tool,'sha256':hashlib.sha256(Path(tool).read_bytes()).hexdigest()}
        script=f'read_verilog -formal dut.v\nhierarchy -check -top {args.top}\nproc\nflatten\ncheck -assert\ntechmap\nopt_clean\ncheck -assert\nwrite_json mapped.json\n'
        (out/'map.ys').write_text(script)
        process=run_group([tool,'-Q','-s','map.ys'],cwd=out,timeout=args.timeout,capture=True)
        (out/'yosys.log').write_text((process.stdout or '')+(process.stderr or ''))
        if process.returncode or process.timed_out:raise ValueError('mapping failed or timed out')
        result.update(analyse(json.loads((out/'mapped.json').read_text()),args.top,args.clock,args.reset,args.reset_active,args.cycles))
        result['analysis_status']='complete'
        result['restrictions']={'clock':args.clock,'reset':args.reset,'reset_active':args.reset_active,
            'reset_clocks':1,'cycles':args.cycles,'inputs':'arbitrary binary values at each step; clock is not data',
            'initial_state':'all retained registers start arbitrary; no initial attributes'}
    except (ValueError,KeyError,TypeError,OSError) as exc:
        result['reason']=str(exc)
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result) if args.json else f'reset-audit: {result["analysis_status"]} ({out})')
    return 1
