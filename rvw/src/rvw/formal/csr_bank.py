"""Explicit shared CSR storage, static alias views and privilege sequences.

This model does not infer conditional AIA aliases or dynamic legalization.
"""
import json
import re
from pathlib import Path

MODES={'U':0,'S':1,'M':3}
OPS=('read','write','read_write','set','clear')
IDENT=re.compile(r'[A-Za-z_][A-Za-z0-9_]*')


def load(path):
    obj=json.loads(Path(path).read_text())
    if obj.get('schema')!='rvw.csr-bank/1' or obj.get('xlen') not in (32,64):
        raise ValueError('expected rvw.csr-bank/1 with XLEN 32 or 64')
    if set(obj)-{'schema','xlen','banks','views','sequences','modes','setup','binding'}:
        raise ValueError('unsupported CSR bank model attribute')
    modes=obj.get('modes',['M'])
    if not modes or 'M' not in modes or set(modes)-set(MODES):
        raise ValueError('declare supported M/S/U modes')
    if set(obj.get('setup',[]))-{'enable_fpu','open_pmp'}:
        raise ValueError('unsupported sequence setup')
    banks={}
    for b in obj['banks']:
        if set(b)!={'name','width','reset'} or not IDENT.fullmatch(b['name']) or b['name'] in banks:
            raise ValueError('invalid or duplicate storage bank')
        if type(b['width']) is not int or not 1<=b['width']<=64 or type(b['reset']) is not int or not 0<=b['reset']<1<<b['width']:
            raise ValueError('invalid bank width/reset')
        banks[b['name']]=b
    if not banks: raise ValueError('declare shared storage')
    views={};addresses=set()
    for v in obj['views']:
        if set(v)-{'name','bank','address','catalog','privilege','shift','mask','write_mask','read_only','present'}:
            raise ValueError('unsupported view semantics; use a richer model')
        if not IDENT.fullmatch(v['name']) or v['name'] in views or v['bank'] not in banks:
            raise ValueError('invalid or duplicate CSR view')
        if 'catalog' in v:
            from .csr_catalog import catalog
            definition=catalog()['registers'][v['catalog']]['definition']
            if definition.get('requires_environment_model') or definition['priv_mode'] not in MODES:
                raise ValueError('CSR requires an interrupt/hypervisor environment')
            if 'address' in v and v['address']!=definition['address']:
                raise ValueError('catalog address mismatch')
            v.update(address=definition['address'],privilege=definition['priv_mode'])
        address=v['address'];shift=v.get('shift',0);mask=v['mask'];writes=v['write_mask']
        if type(address) is not int or not 0<=address<4096 or address in addresses or v['privilege'] not in MODES:
            raise ValueError('invalid CSR address/privilege')
        if (address>>8)&3==2: raise ValueError('hypervisor views require an execution model')
        if type(shift) is not int or shift<0 or type(mask) is not int or not 0<mask<1<<obj['xlen'] or mask<<shift >= 1<<banks[v['bank']]['width']:
            raise ValueError('alias projection exceeds storage or XLEN')
        if type(writes) is not int or writes<0 or writes&~mask:
            raise ValueError('write mask must be a subset of the view mask')
        if any(type(v[k]) is not bool for k in ('present','read_only') if k in v):
            raise ValueError('view flags must be boolean')
        addresses.add(address);views[v['name']]=v
    if not views: raise ValueError('declare CSR views')
    names=set()
    for seq in obj.get('sequences',[]):
        if not IDENT.fullmatch(seq['name']) or seq['name'] in names or not seq['accesses']:
            raise ValueError('sequences require unique names and accesses')
        names.add(seq['name'])
        for access in seq['accesses']:
            if set(access)-{'view','op','data','privilege'} or access['view'] not in views or access['op'] not in OPS:
                raise ValueError('unsupported sequence operation')
            if access.get('privilege','M') not in modes:
                raise ValueError('sequence uses an undeclared privilege mode')
            value=access.get('data',0)
            if type(value) is not int or not 0<=value<1<<obj['xlen']:
                raise ValueError('sequence data exceeds XLEN')
    if obj.get('sequences'):
        touched={0x100,0x300,0x305,0x341,0x342}
        if any(a.get('privilege','M')!='M' for seq in obj['sequences'] for a in seq['accesses']): touched.add(0x302)
        if 'open_pmp' in obj.get('setup',[]): touched.update((0x3a0,0x3b0))
        if addresses & touched:
            raise ValueError('sequence setup/trap-control CSRs need a custom execution harness')
    return obj


