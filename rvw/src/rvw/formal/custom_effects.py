"""Project-declared extra state, one memory access and precise trap transitions."""
import copy
import hashlib
import json
from pathlib import Path
import re

from .custom_isa import OPS,expression,encode


def word(tree,ctx,xlen,emit=False,depth=0):
    if depth>12:raise ValueError('effect expression too deep')
    if type(tree) is int:
        return expression(tree,xlen) if emit else expression(tree,xlen,0,0)
    if isinstance(tree,str):
        if tree not in ctx:raise ValueError('unknown effect operand: '+tree)
        value=ctx[tree]
        return f"{xlen}'({value})" if emit else value
    if not isinstance(tree,list) or len(tree)!=3:raise ValueError('invalid bitvector effect expression')
    op=tree[0]
    if op not in OPS:raise ValueError('unsupported bitvector effect operation')
    lhs,rhs=(word(value,ctx,xlen,emit,depth+1) for value in tree[1:])
    if emit:
        if op in ('sll','srl'):rhs=f'({rhs} & {xlen-1})'
        return f"{xlen}'(({lhs}) {OPS[op]} ({rhs}))"
    return expression([op,lhs,rhs],xlen,0,0)


def predicate(tree,ctx,xlen,emit=False,depth=0):
    if depth>12:raise ValueError('trap predicate too deep')
    if type(tree) is bool:return ("1'b1" if tree else "1'b0") if emit else tree
    if not isinstance(tree,list) or not tree:raise ValueError('trap predicate needs Boolean operations')
    op=tree[0]
    if op=='not' and len(tree)==2:
        value=predicate(tree[1],ctx,xlen,emit,depth+1)
        return '!('+value+')' if emit else not value
    if op in ('all','any') and len(tree)>=3:
        values=[predicate(value,ctx,xlen,emit,depth+1) for value in tree[1:]]
        return (' && ' if op=='all' else ' || ').join('('+v+')' for v in values) if emit else all(values) if op=='all' else any(values)
    if op not in ('eq','ne','ult','slt') or len(tree)!=3:raise ValueError('unsupported trap predicate')
    lhs,rhs=(word(value,ctx,xlen,emit,depth+1) for value in tree[1:])
    if emit:
        if op=='slt':lhs,rhs=f'$signed({lhs})',f'$signed({rhs})'
        return f'({lhs} '+{'eq':'==','ne':'!=','ult':'<','slt':'<'}[op]+f' {rhs})'
    if op=='slt':
        lhs=lhs-(1<<xlen) if lhs>>(xlen-1) else lhs
        rhs=rhs-(1<<xlen) if rhs>>(xlen-1) else rhs
    return lhs==rhs if op=='eq' else lhs!=rhs if op=='ne' else lhs<rhs


def contexts(states):
    return {'rs1':'a','rs2':'b','pc':'pc',**{'state.'+name:'state_'+name for name in states}}


def validate_semantics(row,states,xlen):
    for key in ('result','pc_after','state_updates','memory','trap'):
        if key not in row:raise ValueError('declare every result, PC, state, memory and trap effect')
    ctx=contexts(states);memory=row['memory'];trap=row['trap']
    if memory is not None:
        if memory.get('kind') not in ('load','store') or type(memory.get('size')) is not int or memory['size'] not in (1,2,4,8) or memory['size']>xlen//8:
            raise ValueError('declare one XLEN-bounded load or store')
        word(memory['address'],ctx,xlen,True)
        if memory['kind']=='store':word(memory['data'],ctx,xlen,True)
        else:ctx['mem_rdata']='mem_rdata'
        if trap is None:raise ValueError('memory effects require explicit fault trap semantics')
    word(row['result'],ctx,xlen,True);word(row['pc_after'],ctx,xlen,True)
    if not isinstance(row['state_updates'],dict) or set(row['state_updates'])-set(states):
        raise ValueError('state updates must name declared extra state')
    for value in row['state_updates'].values():word(value,ctx,xlen,True)
    if trap is not None:
        predicate(trap['when'],contexts(states),xlen,True)
        word(trap['cause'],ctx,xlen,True);word(trap['target'],ctx,xlen,True)
        if memory is not None:word(trap['memory_fault_cause'],ctx,xlen,True)
        updates=trap['state_updates']
        if not isinstance(updates,dict) or set(updates)-set(states):raise ValueError('trap updates must name declared state')
        for value in updates.values():word(value,{**ctx,'trap_cause':'cause'},xlen,True)


def load(path):
    data=json.loads(Path(path).read_text())
    if data.get('schema')!='rvw.custom-isa/2':raise ValueError('expected rvw.custom-isa/2')
    states=data['state'];xlen=data['xlen']
    if not isinstance(states,dict) or any(not re.fullmatch(r'[a-z][a-z0-9_]*',name) or type(width) is not int or not 1<=width<=xlen for name,width in states.items()):
        raise ValueError('extra state needs simple names and widths up to XLEN')
    from .custom_isa import validate
    shadow=copy.deepcopy(data);shadow['schema']='rvw.custom-isa/1'
    for row in shadow['instructions']:
        row.update(state=[],effects={'memory':'none','trap':'none','pc':'next'},result=0)
    validate(shadow)
    for row,base in zip(data['instructions'],shadow['instructions']):
        row.update(mask=base['mask'],match=base['match'])
        validate_semantics(row,states,xlen)
        for mutant in row.get('mutants',[]):
            if set(mutant['override'])-{'result','pc_after','state_updates','memory','trap'}:
                raise ValueError('effect mutants can override semantic fields only')
            changed=dict(row,**mutant['override']);validate_semantics(changed,states,xlen)
    return data


