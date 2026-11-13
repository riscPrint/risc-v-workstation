"""Reset only after the project observes a prepared in-flight operation."""
from .programs import HEAD, TAIL


class PhaseDriver:
    """Callbacks perform real project actions. Ticks come from a reference clock."""
    def __init__(self,events):
        self.events=list(events);self.done=[];self.receipts=[];self.prepared=None
        steps=[e['step'] for e in events]
        if steps!=sorted(set(steps)) or any(type(s) is not int or s<=0 for s in steps):
            raise ValueError('mailbox steps must be positive and strictly increasing')
        for event in events:
            if not event.get('phase_gate') or not event.get('prepare'):
                raise ValueError('phased reset needs preparation and independent state gates')

    @property
    def complete(self):return len(self.done)==len(self.events)

    def service(self,request,drive,acknowledge,*,tick,state):
        if self.complete:return False
        event=self.events[len(self.done)]
        if request!=event['step']:return False
        if self.prepared is None:
            try:
                drive(dict(kind='reset-prepare',actions=event['prepare'],step=request))
            except Exception:
                drive(dict(kind='reset-cleanup',actions=event.get('cleanup',[]),step=request))
                raise
            self.prepared=tick
            return False
        if tick-self.prepared<event.get('min_wait_ticks',1):return False
        if any(name not in state or state[name]&spec['mask']!=spec['value']&spec['mask']
               for name,spec in event['phase_gate'].items()):return False
        prepared=self.prepared;observed=dict(state)
        try:
            drive(event)
        finally:
            drive(dict(kind='reset-cleanup',actions=event.get('cleanup',[]),step=request))
            self.prepared=None
        acknowledge(request)
        self.done.append(event)
        self.receipts.append(dict(step=request,prepared_tick=prepared,reset_tick=tick,
                                  state=observed,complete=True))
        return True


def observe(events,receipts):
    if not events or len(events)!=len(receipts):return dict(status='inconclusive',reason='missing phased reset observations')
    previous=-1
    for event,receipt in zip(events,receipts):
        if receipt.get('complete') is not True:return dict(status='inconclusive',reason='incomplete reset phase')
        prepared=receipt.get('prepared_tick');tick=receipt.get('reset_tick')
        if type(prepared) is not int or type(tick) is not int:
            return dict(status='inconclusive',reason='missing independent phase ticks')
        if receipt.get('step')!=event['step'] or prepared<=previous or tick-prepared<event.get('min_wait_ticks',1):
            return dict(status='fail',reason='reset phase order or wait differs')
        for name,spec in event['phase_gate'].items():
            value=receipt.get('state',{}).get(name)
            if value is None:return dict(status='inconclusive',reason='missing in-flight state observation')
            if value&spec['mask']!=spec['value']&spec['mask']:
                return dict(status='fail',reason='reset occurred outside the declared in-flight phase')
        previous=tick
    return dict(status='pass',reason='all declared in-flight reset phases observed')


def programs(config):
    contract=config['reset'];count=contract['pulses']
    if type(count) is not int or not 1<=count<=16:raise ValueError('reset pulses must be in 1..16')
    if not contract.get('state') or not contract.get('invalid_outputs'):
        raise ValueError('reset needs state and output validity contracts')
    rows=[]
    for phase in contract['phases']:
        name=phase['name']
        if name not in ('fetch','load','store','trap','debug'):
            raise ValueError('unsupported reset phase')
        if not phase.get('prepare') or not phase.get('state') or phase.get('min_wait_ticks',1)<1:
            raise ValueError('reset phase needs preparation, independent state and a wait')
        if any(type(s['mask']) is not int or s['mask']<=0 for s in phase['state'].values()):
            raise ValueError('reset phase masks must be positive')
        for kind in contract.get('kinds',['cold','warm','local']):
            if kind not in ('cold','warm','local'):raise ValueError('invalid reset kind')
            code=HEAD+f''' la t0, handler
 csrw mtvec, t0
 la t0, restart_count
 ld t1, 0(t0)
 li t2, {count}
 beq t1, t2, pass
 bgtu t1, t2, fail
 addi t1, t1, 1
 sd t1, 0(t0)
 fence rw, rw
 la t0, stimulus_step
 sd t1, 0(t0)
 la a0, probe_data
phase_site:
'''
            code+=dict(fetch=' j phase_site\n',load=' ld a1, 0(a0)\n j phase_site\n',
                       store=' sd t1, 0(a0)\n j phase_site\n',trap=' ecall\n j fail\n',debug=' j phase_site\n')[name]
            code+='''handler:
 csrr t0, mcause
 li t1, 11
 bne t0, t1, fail
trap_wait:
 j trap_wait
'''+TAIL+'''.section .data
.balign 8
.globl restart_count, stimulus_step, stimulus_ack, phase_site, trap_wait
restart_count: .dword 0
stimulus_step: .dword 0
stimulus_ack: .dword 0
probe_data: .dword 0
'''
            events=[dict(step=i,kind='reset',reset_kind=kind,preserve_ram=True,
                         phase=name,prepare=phase['prepare'],cleanup=phase.get('cleanup',[]),
                         phase_gate=phase['state'],min_wait_ticks=phase.get('min_wait_ticks',1)) for i in range(1,count+1)]
            rows.append(dict(id=f'reset-{kind}-inflight-{name}',assembly=code,family='reset',
                             bins=[f'reset.{kind}.{name}',f'reset.repeated.{name}'] if count>1 else [f'reset.{kind}.{name}'],
                             events=events,reset_contract=contract,reset_phase_contract=events,
                             reference_unavailable='Spike CLI cannot drive project reset pulses or in-flight device phases'))
    if not rows:raise ValueError('reset campaign has no declared phases')
    return rows