def step(obj,state,access):
    v=next(v for v in obj['views'] if v['name']==access['view'])
    before=(state[v['bank']]>>v.get('shift',0))&v['mask']
    op=access['op'];data=access.get('data',0)
    write=op in ('write','read_write') or op in ('set','clear') and data!=0
    denied=(not v.get('present',True) or MODES[access.get('privilege','M')]<MODES[v['privilege']] or
            write and (v.get('read_only',False) or v['address']>>10==3))
    after=dict(state)
    if write and not denied:
        value=before|data if op=='set' else before&~data if op=='clear' else data
        shift=v.get('shift',0);mask=v['write_mask']<<shift
        after[v['bank']]=(state[v['bank']]&~mask)|((value<<shift)&mask)
    return dict(trap=bool(denied),rdata=before,state=after)


def monitor(obj):
    w=obj['xlen'];banks=obj['banks']
    ports=['input clk, reset, valid, rd, wr','input [1:0] privilege','input [11:0] address',
           f'input [{w-1}:0] data, rdata','input trap']
    for b in banks:
        ports.append(f'input [{b["width"]-1}:0] state_{b["name"]}, hw_set_{b["name"]}, hw_clear_{b["name"]}')
    lines=['module rvw_csr_bank('+', '.join(ports)+');','reg initialized=0;',
           'always @(posedge clk) begin if(!initialized) assume(reset); initialized<=1; end']
    for b in banks:
        lines.append(f'reg [{b["width"]-1}:0] expected_{b["name"]}, next_{b["name"]};')
    for v in obj['views']:
        n=v['name'];shift=v.get('shift',0);b=v['bank']
        lines += [f'wire [{w-1}:0] view_{n} = (expected_{b} >> {shift}) & {w}\'d{v["mask"]};',
                  f'wire denied_{n} = {int(not v.get("present",True))} || privilege==2 || privilege<2\'d{MODES[v["privilege"]]} || (wr && {int(v.get("read_only",False) or v["address"]>>10==3)});']
    lines.append('always @* begin')
    for b in banks: lines.append(f' next_{b["name"]}=expected_{b["name"]};')
    for v in obj['views']:
        b=next(b for b in banks if b['name']==v['bank']);n=b['name'];width=b['width']
        shift=v.get('shift',0);mask=v['write_mask']<<shift
        lines.append(f" if(valid && wr && address==12'd{v['address']} && !denied_{v['name']}) next_{n}=(expected_{n} & ~{width}'d{mask}) | (({{64'd0,data}} << {shift}) & {width}'d{mask});")
    lines+=['end','always @(posedge clk) begin',' if(reset) begin']
    for b in banks: lines.append(f' expected_{b["name"]}<={b["width"]}\'d{b["reset"]};')
    lines+=[' end else begin']
    for b in banks:
        n=b['name'];lines += [f' if(initialized) assert(state_{n}==expected_{n});',
                              f' expected_{n}<=(next_{n} & ~hw_clear_{n}) | hw_set_{n};']
    for v in obj['views']:
        n=v['name'];lines += [f' if(valid && address==12\'d{v["address"]}) begin',
            f'  assert(trap==denied_{n});',f'  if(rd && !denied_{n}) assert(rdata==view_{n});',' end']
    return '\n'.join(lines+[' end','end','endmodule',''])