def transition(data,row,inputs):
    xlen=data['xlen'];mask=(1<<xlen)-1;states=data['state']
    for key in ('rs1','rs2','pc','mem_rdata'):
        if type(inputs[key]) is not int or not 0<=inputs[key]<=mask:raise ValueError('transition inputs must fit XLEN')
    if type(inputs['mem_fault']) is not bool or type(inputs['rd']) is not int or not 0<=inputs['rd']<32:
        raise ValueError('declare Boolean memory fault and rd 0..31')
    before=inputs['state']
    if set(before)!=set(states) or any(type(before[name]) is not int or not 0<=before[name]<1<<width for name,width in states.items()):
        raise ValueError('declare complete width-bounded pre-state')
    ctx={key:inputs[key] for key in ('rs1','rs2','pc','mem_rdata')}
    ctx.update({'state.'+name:value for name,value in before.items()})
    trap=row['trap'];memory=row['memory']
    pretrap=predicate(trap['when'],ctx,xlen) if trap else False
    attempt=memory is not None and not pretrap
    if inputs['mem_fault'] and not attempt:raise ValueError('memory fault without an attempted access')
    fault=attempt and inputs['mem_fault'];trapped=pretrap or fault
    cause=word(trap['memory_fault_cause'] if fault else trap['cause'],ctx,xlen) if trapped else 0
    ctx['trap_cause']=cause
    updates=trap['state_updates'] if trapped else row['state_updates']
    after={name:word(updates[name],ctx,xlen)&((1<<width)-1) if name in updates else before[name] for name,width in states.items()}
    access=None
    if attempt:
        value=word(memory['data'],ctx,xlen) if memory['kind']=='store' else inputs['mem_rdata']
        access=dict(kind=memory['kind'],address=word(memory['address'],ctx,xlen),size=memory['size'],
                    data=value&((1<<(8*memory['size']))-1),commit=not trapped)
    write=not trapped and inputs['rd']!=0
    return dict(result=word(row['result'],ctx,xlen) if write else 0,rd_write=write,
                pc_after=word(trap['target'] if trapped else row['pc_after'],ctx,xlen),
                trap=trapped,cause=cause,state=after,memory=access)


def rtl(data,row):
    xlen=data['xlen'];states=data['state'];ctx=contexts(states);ctx['mem_rdata']='mem_rdata'
    memory=row['memory'];trap=row['trap']
    ports=['input execute,mem_fault',f'input [{xlen-1}:0] a,b,pc,mem_rdata','input [31:0] insn']
    ports += [f'input [{width-1}:0] state_{name}' for name,width in states.items()]
    ports += ['output selected,trap,rd_write,mem_valid,mem_write,mem_commit',
              f'output [{xlen-1}:0] result,pc_after,cause,mem_addr,mem_data',f'output [{xlen//8-1}:0] mem_mask']
    ports += [f'output [{width-1}:0] next_{name}' for name,width in states.items()]
    lines=[f'module rvw_custom_{row["name"]}_effects('+',\n'.join(ports)+');',
           f"assign selected = execute && ((insn & 32'h{row['mask']:08x}) == 32'h{row['match']:08x});",
           'wire pretrap = '+(predicate(trap['when'],contexts(states),xlen,True) if trap else "1'b0")+';',
           "assign mem_valid = selected && !pretrap && "+("1'b1" if memory else "1'b0")+';',
           "wire fault = mem_valid && mem_fault;",
           'assign trap = selected && (pretrap || fault);',
           'assign rd_write = selected && !trap && (insn[11:7] != 0);',
           "assign mem_write = mem_valid && "+("1'b1" if memory and memory['kind']=='store' else "1'b0")+';',
           'assign mem_commit = mem_valid && !trap;']
    cause=word(trap['cause'],ctx,xlen,True) if trap else '0'
    faultcause=word(trap['memory_fault_cause'],ctx,xlen,True) if memory else '0'
    lines += [f'assign cause = trap ? (fault ? {faultcause} : {cause}) : 0;',
              f'assign result = rd_write ? {word(row["result"],ctx,xlen,True)} : 0;',
              f'assign pc_after = !selected ? pc : trap ? '+(word(trap['target'],ctx,xlen,True) if trap else 'pc')+f' : {word(row["pc_after"],ctx,xlen,True)};']
    for name in states:
        normal=word(row['state_updates'][name],ctx,xlen,True) if name in row['state_updates'] else 'state_'+name
        exceptional=word(trap['state_updates'][name],{**ctx,'trap_cause':'cause'},xlen,True) if trap and name in trap['state_updates'] else 'state_'+name
        lines += [f'assign next_{name} = !selected ? state_{name} : trap ? {exceptional} : {normal};']
    if memory:
        value=word(memory['data'],ctx,xlen,True) if memory['kind']=='store' else 'mem_rdata'
        lines += [f'assign mem_addr = mem_valid ? {word(memory["address"],contexts(states),xlen,True)} : 0;',
                  f"assign mem_data = mem_valid ? ({value} & {xlen}'h{(1<<(8*memory['size']))-1:x}) : 0;",
                  f"assign mem_mask = mem_valid ? {xlen//8}'h{(1<<memory['size'])-1:x} : 0;"]
    else:lines += ['assign mem_addr = 0; assign mem_data = 0; assign mem_mask = 0;']
    lines += ['always @* if(selected && mem_fault) assert(mem_valid);','endmodule']
    return '\n'.join(lines)+'\n'


