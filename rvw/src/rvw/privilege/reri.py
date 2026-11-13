"""RERI 1.0 model and logging/recovery campaigns. No reset value is assumed."""
from .programs import HEAD, TAIL

VERSION='RERI-v1.0'
REVISION='12eef3f549fe54f817185b1e084b85537f442999'
COUNTER=((1<<16)-1)<<48
STICKY=0xe
RDIP=1<<23
CECO=1<<21


def severity(status):
    return 3 if status&8 else 2 if status&4 else 1 if status&2 else 0


class Record:
    def __init__(self, *, status=0, control=0):
        self.status=status;self.control=control;self.info={};self.signals=[]

    def write_status(self,value):
        if not self.status&1:self.status=value&((1<<64)-1)

    def write_control(self,value):
        if value&(1<<49):self.status|=RDIP
        if value&(1<<48) and self.status&RDIP:self.status&=~1
        self.control=value&~((1<<48)|(1<<49))

    def log(self,new_status,**info):
        if not self.control&1:return
        old=self.status;old_sev=severity(old);new_sev=severity(new_status)
        overflow=False
        if new_sev==1 and self.control&2:
            count=((old>>48)+1)&0xffff
            overflow=count==0
            self.status=(self.status&~COUNTER)|(count<<48)
            if overflow:self.status|=CECO
        valid=bool(old&1)
        overwrite=not valid or new_sev>old_sev or (new_sev==old_sev and ((new_status>>4)&3)>((old>>4)&3))
        if valid:
            self.status&=~RDIP
            if new_sev>old_sev:self.status&=~64
            elif new_sev==old_sev:self.status|=64
            self.status|=new_status&STICKY
        else:
            self.status=(self.status&~(STICKY|64))|RDIP
            self.status|=(1<<new_sev) if new_sev else 0
        if overwrite:
            retained=COUNTER|CECO|RDIP|STICKY|64
            self.status=(self.status&retained)|(new_status&~retained)|1
            self.info=dict(info)
        signal=(self.control>>{0:2,1:2,2:4,3:6}[new_sev])&3
        if signal and ((overwrite and not (new_sev==1 and self.control&2)) or overflow):
            self.signals.append(dict(severity=new_sev,signal=signal))


def programs(config):
    if config.get('spec_version')!=VERSION:raise ValueError('unsupported RERI version')
    base=config['reri']['base']
    if base < 0 or base%8:raise ValueError('RERI bank must be eight-byte aligned')
    rows=[]
    cases={'ce':[2], 'ued':[4], 'uec':[8], 'severity':[2,4,8],
           'same-priority':[2,2], 'higher-priority':[2,2|(3<<4)], 'lower-severity':[8,2]}
    if not config['reri'].get('priority_supported',False):cases.pop('higher-priority')
    control=config['reri'].get('control',1)
    classes=set(config['reri'].get('classes',['ce','ued','uec']))
    for name,events in cases.items():
        if any({1:'ce',2:'ued',3:'uec'}[severity(s)] not in classes for s in events):continue
        m=Record(control=control)
        code=HEAD+f''' li a0, {base+64}
 li t0, {(1<<48)|(1<<49)}
 sd t0, 0(a0)
 li a1, {base+72}
 sd zero, 0(a1)
 li t0, {control}
 sd t0, 0(a0)
'''
        stimulus=[];observations=[]
        for step,status in enumerate(events,1):
            m.log(status)
            mask=1|STICKY|64|RDIP|(3<<4)
            expected=m.status&mask
            code+=f''' la t0, stimulus_step
 li t1, {step}
 sd t1, 0(t0)
 la t0, stimulus_ack
1: ld t1, 0(t0)
 li t2, {step}
 bne t1, t2, 1b
 li a1, {base+72}
 ld t0, 0(a1)
 li t1, {mask}
 and t0, t0, t1
 li t1, {expected}
 bne t0, t1, fail
'''
            stimulus.append(dict(step=step,kind='reri-error',record=0,status=status))
            observations.append(expected)
        code+=f''' li a0, {base+64}
 li t0, {(1<<48)|(1<<49)|control}
 sd t0, 0(a0)
 li a1, {base+72}
 ld t0, 0(a1)
 andi t0, t0, 1
 bnez t0, fail
 j pass
'''+TAIL+'''.section .data
.balign 8
.globl stimulus_step, stimulus_ack
stimulus_step: .dword 0
stimulus_ack: .dword 0
'''
        routes=config['reri'].get('irq_routes',{})
        route=routes.get(str(m.signals[0]['signal'])) if m.signals else None
        if route is not None:
            if type(route) is not int or not 0 <= route < 64:raise ValueError('invalid project RAS interrupt cause')
            start='reri_event_start:\n'
            enable=f' la s5, reri_irq_handler\n csrw mtvec, s5\n li s4, 0\n li s5, {1<<route}\n csrw mie, s5\n csrsi mstatus, 8\n'
            code=code.replace(' la t0, stimulus_step',enable+start+' la t0, stimulus_step',1)
            recovery=f' li a0, {base+64}\n li t0, {(1<<48)|(1<<49)|control}'
            wait=' li s5, 1000\n3: bnez s4, 4f\n addi s5, s5, -1\n bnez s5, 3b\n j fail\n4:\nreri_event_end:\n'
            code=code.replace(recovery,wait+recovery,1)
            handler=f'reri_irq_handler:\n csrr s5, mcause\n li s6, {(1<<63)|route}\n bne s5, s6, fail\n csrr s5, mepc\n la s6, reri_event_start\n bltu s5, s6, fail\n la s6, reri_event_end\n bgeu s5, s6, fail\n li s5, {base+72}\n ld s6, 0(s5)\n andi s6, s6, 1\n beqz s6, fail\n li s4, 1\n csrw mie, zero\n mret\n'
            code=code.replace('fail:\n',handler+'fail:\n',1)
        rows.append(dict(id='reri-'+name,family='reri',assembly=code,bins=['reri.'+name],events=stimulus,
            reference_model=dict(kind='reri',events=events,expected=observations,control=control),
            spec='https://github.com/riscv-non-isa/riscv-ras-eri/tree/'+REVISION,
            reri_signals=list(m.signals)))
    return rows


def reference(scenario):
    plan=scenario['reference_model'];m=Record(control=plan['control']);actual=[]
    for status in plan['events']:
        m.log(status);actual.append(m.status&(1|STICKY|64|RDIP|(3<<4)))
    return dict(id=scenario['id'],status='pass' if actual==plan['expected'] else 'fail',
                evidence='model-based',actual=actual,expected=plan['expected'],signals=m.signals)
