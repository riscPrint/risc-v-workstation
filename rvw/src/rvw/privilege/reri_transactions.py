"""RERI v1.0 status write protection, read races and CE counter programs."""
from .programs import HEAD,TAIL
from .reri import Record,VERSION,REVISION,RDIP,COUNTER,CECO
from .events import mailbox


def apply(model,action):
    value=int(action['value'],0)
    if action['kind']=='control':model.write_control(value)
    elif action['kind']=='status':model.write_status(value)
    elif action['kind']=='error':model.log(value)
    else:raise ValueError('unknown RERI transaction')


def programs(config):
    data=config['reri'];base=data['base']
    if config.get('spec_version')!=VERSION:raise ValueError('unsupported RERI version')
    if base<0 or base%8:raise ValueError('RERI base must be eight-byte aligned')
    if data.get('logging_writable') is not True or 'ce' not in data.get('classes',[]):
        raise ValueError('RERI transactions require writable logging enable and CE reporting')
    counter_bits=data.get('ce_counter_bits',0)
    if counter_bits not in (0,16):raise ValueError('this counter profile supports declared 16-bit CE counters')
    cases={
        'valid-write-protection':(0,1,[('error',2),('status',0)]),
        'read-invalidate-race':(0,1,[('error',2),('control',1|(1<<49)),('error',2),
                                  ('control',1|(1<<48)),('control',1|(1<<49)),('control',1|(1<<48))]),
        'logging-disabled':(0,0,[('error',2),('control',1),('error',2),('control',0),('error',2)]),
    }
    if counter_bits:
        cases.update({
            'counter-increment':(0,7,[('error',2),('error',2)]),
            'counter-overflow':(0xfffe<<48,7,[('error',2),('error',2)]),
            'counter-disabled':(7<<48,5,[('error',2),('error',2)]),
            'counter-toggle':(7<<48,5,[('error',2),('control',7),('error',2),('control',5),('error',2)]),
        })
    mask=1|0xe|64|RDIP|(3<<4)|(COUNTER|CECO if counter_bits else 0)
    rows=[]
    for name,(seed,control,actions) in cases.items():
        all_actions=[('control',(1<<48)|(1<<49)),('status',seed),('control',control)]+actions
        all_actions+=[('control',control|(1<<48)|(1<<49))]
        code=HEAD;model=Record();events=[];plan=[];expected=[]
        for index,(kind,value) in enumerate(all_actions):
            action=dict(kind=kind,value=hex(value),observe=index>0);apply(model,action);plan.append(action)
            if kind=='error':
                step=len(events)+1
                events.append(dict(step=step,kind='reri-error',record=0,status=value))
                code+=mailbox(step)
            else:
                address=base+(64 if kind=='control' else 72)
                code+=f' li a0, {address}\n li a1, {value}\n sd a1, 0(a0)\n fence iorw, iorw\n'
            if not action['observe']:continue
            status=model.status&mask;expected.append(hex(status))
            code+=f''' li a0, {base+72}
 ld t0, 0(a0)
 li t1, {mask}
 and t0, t0, t1
 li t1, {status}
 bne t0, t1, fail
'''
        code+=' j pass\n'+TAIL+'''.section .data
.balign 8
.globl stimulus_step, stimulus_ack
stimulus_step: .dword 0
stimulus_ack: .dword 0
'''
        rows.append(dict(id='reri-transactions-'+name,family='reri',assembly=code,
            events=events,bins=['reri.transactions.'+name],spec_version=VERSION,
            spec='https://github.com/riscv-non-isa/riscv-ras-eri/tree/'+REVISION,
            reference_model=dict(kind='reri-transactions',base=base,actions=plan,mask=hex(mask),expected=expected)))
    return rows


def reference(scenario):
    plan=scenario['reference_model'];m=Record();actual=[]
    for action in plan['actions']:
        apply(m,action)
        if action.get('observe',True):actual.append(hex(m.status&int(plan['mask'],0)))
    return dict(id=scenario['id'],status='pass' if actual==plan['expected'] else 'fail',
                evidence='model-based',actual=actual,expected=plan['expected'],signals=m.signals)


class Device:
    """One explicit full-capability record used after program initialization."""
    def __init__(self,base,status=0):self.base=base;self.record=Record(status=status)
    def read(self,address,size):
        if size!=8:raise ValueError('RERI reference needs 64-bit accesses')
        if address==self.base+64:return self.record.control
        if address==self.base+72:return self.record.status
        raise ValueError('unsupported RERI register')
    def write(self,address,value,size):
        if size!=8:raise ValueError('RERI reference needs 64-bit accesses')
        if address==self.base+64:self.record.write_control(value)
        elif address==self.base+72:self.record.write_status(value)
        else:raise ValueError('unsupported RERI register')
    def event(self,event):
        if event['kind']!='reri-error' or event['record']!=0:raise ValueError('unsupported RERI hardware event')
        self.record.log(event['status'])