def plan_cases(data,row):
    xlen=data['xlen'];values=[0,1,(1<<xlen)-1,1<<(xlen-1),(1<<(xlen-1))-1];cases=[]
    for ai,a in enumerate(values):
        for bi,b in enumerate(values):
            state={name:[0,1,(1<<width)-1,1<<(width-1),(1<<(width-1))-1][(ai+bi)%5] for name,width in data['state'].items()}
            inputs=dict(rs1=a,rs2=b,pc=4096,rd=3,mem_rdata=values[(ai+2*bi)%5],mem_fault=False,state=state)
            cases.append(dict(inputs=inputs,expected=transition(data,row,inputs),insn=encode(row,3,1,2),origin='generated'))
    ordinary=next((case for case in cases if not case['expected']['trap'] and case['expected']['result']!=0),None)
    ordinary=ordinary or next((case for case in cases if not case['expected']['trap']),cases[0])
    for rd in (0,1,2):
        inputs=copy.deepcopy(ordinary['inputs']);inputs['rd']=rd
        cases.append(dict(inputs=inputs,expected=transition(data,row,inputs),insn=encode(row,rd,1,2),origin='generated',scenario='destination alias or x0'))
    first=next((case for case in cases if case['expected']['memory'] is not None),None)
    if first:
        inputs=copy.deepcopy(first['inputs']);inputs['mem_fault']=True
        cases.append(dict(inputs=inputs,expected=transition(data,row,inputs),insn=first['insn'],origin='generated',scenario='memory fault'))
    cases += [dict(vector,origin='project-reference',insn=encode(row,vector['inputs']['rd'],1,2)) for vector in row.get('reference_vectors',[])]
    return cases


def generate(manifest,out):
    data=load(manifest);out=Path(out).resolve();out.mkdir(parents=True,exist_ok=False)
    checks=[];gaps=[]
    for row in data['instructions']:
        (out/(row['name']+'.sv')).write_text(rtl(data,row))
        vectors=row.get('reference_vectors',[])
        if not vectors:gaps.append(row['name']+': independent reference vectors missing')
        for index,vector in enumerate(vectors):
            actual=transition(data,row,vector['inputs'])
            checks.append(dict(instruction=row['name'],kind='reference',index=index,
                               status='consistent' if actual==vector['expected'] else 'mismatch',actual=actual,expected=vector['expected']))
        if not row.get('mutants'):gaps.append(row['name']+': independent effect mutants missing')
        for mutant in row.get('mutants',[]):
            changed=dict(row,**mutant['override'])
            killed=any(transition(data,changed,vector['inputs'])!=vector['expected'] for vector in vectors)
            checks.append(dict(instruction=row['name'],kind='mutant',id=mutant['id'],status='detected' if killed else 'survived'))
            if not killed:gaps.append(row['name']+': surviving effect mutant '+mutant['id'])
    plan=dict(schema='rvw.custom-effects-plan/1',instructions={row['name']:plan_cases(data,row) for row in data['instructions']},
              limits=['Generated expected values share the declared model.', 'Project hooks must set and observe extra state. No DUT execution is implied.'])
    (out/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    (out/'interface.json').write_text(json.dumps(data,indent=2)+'\n')
    files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()}
    result=dict(schema='rvw.custom-effects-generation/1',status='mismatch' if any(row['status']=='mismatch' for row in checks) else 'generated',
                manifest_sha256=hashlib.sha256(Path(manifest).read_bytes()).hexdigest(),
                generator_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),Path(__file__).with_name('custom_isa.py'))},files=files,checks=checks,gaps=gaps,
                limits=['One completed instruction transition and one load or store. No AMO or bus handshake model.',
                        'All extra-state updates read pre-state and commit together. Traps suppress normal writes.',
                        'The generated RTL and interpreter share declared semantics. Vectors and mutants need author independence.',
                        'No actual DUT binding, backend integration, ISA proof or qualification is implied.'])
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');return result


def main(args):
    try:
        result=generate(args.manifest,args.out)
        print(json.dumps(result) if args.json else result['status'])
        return 1 if result['status']=='mismatch' else 0
    except (ValueError,OSError,KeyError,TypeError) as exc:
        print(json.dumps(dict(status='error',error=str(exc))));return 2