def assembly(obj,seq):
    lines=['.option norvc','.section .text.init','.globl _start','_start:',
           'la t0, handler','csrw mtvec, t0','li s3, 0','li s1, 0']
    if 'enable_fpu' in obj.get('setup',[]): lines+=['li t0, 0x6000','csrs mstatus, t0']
    if 'open_pmp' in obj.get('setup',[]): lines+=['li t0, -1','csrw pmpaddr0, t0','li t0, 0x1f','csrw pmpcfg0, t0']
    if any(a.get('privilege','M')!='M' for a in seq['accesses']):
        lines+=['csrw medeleg, zero']
    state={b['name']:b['reset'] for b in obj['banks']}
    for index,access in enumerate(seq['accesses']):
        v=next(v for v in obj['views'] if v['name']==access['view']);addr=hex(v['address'])
        result=step(obj,state,access);mode=access.get('privilege','M')
        lines+=['li s0, 0',f'li s1, {int(result["trap"])}','li s2, 0']
        if mode!='M':
            lines+=['li t0, 0x1800','csrc mstatus, t0',f'li t0, {MODES[mode]<<11}',
                    'csrs mstatus, t0',f'la t0, action_{index}','csrw mepc, t0','mret',f'action_{index}:']
        op=access['op'];value=access.get('data',0)
        lines += [f'li t0, {value}']
        instruction={'read':f'csrr s2, {addr}','write':f'csrw {addr}, t0',
                     'read_write':f'csrrw s2, {addr}, t0','set':f'csrrs s2, {addr}, t0','clear':f'csrrc s2, {addr}, t0'}[op]
        lines += [instruction,f'li t0, {int(result["trap"])}','bne s0, t0, fail']
        if op!='write' and not result['trap']:
            lines += [f'li t0, {result["rdata"]}','bne s2, t0, fail']
        if mode!='M':
            lines+=['li s3, 1',f'la s4, return_{index}',f'li s5, {8 if mode=="U" else 9}','ecall',f'return_{index}:']
        state=result['state']
    lines+=['li t0, 1','j finish','fail:','li t0, 3','finish:','la t1, tohost','sw t0, 0(t1)',
        '1: j 1b','.balign 4','handler:','bnez s3, return_to_machine','beqz s1, fail',
        'csrr t0, mcause','li t1, 2','bne t0, t1, fail','addi s0, s0, 1',
        'csrr t0, mepc','addi t0, t0, 4','csrw mepc, t0','mret','return_to_machine:',
        'csrr t0, mcause','bne t0, s5, fail','li s3, 0','csrw mepc, s4',
        'li t0, 0x1800','csrs mstatus, t0','mret','.section .tohost,"aw",@progbits','.balign 8',
        '.globl tohost','tohost: .dword 0','.globl fromhost','fromhost: .dword 0','']
    return '\n'.join(lines)


def generate(path,out):
    obj=load(path);programs={s['name']:assembly(obj,s) for s in obj.get('sequences',[])}
    source=monitor(obj)
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    (out/'csr.sv').write_text(source)
    (out/'model.json').write_text(json.dumps(obj,indent=2)+'\n')
    from .csr import write_binding
    write_binding(path,obj,out)
    groups=[dict(name=v['name'],fields=['csr','csr_access','mode'],
                 when={'class':'csr','csr':f"0x{v['address']:03x}"},
                 domains=[[f"0x{v['address']:03x}"],['read','write','read_write'],obj.get('modes',['M'])]) for v in obj['views']]
    (out/'coverage.json').write_text(json.dumps(dict(groups=groups),indent=2)+'\n')
    for name,program in programs.items(): (out/(name+'.S')).write_text(program)
    result=dict(schema='rvw.csr-generation/1',status='generated',csrs=len(obj['views']),
                banks=len(obj['banks']),sequences=list(programs),limitations=[
                    'Project-declared static aliases and masks only; no conditional AIA aliases or WARL interpretation.',
                    'Bind canonical DUT storage and independent hardware set/clear events for every bank.',
                    'Bank resets and supported privilege modes are project declarations.',
                    'Dynamic state-enable controls and FP-disabled access rules are not modeled; the harness must establish those conditions.',
                    'No compiler, solver, Spike or DUT execution was run.'])
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
