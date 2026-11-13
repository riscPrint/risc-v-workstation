"""Wake inputs gated by actual WFI and independent clock-stop observations."""
from copy import deepcopy
from .programs import HEAD, TAIL

VERSION='privileged-20260120'


class StopWakeDriver:
    """Call service once per independent tick. Close in the adapter's finally block."""
    def __init__(self,event,symbols):
        self.event=deepcopy(event);self.pc=symbols['wfi_site'];self.samples=[]
        self.asserted=None;self.cleared=None;self.stopped_since=None;self.contiguous=True
        self.resumed=False;self.complete=False;self.input_applied=False

    def service(self,request,drive,acknowledge,*,tick,snapshot):
        if type(tick) is not int or self.samples and tick<=self.samples[-1]['tick']:
            raise ValueError('reference ticks must increase')
        if self.samples and tick!=self.samples[-1]['tick']+1:self.contiguous=False
        sample=deepcopy(snapshot);sample['tick']=tick;self.samples.append(sample)
        if self.asserted is None:
            eligible=(request==self.event['step'] and sample.get('wfi_active') is True
                      and sample.get('clock_running') is False and sample.get('pending') is False
                      and sample.get('wfi_pc')==self.pc)
            if not eligible:self.stopped_since=None;return False
            if self.stopped_since is None:self.stopped_since=tick
            if tick-self.stopped_since<self.event['min_stop_ticks']:return False
            self.asserted=tick
            drive(dict(kind='irq',source=self.event['source'],cause=self.event['cause'],asserted=True))
            self.input_applied=True
            return True
        if sample.get('clock_running') is True:self.resumed=True
        if self.cleared is None and self.resumed and request==self.event['completion_step'] and tick-self.asserted>=self.event['pulse_ticks']:
            drive(dict(kind='irq',source=self.event['source'],cause=self.event['cause'],asserted=False))
            self.cleared=tick
            acknowledge(self.event['completion_step'])
        paused=[s for s in self.samples if s.get('clock_running') is False]
        base=paused[0].get('retired') if paused else None
        self.complete=(self.cleared is not None and type(base) is int
                       and type(sample.get('retired')) is int and sample['retired']>base)
        return False

    def close(self,drive):
        if self.asserted is not None and self.cleared is None:
            drive(dict(kind='irq',source=self.event['source'],cause=self.event['cause'],asserted=False))

    def capture(self):
        return dict(event=deepcopy(self.event),complete=self.contiguous and bool(self.samples),input_applied=self.input_applied,
                    asserted_tick=self.asserted,cleared_tick=self.cleared,samples=deepcopy(self.samples))


def observe(event,capture,wfi_pc):
    if not capture or capture.get('complete') is not True or capture.get('event')!=event or capture.get('input_applied') is not True:
        return dict(status='inconclusive',reason='missing complete WFI stop input capture')
    samples=capture.get('samples',[]);asserted=capture.get('asserted_tick');cleared=capture.get('cleared_tick')
    if not samples or type(asserted) is not int:
        return dict(status='inconclusive',reason='wake input was not gated by an observed WFI stop')
    ticks=[s.get('tick') for s in samples]
    if any(type(t) is not int for t in ticks) or any(b!=a+1 for a,b in zip(ticks,ticks[1:])):
        return dict(status='inconclusive',reason='missing independent reference samples')
    if any(type(s.get('clock_running')) is not bool for s in samples):
        return dict(status='inconclusive',reason='unknown core clock state')
    before=[s for s in samples if s['tick']<=asserted]
    paused=[]
    for s in reversed(before):
        if s.get('clock_running') is not False:break
        paused.append(s)
    paused.reverse()
    if not paused or paused[-1]['tick']!=asserted or asserted-paused[0]['tick']<event['min_stop_ticks']:
        return dict(status='fail',reason='wake input preceded the required observed stop phase')
    if paused[0] is samples[0] or samples[samples.index(paused[0])-1].get('clock_running') is not True:
        return dict(status='inconclusive',reason='need running state before WFI stop')
    if any(type(s.get('wfi_active')) is not bool or type(s.get('wfi_pc')) is not int or type(s.get('pending')) is not bool for s in paused):
        return dict(status='inconclusive',reason='missing bound WFI phase samples')
    if any(s.get('wfi_active') is not True or s.get('wfi_pc')!=wfi_pc or s.get('pending') is not False for s in paused):
        return dict(status='fail',reason='wake input was not asserted in the clean bound WFI phase')
    after=[s for s in samples if s['tick']>asserted]
    resumed=next((s for s in after if s.get('clock_running') is True),None)
    if resumed is None:
        return dict(status='fail' if ticks[-1]-asserted>event['max_wake_ticks'] else 'inconclusive',reason='no clock restart in the captured wake interval')
    if resumed['tick']-asserted>event['max_wake_ticks']:
        return dict(status='fail',reason='clock restart exceeded the project wake bound')
    if not any(s.get('pending') is True for s in after if s['tick']<=resumed['tick']):
        return dict(status='inconclusive',reason='missing pending input at restart')
    if type(cleared) is not int or cleared-asserted<event['pulse_ticks'] or cleared<resumed['tick'] or cleared>ticks[-1]:
        return dict(status='inconclusive',reason='missing wake-input release after restart and minimum pulse')
    stopped=[s for s in samples if paused[0]['tick']<=s['tick']<resumed['tick']]
    baseline=paused[0]
    for s in stopped:
        if s.get('clock_running') is not False:return dict(status='fail',reason='clock restarted before wake assertion')
        if type(s.get('retired')) is not int or type(baseline.get('retired')) is not int:
            return dict(status='inconclusive',reason='missing stopped retirement count')
        if s['retired']!=baseline['retired']:return dict(status='fail',reason='retirement during stopped clock')
    for name,mask in event['state_masks'].items():
        value=baseline.get('state',{}).get(name)
        for s in [samples[samples.index(baseline)-1],*stopped,*[v for v in after if v['tick']>=resumed['tick']]]:
            current=s.get('state',{}).get(name)
            if type(value) is not int or type(current) is not int:return dict(status='inconclusive',reason='missing retained state '+name)
            if (value^current)&mask:return dict(status='fail',reason='retained state changed: '+name)
    if not any(type(s.get('retired')) is int and s['retired']>baseline['retired'] for s in after if s['tick']>=resumed['tick']):
        return dict(status='inconclusive',reason='missing resumed retirement')
    return dict(status='pass',reason='observed WFI stop, gated input, retention and restart checked',wake_ticks=resumed['tick']-asserted)


