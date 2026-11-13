"""Two-copy digital observation contracts and initial-state independence."""
import json
import math
from pathlib import Path
import time

from rvw.common.proc import run_group
from rvw.formal.apps import flow, ident
from rvw.formal.snapshot import digest


def generate(plan):
    top=ident(plan['top']); ports=plan['ports']
    clock,reset=ident(plan['clock']),ident(plan['reset'])
    if clock==reset or any(ports.get(p)!={'direction':'input','width':1} for p in (clock,reset)):
        raise ValueError('distinct scalar clock and synchronous active-high reset required')
    secrets=plan.get('secrets',[]);arch=plan.get('architectural',[]);micro=plan['observations']
    if plan.get('kind','noninterference') not in ('noninterference','initialization','constant_time'):
        raise ValueError('unknown pair kind')
    if not micro or any(len(x)!=len(set(x)) for x in (secrets,arch,micro)) or set(arch)&set(micro):
        raise ValueError('distinct architectural and microarchitectural observations required')
    if plan.get('kind')=='constant_time' and (arch or not plan.get('operations')):
        raise ValueError('constant_time needs declared operations and no architectural guard')
    if plan.get('kind')=='initialization':
        if secrets or arch: raise ValueError('initialization compares identical inputs without an architectural guard')
    elif not secrets:
        raise ValueError('declare secret inputs')
    if set(secrets)&{clock,reset}:
        raise ValueError('clock and reset must be public')
    if not plan.get('adversary') or not plan.get('unmodeled_channels'):
        raise ValueError('declare adversary and unmodeled_channels')
    for names,direction in ((secrets,'input'),(arch+micro,'output')):
        if any(name not in ports or ports[name]['direction']!=direction for name in names):
            raise ValueError('secrets must be inputs and observations must be outputs')
    declarations=[];wires=[];connections={'l':[],'r':[]}
    for name,port in ports.items():
        ident(name);width=port['width'];direction=port['direction']
        if name.startswith('rvws_') or type(width) is not int or not 1<=width<=4096 or direction not in ('input','output'):
            raise ValueError('plain ports with input/output direction and width 1..4096 required')
        if direction=='input' and name not in secrets:
            declarations.append(f'input [{width-1}:0] {name}')
        for side in ('l','r'):
            target=f'rvws_{side}_{name}' if direction=='output' or name in secrets else name
            if direction=='output':wires.append(f'wire [{width-1}:0] {target};')
            elif name in secrets:declarations.append(f'input [{width-1}:0] {target}')
            connections[side].append(f'.{name}({target})')
    equal=lambda names:' && '.join(f'(rvws_l_{n} == rvws_r_{n})' for n in names) or "1'b1"
    body=[f'module rvw_security_pair({", ".join(declarations)});',*wires]
    body += [f'{top} rvws_{side}({", ".join(connections[side])});' for side in ('l','r')]
    body += ['reg rvws_arch_equal = 1;',f'always @(posedge {clock}) begin',
             f'if ({reset}) rvws_arch_equal <= 1;',
             f'else begin rvws_arch_equal <= rvws_arch_equal && ({equal(arch)});',
             f'if (rvws_arch_equal && ({equal(arch)})) assert ({equal(micro)});',
             'end end']
    resets=plan.get('reset_values',{})
    if resets:
        body += ['reg rvws_reset_seen = 0;', f'always @(posedge {clock}) begin',
                 f'rvws_reset_seen <= {reset};', 'if (rvws_reset_seen) begin']
        for name,value in resets.items():
            if name not in ports or ports[name]['direction']!='output' or type(value) is not int or not 0<=value<1<<ports[name]['width']:
                raise ValueError('reset_values need declared outputs and fitting unsigned values')
            for side in ('l','r'):
                body.append(f"assert (rvws_{side}_{name} == {ports[name]['width']}'d{value});")
        body += ['end end']
    body += ['endmodule','']
    return '\n'.join(body)


def run(args):
    out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=False)
    started=time.monotonic()
    result={'schema':'rvw.security-pair/1','status':'inconclusive'}
    try:
        if not math.isfinite(args.timeout) or args.timeout<=0:raise ValueError('positive finite timeout required')
        def budget():
            left=args.timeout-(time.monotonic()-started)
            if left<=0:raise ValueError('total time limit')
            return left
        path=Path(args.manifest).resolve();plan=json.loads(path.read_text())
        if plan.get('schema')!='rvw.security-pair/1':raise ValueError('expected rvw.security-pair/1')
        wrapper=generate(plan)
        if plan['top']=='rvw_security_pair':raise ValueError('reserved top')
        raw=(path.parent/plan['rtl']).read_bytes()
        if b'`include' in raw or b'$readmem' in raw:raise ValueError('self-contained RTL required')
        (out/'dut.v').write_bytes(raw);(out/'plan.json').write_text(json.dumps(plan,indent=2))
        result['plan']=plan;result['rtl_sha256']=digest(out/'dut.v')
        script=f'read_verilog -formal dut.v\nhierarchy -check -top {plan["top"]}\nproc\nflatten\ncheck -assert\nwrite_json mapped.json\n'
        (out/'map.ys').write_text(script)
        process=run_group(['yosys','-Q','-s','map.ys'],cwd=out,timeout=budget(),capture=True)
        (out/'map.log').write_text((process.stdout or '')+(process.stderr or ''))
        if process.timed_out or process.returncode:raise ValueError('RTL mapping failed')
        mod=json.loads((out/'mapped.json').read_text())['modules'][plan['top']]
        actual={name:{'direction':p['direction'],'width':len(p['bits'])} for name,p in mod['ports'].items()}
        if actual!=plan['ports']:raise ValueError('declared ports differ from RTL')
        forbidden={'$assume','$assert','$cover','$anyseq','$anyconst','$allseq','$allconst','$initstate','$check','$fair','$live'}
        if any(c['type'] in forbidden for c in mod['cells'].values()):raise ValueError('DUT formal properties and nondeterministic cells are refused')
        (out/'pair.sv').write_text(wrapper)
        proof=flow([out/'dut.v',out/'pair.sv'],'rvw_security_pair',plan['clock'],plan['reset'],
                   out/'proof',20,'abc:pdr',budget(),'prove',{plan['top']:plan['ports']})
        result['proof']=proof
        declared=sum(plan['ports'][name]['width'] for name in plan.get('reset_values',{}))
        total=sum(p['width'] for p in plan['ports'].values() if p['direction']=='output')
        result['reset_coverage']={'declared_bits':declared,'output_bits':total,
                                  'proved_bits':declared if proof.get('status')=='pass' else 0,
                                  'scope':'declared output reset values only; no internal register coverage claim'}
        if proof.get('status') in ('pass','fail'):result['status']=proof['status']
        result['semantics']='equal architectural observation prefixes imply equal simultaneous digital observation samples'
        result['limits']='Declared digital channels and reset only. No physical leakage or whole-core security claim. Architectural observation timing is part of the declared contract.'
    except (ValueError,KeyError,TypeError,OSError) as exc:
        result['reason']=str(exc)
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
    return 0 if result['status']=='pass' else 1
