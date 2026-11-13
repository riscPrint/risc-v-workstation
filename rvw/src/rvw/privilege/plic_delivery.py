"""Machine/supervisor PLIC interrupt delivery with masked input phases."""
from .programs import HEAD,TAIL
from .disabled import enter
from rvw.cosim.devices import Plic,PlicMap


def mailbox(step):
    return f''' la t0, stimulus_step
 li t1, {step}
 sd t1, 0(t0)
 la t0, stimulus_ack
1: ld t1, 0(t0)
 li t2, {step}
 bne t1, t2, 1b
'''


def programs(config):
    layout=PlicMap(**config['plic']);options=config['plic_delivery'];rows=[]
    if not config.get('isa','rv64im_zicsr_zifencei').startswith('rv64'):
        raise ValueError('PLIC delivery requires RV64')
    if type(options.get('settle_ticks',4)) is not int or options.get('settle_ticks',4)<1:
        raise ValueError('PLIC settling time must be a positive integer')
    if layout.sources<1 or layout.max_priority<3:raise ValueError('PLIC delivery needs a source and priority 3')
    for target in options['targets']:
        mode=target['mode'];context=target['context']
        if mode not in ('M','S') or not 0<=context<layout.contexts:raise ValueError('invalid PLIC delivery target')
        cause=11 if mode=='M' else 9;prefix='m' if mode=='M' else 's'
        bit=1<<cause;global_bit=8 if mode=='M' else 2
        status_mask=0x1888 if mode=='M' else 0x122;status_value=0x1880 if mode=='M' else 0x120
        claim=layout.context+context*layout.context_stride+4
        threshold=claim-4;enable=layout.enable+context*layout.enable_stride
        for masked in ('global','local','threshold'):
            code=HEAD+''' la t0, machine_handler
 csrw mtvec, t0
 li s0, 0
 li s1, 0x12345
'''+mailbox(1)+f''' li t0, {layout.priority+4}
 li t1, 3
 sw t1, 0(t0)
 li t0, {enable}
 li t1, 2
 sw t1, 0(t0)
 li t0, {threshold}
 sw zero, 0(t0)
 li t0, {claim}
 lw t1, 0(t0)
 beqz t1, drained
 sw t1, 0(t0)
drained:
 li t0, {threshold}
 li t1, {3 if masked=='threshold' else 0}
 sw t1, 0(t0)
 fence iorw, iorw
'''
            if mode=='S':code+=f' li t0, {bit}\n csrs mideleg, t0\n la t0, irq_handler\n csrw stvec, t0\n'
            else:code+=' la t0, irq_handler\n csrw mtvec, t0\n'
            code+=enter(mode)+f'''access_site:
 li t0, {bit if masked!='local' else 0}
 csrw {prefix}ie, t0
 {'csrci' if masked=='global' else 'csrsi'} {prefix}status, {global_bit}
delivery_start:
'''+mailbox(2)+f''' bnez s0, fail
 li a0, {layout.pending}
 li a1, 10000
pending_wait:
 lw t0, 0(a0)
 andi t0, t0, 2
 bnez t0, pending_seen
 addi a1, a1, -1
 bnez a1, pending_wait
 j fail
pending_seen:
'''
            # Context delivery can have a project latency. A bounded poll checks asserted pending.
            if masked!='threshold':
                code+=f''' li a1, 10000
irq_pending_wait:
 csrr t0, {prefix}ip
 li t1, {bit}
 and t0, t0, t1
 bnez t0, irq_pending_seen
 addi a1, a1, -1
 bnez a1, irq_pending_wait
 j fail
irq_pending_seen:
'''
            else:code+=f' csrr t0, {prefix}ip\n li t1, {bit}\n and t0, t0, t1\n bnez t0, fail\n'
            if masked=='global':code+=f' csrsi {prefix}status, {global_bit}\n'
            elif masked=='local':code+=f' li t0, {bit}\n csrs {prefix}ie, t0\n'
            else:code+=f' li t0, {threshold}\n sw zero, 0(t0)\n fence iorw, iorw\n'
            code+=f''' li a1, 10000
delivery_wait:
 bnez s0, delivered
 addi a1, a1, -1
 bnez a1, delivery_wait
 j fail
delivered:
delivery_end:
 li t0, 0x12345
 bne s1, t0, fail
 li t0, {claim}
 lw t1, 0(t0)
 bnez t1, fail
'''
            code+=' j pass\n' if mode=='M' else 'finish_ecall:\n ecall\n j fail\n'
            code+=f'''irq_handler:
 csrr t0, {prefix}cause
 li t1, {(1<<63)|cause}
 bne t0, t1, fail
 csrr t0, {prefix}epc
 la t1, delivery_start
 bltu t0, t1, fail
 la t1, delivery_end
 bgeu t0, t1, fail
 csrr t0, {prefix}status
 li t1, {status_mask}
 and t0, t0, t1
 li t1, {status_value}
 bne t0, t1, fail
 bnez s0, fail
 li t0, {claim}
 lw t1, 0(t0)
 li t2, 1
 bne t1, t2, fail
'''+mailbox(3)+f''' li t0, {claim}
 li t1, 1
 sw t1, 0(t0)
 fence iorw, iorw
 csrw {prefix}ie, zero
 li s0, 1
 {prefix}ret
machine_handler:
'''
            if mode=='S':code+=' csrr t0, mcause\n li t1, 9\n bne t0, t1, fail\n csrr t0, mepc\n la t1, finish_ecall\n bne t0, t1, fail\n j pass\n'
            else:code+=' j fail\n'
            code+=TAIL+'''.section .data
.balign 8
.globl stimulus_step, stimulus_ack
stimulus_step: .dword 0
stimulus_ack: .dword 0
'''
            events=[dict(step=step,kind='plic-level',source=1,level=level,settle_ticks=options.get('settle_ticks',4))
                    for step,level in ((1,False),(2,True),(3,False))]
            rows.append(dict(id=f'plic-delivery-{mode.lower()}-{context}-{masked}',family='plic',assembly=code,
                bins=[f'plic.delivery.{mode}.{masked}'],events=events,
                reference_model=dict(kind='plic-delivery',layout=config['plic'],context=context,masked=masked)))
    if not rows:raise ValueError('PLIC delivery needs a project target')
    return rows


def reference(scenario):
    plan=scenario['reference_model'];m=Plic(PlicMap(**plan['layout']));c=plan['context'];layout=m.map
    m.write(layout.priority+4,3);m.write(layout.enable+c*layout.enable_stride,2)
    m.write(layout.context+c*layout.context_stride,3 if plan['masked']=='threshold' else 0)
    m.set_level(1,True);actual=[m.irq(c)]
    m.write(layout.context+c*layout.context_stride,0);actual.append(m.irq(c))
    claim=layout.context+c*layout.context_stride+4
    actual.append(m.read(claim));m.set_level(1,False);m.write(claim,1)
    actual.extend([m.irq(c),m.read(claim)])
    expected=[plan['masked']!='threshold',True,1,False,0]
    return dict(id=scenario['id'],status='pass' if actual==expected else 'fail',evidence='model-based',
                actual=actual,expected=expected,scope='PLIC controller expectations; CPU delivery requires program execution')
