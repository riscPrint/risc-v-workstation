"""Project digital DVFS sequencing. No analog voltage or PLL claim."""
from .programs import HEAD, TAIL


def transitions(config):
    data=config['dvfs'];states=data['states'];sequence=data['sequence']
    if len(sequence)<2 or any(s not in states for s in sequence):raise ValueError('DVFS needs a declared state sequence')
    for state in states.values():
        if any(type(state[k]) is not int or state[k]<=0 for k in ('frequency_hz','voltage_uv')):
            raise ValueError('DVFS frequency and voltage must be positive integers')
    return [(a,b) for a,b in zip(sequence,sequence[1:])]


def programs(config):
    pairs=transitions(config)
    code=HEAD+' li s0, 0x12345\n li s1, 0\n'
    events=[]
    for step,(old,new) in enumerate(pairs,1):
        events.append(dict(step=step,kind='dvfs',source=old,target=new))
        code+=f''' la t0, stimulus_step
 li t1, {step}
 sd t1, 0(t0)
 la t0, stimulus_ack
1: ld t1, 0(t0)
 li t2, {step}
 bne t1, t2, 1b
 li t0, 0x12345
 bne s0, t0, fail
 addi s1, s1, 1
'''
    code+=f' li t0, {len(pairs)}\n bne s1, t0, fail\n j pass\n'+TAIL+'''.section .data
.balign 8
.globl stimulus_step, stimulus_ack
stimulus_step: .dword 0
stimulus_ack: .dword 0
'''
    return [dict(id='dvfs-sequence',family='dvfs',assembly=code,events=events,
                 bins=[f'dvfs.{a}.{b}' for a,b in pairs],dvfs_contract=config['dvfs'],
                 reference_model=dict(kind='dvfs',contract=config['dvfs']))]


def plan(contract):
    pairs=transitions({'dvfs':contract});rows=[]
    for index,(old,new) in enumerate(pairs,1):
        up=contract['states'][new]['frequency_hz']>contract['states'][old]['frequency_hz']
        phases=['requested','voltage_ready','clock_changed','acknowledged'] if up else ['requested','clock_changed','voltage_ready','acknowledged']
        rows.append(dict(step=index,source=old,target=new,phases=phases))
    return rows


def observe(contract,samples):
    expected=plan(contract)
    if not samples:return dict(status='inconclusive',reason='missing DVFS samples')
    if any(a['tick']>=b['tick'] for a,b in zip(samples,samples[1:])):raise ValueError('DVFS sample ticks must increase')
    unknown=False
    for transition in expected:
        group=[s for s in samples if s.get('step')==transition['step']]
        if [s.get('phase') for s in group]!=transition['phases']:
            return dict(status='inconclusive' if len(group)<4 else 'fail',reason='missing or reordered DVFS handshake phases')
        target=contract['states'][transition['target']]
        source=contract['states'][transition['source']]
        if group[0].get('frequency_hz') is not None and group[0]['frequency_hz'] != source['frequency_hz']:
            return dict(status='fail',reason='request did not start in the declared source state')
        for sample in group:
            if any(sample.get(k) is None for k in ('frequency_hz','voltage_uv','clock_ready','voltage_ready')):
                unknown=True;continue
            frequency,voltage=sample['frequency_hz'],sample['voltage_uv']
            if frequency not in (source['frequency_hz'],target['frequency_hz']):
                return dict(status='fail',reason='undeclared clock frequency')
            needed=target['voltage_uv'] if frequency==target['frequency_hz'] else source['voltage_uv']
            if voltage<needed:return dict(status='fail',reason='clock exceeds declared voltage-state limit')
            if sample['phase']=='acknowledged' and (frequency!=target['frequency_hz'] or voltage!=target['voltage_uv'] or not sample['clock_ready'] or not sample['voltage_ready']):
                return dict(status='fail',reason='acknowledged before target state ready')
        for phase in ('voltage_ready','clock_changed'):
            sample=next(s for s in group if s['phase']==phase)
            field='voltage_uv' if phase=='voltage_ready' else 'frequency_hz'
            ready='voltage_ready' if phase=='voltage_ready' else 'clock_ready'
            if sample.get(field)!=target[field] or sample.get(ready) is not True:
                if sample.get(field) is None or sample.get(ready) is None:unknown=True
                else:return dict(status='fail',reason='phase completed without target readiness')
    if {s.get('step') for s in samples} != {r['step'] for r in expected}:
        return dict(status='fail',reason='unexpected transition step')
    return dict(status='inconclusive' if unknown else 'pass',reason='digital sequence checked; no analog qualification')


def reference(scenario):
    return dict(id=scenario['id'],status='pass',evidence='model-based',
                scope='expected digital sequence only; no DUT observation',transitions=plan(scenario['reference_model']['contract']))