def programs(config):
    if config.get('spec_version')!=VERSION or not config['isa'].startswith('rv64'):
        raise ValueError('WFI stop requires RV64 privileged-20260120')
    settings=config['wake'];masks=settings['state_masks'];sources=settings['sources']
    if not masks or any(type(v) is not int or v<=0 for v in masks.values()):raise ValueError('positive retained state masks required')
    for name in ('min_stop_ticks','pulse_ticks','max_wake_ticks'):
        if type(settings[name]) is not int or settings[name]<1:raise ValueError('positive independent tick bounds required')
    if not sources or len({s['cause'] for s in sources})!=len(sources):raise ValueError('distinct wake causes required')
    rows=[]
    for source in sources:
        cause=source['cause']
        if type(cause) is not int or cause not in (1,3,5,7,9,11) and not 16<=cause<=63 or not source['source']:
            raise ValueError('wake cause must be standard or project interrupt 16..63')
        for enabled in (0,1):
            event=dict(step=1,completion_step=2,kind='wfi-wake',source=source['source'],cause=cause,
                       **{k:settings[k] for k in ('min_stop_ticks','pulse_ticks','max_wake_ticks','state_masks')})
            code=HEAD+f''' la t0, handler
 csrw mtvec, t0
 li s0, 0x12345
 li t0, {1<<cause}
 csrw mie, t0
 {'csrsi' if enabled else 'csrci'} mstatus, 8
 la t0, stimulus_step
 li t1, 1
 sd t1, 0(t0)
 fence rw, rw
wfi_site:
 wfi
wfi_after:
'''
            code+=(' j fail\n' if enabled else f'''wait_pending:
 csrr t0, mip
 li t1, {1<<cause}
 and t0, t0, t1
 beqz t0, wait_pending
pending_read:
 csrr a0, mip
 j check_state
''')
            code+=f'''handler:
trap_cause_read:
 csrr a0, mcause
 li t0, {(1<<63)|cause}
 bne a0, t0, fail
trap_pc_read:
 csrr a0, mepc
 la t0, wfi_after
 bne a0, t0, fail
 {'j check_state' if enabled else 'j fail'}
check_state:
retention_read:
 addi a0, s0, 0
 li t0, 0x12345
 bne a0, t0, fail
 csrw mie, zero
 csrci mstatus, 8
 la t0, stimulus_step
 li t1, 2
 sd t1, 0(t0)
 fence rw, rw
 la t0, stimulus_ack
wait_release:
 ld t1, 0(t0)
 li t2, 2
 bne t1, t2, wait_release
 j pass
'''+TAIL+'''.section .data
.balign 8
.globl stimulus_step, stimulus_ack, wfi_site
stimulus_step: .dword 0
stimulus_ack: .dword 0
'''
            plan=dict(kind='wfi-stop',cause=cause,enabled=enabled,expected=dict(trap=bool(enabled),pending_mask=hex(1<<cause),retained='0x12345'))
            rows.append(dict(id=f'wfi-stop-{cause}-{enabled}',assembly=code,family='wfi',bins=[f'wfi.stopped.{cause}.{enabled}'],
                spec_version=VERSION,spec='https://docs.riscv.org/reference/isa/v20260120/priv/machine.html',events=[event],wfi_stop_contract=event,
                reference_mode='model-observations',reference_model=plan,model_bindings=observation_bindings(plan)))
    return rows


def reference(scenario):
    p=scenario['reference_model'];actual=dict(trap=bool(p['enabled']),pending_mask=hex(1<<p['cause']),retained='0x12345')
    valid=p['enabled'] in (0,1) and (p['cause'] in (1,3,5,7,9,11) or 16<=p['cause']<=63)
    return dict(id=scenario['id'],status='pass' if valid and actual==p['expected'] else 'fail',evidence='model-based',actual=actual,
                scope='one enabled local wake input with global MIE off/on; no native clock or DUT execution')


def observation_bindings(plan):
    result=[dict(symbol='retention_read',kind='writeback',insn='0x40513',expected=['0x12345'])]
    if plan['enabled']:
        result.extend([dict(symbol='trap_cause_read',kind='csr',csr='0x342',expected=[hex((1<<63)|plan['cause'])]),
                       dict(symbol='trap_pc_read',kind='csr',csr='0x341',expected=[dict(symbol='wfi_after')])])
    else:result.append(dict(symbol='pending_read',kind='csr',csr='0x344',mask=hex(1<<plan['cause']),expected=[hex(1<<plan['cause'])]))
    return result
