"""v0.20 Smijt jump-table entry and common-dispatch fallback."""
from .programs import HEAD,TAIL
from .events import mailbox
from .controllers import FAST
from .fast_runtime import validate,setup,baseline


def resolve(base,shift,major,minor,entry,common,ialign):
    offset=minor if minor is not None else -major
    address=(base+(offset<<(shift+2)))&((1<<64)-1)
    target=(entry&~(ialign//8-1)) if entry&1 else common&~3
    return address,target


def programs(config):
    options=validate(config);rows=[]
    if 'smijt' not in config['isa'].split('_'):raise ValueError('vector profile requires Smijt')
    base=options['ijt_base'];handler=options['handler_address'];common=options['common_address']
    if any(type(a) is not int or a<0 or a%64 for a in (base,handler,common)):
        raise ValueError('IJT and handler addresses must be nonnegative and 64-byte aligned')
    if base<1024 or len({base,handler,common})!=3:raise ValueError('distinct IJT/handler regions are required')
    compressed='c' in config['isa'].split('_')[0][4:] or 'zca' in config['isa'].split('_');ialign=16 if compressed else 32
    shifts=options.get('table_shifts',[1,2])
    if not shifts or len(set(shifts))!=len(shifts) or any(s not in (1,2,3) for s in shifts):
        raise ValueError('RV64 table_shifts must select 1, 2 or 3')
    for major,minor in ((3,None),(7,None),(11,1)):
        for shift in shifts:
            for low in (0,1,3):
                entry=handler|low;address,target=resolve(base,shift,major,minor,entry,common,ialign)
                cause=(1<<63)|minor if minor is not None else (-major)&((1<<64)-1)
                raw=base|(shift<<2)
                code=HEAD+mailbox(1)+setup(8)+f''' li t0, {raw}
 csrw 0x307, t0
 csrr t1, 0x307
 bne t0, t1, fail
 li a0, {address}
 li t0, {entry}
 sd t0, 0(a0)
 fence iorw, iorw
 li t0, {common|3}
 csrw mtvec, t0
 csrr t1, mtvec
 bne t0, t1, fail
 li t0, {1<<major}
 csrw mie, t0
 li s0, 0x12345
 csrsi mstatus, 8
 la t0, stimulus_step
 li t1, 2
 sd t1, 0(t0)
vector_wait:
 j vector_wait
validation:
vector_cause_read:
 csrr t0, mcause
 li t1, {cause}
 bne t0, t1, fail
vector_mepc_read:
 csrr t0, mepc
 la t1, vector_wait
 bne t0, t1, fail
 csrr t0, 0x347
'''
                # External priority was programmed to 0x48. Major default priorities
                # are implementation-selected AIA values, so do not invent one here.
                if minor is not None:code+=' li t1, 72\n bne t0, t1, fail\n'
                code+=f'''vector_previous_read:
 csrr t0, 0x346
 srli t0, t0, 8
 andi t0, t0, 511
 li t1, 256
 bne t0, t1, fail
 li t0, 0x12345
 bne s0, t0, fail
'''+mailbox(3)+''' csrw mie, zero
 csrci mstatus, 8
 j pass
'''+TAIL+'''.section .data
.balign 8
.globl stimulus_step,stimulus_ack
stimulus_step: .dword 0
stimulus_ack: .dword 0
.section .jump_table,"aw"
.space 2048
.section .fast_common,"ax"
.balign 64
common_handler:
'''
                code+=(' j validation\n' if low==0 else ' j fail\n')
                code+=' .section .fast_handler,"ax"\n'
                if compressed and low==3:code+=' .hword 0x9002\n'
                code+='vector_handler:\n'+(' j fail\n' if low==0 else ' j validation\n')
                name=f'fast-vector-{major}-{shift}-{low}'
                events=[baseline(),dict(step=2,kind='fast-source',major=major,minor=minor,level=True,when_pc='vector_wait'),
                        dict(step=3,kind='fast-source',major=major,minor=minor,level=False)]
                bindings=observation_bindings(dict(major=major,minor=minor))
                rows.append(dict(id=name,reference_mode='model-observations',model_bindings=bindings,model_required_pcs=[hex(target)],family='smijt',assembly=code,bins=[f'{name}.ialign{ialign}'],events=events,
                    spec_version=FAST,link_options=[f'-Wl,--section-start=.jump_table={base-1024:#x}',
                        f'-Wl,--section-start=.fast_handler={handler:#x}',f'-Wl,--section-start=.fast_common={common:#x}'],
                    reference_model=dict(kind='fast-vector',base=hex(base),shift=shift,major=major,minor=minor,
                        entry=hex(entry),common=hex(common),ialign=ialign,address=hex(address),target=hex(target)),
                    reference_unavailable='Spike has no v0.20 Smijt interrupt-jump-table model'))
    return rows


def reference(scenario):
    p=scenario['reference_model']
    address,target=resolve(int(p['base'],0),p['shift'],p['major'],p['minor'],int(p['entry'],0),int(p['common'],0),p['ialign'])
    actual=dict(address=hex(address),target=hex(target))
    expected=dict(address=p['address'],target=p['target'])
    return dict(id=scenario['id'],status='pass' if actual==expected else 'fail',evidence='model-based',actual=actual,expected=expected)


def observation_bindings(plan):
    major,minor=plan['major'],plan['minor']
    cause=(1<<63)|minor if minor is not None else (-major)&((1<<64)-1)
    return [dict(symbol='vector_cause_read',kind='csr',csr='0x342',expected=[hex(cause)]),
            dict(symbol='vector_mepc_read',kind='csr',csr='0x341',expected=[{'symbol':'vector_wait'}]),
            dict(symbol='vector_previous_read',kind='csr',csr='0x346',mask='0x1ff00',expected=['0x10000'])]


def observation_pcs(plan):
    _,target=resolve(int(plan['base'],0),plan['shift'],plan['major'],plan['minor'],
                     int(plan['entry'],0),int(plan['common'],0),plan['ialign'])
    return [hex(target)]
