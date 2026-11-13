"""ACLIC v0.20 real nested entry, grouping and software frame restoration."""
from .programs import HEAD,TAIL
from .events import mailbox
from .controllers import NestedPriority,FAST
from .fast_runtime import validate,setup,baseline


def programs(config):
    options=validate(config);rows=[]
    groups=options.get('group_bits',[0,4,8])
    if not groups or len(set(groups))!=len(groups) or any(type(g) is not int or not 0<=g<=8 for g in groups):
        raise ValueError('group_bits must select distinct implemented counts in 0..8')
    for group in groups:
        for inner in (0x20,0x40,0x48,0x50):
            model=NestedPriority(8,group);model.trap(0x48);preempts=model.eligible(inner)
            code=HEAD+mailbox(1)+setup(group,0x48,inner)+''' la t0, irq_handler
 csrw mtvec, t0
 li s0, 0
 li s1, 0x12345
 li s2, 0
 csrsi mstatus, 8
 la t0, stimulus_step
 li t1, 2
 sd t1, 0(t0)
main_wait:
 li t0, 2
 bne s0, t0, main_wait
 li t0, 1
 bne s2, t0, main_wait
main_done:
 csrw mie, zero
 csrci mstatus, 8
final_threshold_read:
 csrr t0, 0x347
 li t1, 256
 bne t0, t1, fail
 li t0, 0x12345
 bne s1, t0, fail
final_top_read:
 csrr t0, 0x348
 bnez t0, fail
 j pass
irq_handler:
irq_status_read:
 csrr t0, mstatus
 andi t0, t0, 136
 li t1, 128
 bne t0, t1, fail
irq_cause_read:
 csrr t0, mcause
 li t1, 0x8000000000000001
 beq t0, t1, outer_handler
 li t1, 0x8000000000000002
 bne t0, t1, fail
inner_handler:
 li t0, '''+str(1 if preempts else 2)+f'''
 bne s0, t0, fail
 bnez s2, fail
inner_threshold_read:
 csrr t0, 0x347
 li t1, {inner}
 bne t0, t1, fail
inner_previous_read:
 csrr t0, 0x346
 srli t0, t0, 8
 andi t0, t0, 511
 li t1, {0x48 if preempts else 256}
 bne t0, t1, fail
 li s2, 1
 mret
outer_handler:
 bnez s0, fail
 li s0, 1
outer_previous_read:
 csrr s4, 0x346
 csrr s6, mepc
 la t0, main_wait
 bltu s6, t0, fail
 la t0, main_done
 bgeu s6, t0, fail
outer_threshold_read:
 csrr t0, 0x347
 li t1, 72
 bne t0, t1, fail
 srli t0, s4, 8
 andi t0, t0, 511
 li t1, 256
 bne t0, t1, fail
'''+mailbox(3)+''' li a0, 10000
inner_pending_wait:
 csrr t0, 0x35c
 srli t0, t0, 16
 li t1, 2
 beq t0, t1, inner_pending_seen
 addi a0, a0, -1
 bnez a0, inner_pending_wait
 j fail
inner_pending_seen:
 csrsi mstatus, 8
'''
            if preempts:
                code+=' li a0, 10000\nnested_wait:\n bnez s2, nested_done\n addi a0, a0, -1\n bnez a0, nested_wait\n j fail\nnested_done:\n'
            else:
                code+=' li a0, 64\nnonpreempt_wait:\n addi a0, a0, -1\n bnez a0, nonpreempt_wait\n bnez s2, fail\n'
            code+=''' csrci mstatus, 8
 csrr t0, 0x347
 li t1, 72
 bne t0, t1, fail
 csrw 0x346, s4
 csrw mepc, s6
 li s0, 2
 mret
'''+TAIL+'''.section .data
.balign 8
.globl stimulus_step,stimulus_ack
stimulus_step: .dword 0
stimulus_ack: .dword 0
'''
            name=f'fast-preemption-{group}-{inner}'
            events=[baseline(),dict(step=2,kind='aclic-edge',source=1,when_pc='main_wait'),dict(step=3,kind='aclic-edge',source=2)]
            bindings=observation_bindings(dict(group=group,inner=inner))
            rows.append(dict(id=name,reference_mode='model-observations',model_bindings=bindings,family='smnip',assembly=code,events=events,bins=[name],spec_version=FAST,
                             reference_model=dict(kind='fast-preemption',group=group,inner=inner,preempts=preempts),
                             reference_unavailable='Spike has no v0.20 ACLIC/Smnip entry model'))
    return rows


def reference(scenario):
    p=scenario['reference_model'];m=NestedPriority(8,p['group']);m.trap(0x48);saved=m.previous
    eligible=m.eligible(p['inner'])
    if eligible:m.trap(p['inner']);m.ret()
    restored=m.threshold==0x48
    m.restore_previous(saved);m.ret()
    return dict(id=scenario['id'],status='pass' if eligible==p['preempts'] and restored and m.threshold==256 else 'fail',
                evidence='model-based',preempts=eligible,outer_threshold_restored=restored,final_threshold=m.threshold)


def observation_bindings(plan):
    inner=plan['inner'];m=NestedPriority(8,plan['group']);m.trap(0x48);preempts=m.eligible(inner)
    bindings=[dict(symbol='final_threshold_read',kind='csr',csr='0x347',expected=['0x100']),
        dict(symbol='final_top_read',kind='csr',csr='0x348',expected=['0x0']),
        dict(symbol='irq_status_read',kind='csr',csr='0x300',mask='0x88',expected=['0x80','0x80']),
        dict(symbol='irq_cause_read',kind='csr',csr='0x342',expected=['0x8000000000000001','0x8000000000000002']),
        dict(symbol='inner_threshold_read',kind='csr',csr='0x347',expected=[hex(inner)]),
        dict(symbol='inner_previous_read',kind='csr',csr='0x346',mask='0x1ff00',expected=[hex((0x48 if preempts else 256)<<8)]),
        dict(symbol='outer_previous_read',kind='csr',csr='0x346',mask='0x1ff00',expected=['0x10000']),
        dict(symbol='outer_threshold_read',kind='csr',csr='0x347',expected=['0x48'])]
    return bindings
