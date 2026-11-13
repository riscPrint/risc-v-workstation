"""Independent sampled timer checks. No synchronized architectural time reads."""
MASK=(1<<64)-1


def integer(value):
    return int(value,0) if isinstance(value,str) else value if type(value) is int else None


def check(contract,samples):
    if not samples:return dict(status='inconclusive',reason='missing independent timer samples')
    if any(a['tick']>=b['tick'] for a,b in zip(samples,samples[1:])):
        raise ValueError('timer reference ticks must increase')
    latency=contract.get('latency_ticks')
    if latency is not None and (type(latency) is not int or latency<0):raise ValueError('timer latency must be nonnegative')
    if any(s.get('phase') not in contract['phases'] for s in samples):
        raise ValueError('unknown timer phase')
    order=contract.get('order',list(contract['phases']))
    seen_order=[]
    for sample in samples:
        if not seen_order or sample['phase']!=seen_order[-1]:seen_order.append(sample['phase'])
    if seen_order!=order:
        return dict(status='fail' if set(seen_order)==set(order) else 'inconclusive',reason='missing or reordered timer phases')
    unknown=False;rows=[]
    for phase,expected in contract['phases'].items():
        group=[s for s in samples if s['phase']==phase]
        if not group:unknown=True;continue
        start=group[0].get('phase_start')
        if start is None or start>group[0]['tick']:
            unknown=True;continue
        if any(s.get('phase_start')!=start for s in group):raise ValueError('timer phase boundaries differ')
        if any(b['tick']!=a['tick']+1 for a,b in zip(group,group[1:])):unknown=True
        previous=None;deadline=None if latency is None else start+latency;witness=False
        for sample in group:
            time=integer(sample.get('reference_time'));actual=sample.get('pending')
            if type(time) is not int or not 0<=time<=MASK or type(actual) is not bool:
                unknown=True;continue
            if time>integer(contract.get('max_reference_time',MASK)):
                unknown=True;continue
            wanted=((time+integer(expected.get('delta',0)))&MASK)>=integer(expected['compare'])
            if previous is not None and wanted!=previous:
                deadline=None if latency is None else sample['tick']+latency;witness=False
            previous=wanted
            if actual==wanted and (deadline is None or sample['tick']<=deadline):witness=True
            elif actual!=wanted and deadline is not None and sample['tick']>=deadline:
                return dict(status='fail',reason='pending state differs after declared latency',phase=phase,tick=sample['tick'])
        if not witness:unknown=True
        rows.append(dict(phase=phase,witness=witness))
    return dict(status='inconclusive' if unknown else 'pass',phases=rows,
                latency_ticks=latency, scope='sampled timer consistency against declared phase boundaries and independent time')
