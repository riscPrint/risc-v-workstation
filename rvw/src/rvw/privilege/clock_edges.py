"""Digital clock measurements on independent reference-clock ticks."""
from fractions import Fraction
from .dvfs import plan,observe as observe_handshake


def validate(settings):
    reference=settings['reference_hz']
    tolerance=settings.get('period_tolerance_ticks',0);settle=settings.get('settle_ticks',0)
    for name,value,minimum in [('reference_hz',reference,1),('period_tolerance_ticks',tolerance,0),
                               ('settle_ticks',settle,0),('min_high_ticks',settings['min_high_ticks'],1),
                               ('min_low_ticks',settings['min_low_ticks'],1)]:
        if type(value) is not int or value<minimum:raise ValueError('invalid clock measure '+name)
    for name in ('max_switch_ticks','max_edge_gap_ticks'):
        if name in settings and (type(settings[name]) is not int or settings[name]<1):
            raise ValueError('invalid clock measure '+name)
    return reference,tolerance,settle


def observe(contract,samples,capture):
    settings=contract['clock_measure'];reference,tolerance,settle=validate(settings)
    if not capture or capture.get('complete') is not True:
        return dict(status='inconclusive',reason='need complete independent clock edge capture')
    if capture.get('reference_hz')!=reference:
        return dict(status='inconclusive',reason='clock capture reference frequency differs')
    gate=observe_handshake(contract,samples)
    if gate['status']!='pass':return gate
    start,end=capture.get('start_tick'),capture.get('end_tick');edges=capture.get('edges',[])
    if type(start) is not int or type(end) is not int or end<=start:
        return dict(status='inconclusive',reason='missing clock observation interval')
    if any(type(e.get('tick')) is not int or type(e.get('level')) is not bool for e in edges):
        return dict(status='inconclusive',reason='unknown clock edge')
    if any(e['tick']<start or e['tick']>end for e in edges):raise ValueError('clock edge outside capture interval')
    if any(a['tick']>=b['tick'] for a,b in zip(edges,edges[1:])):raise ValueError('clock edge ticks must increase')
    for a,b in zip(edges,edges[1:]):
        if a['level']==b['level']:return dict(status='inconclusive',reason='missing intervening clock transition')
        width=b['tick']-a['tick'];bound=settings['min_high_ticks' if a['level'] else 'min_low_ticks']
        if width<bound:return dict(status='fail',reason='sampled clock pulse is too short',tick=a['tick'],width_ticks=width)
        if settings.get('max_edge_gap_ticks') is not None and width>settings['max_edge_gap_ticks']:
            return dict(status='fail',reason='clock edge gap exceeds project bound',tick=a['tick'],width_ticks=width)
    transitions=plan(contract);windows=[];previous=start;state=contract['sequence'][0]
    for transition in transitions:
        group=[s for s in samples if s['step']==transition['step']]
        request=group[0]['tick'];ack=group[-1]['tick']
        if request<previous or ack>end:return dict(status='inconclusive',reason='clock capture does not cover stable windows')
        if settings.get('max_switch_ticks') is not None and ack-request>settings['max_switch_ticks']:
            return dict(status='fail',reason='clock switch acknowledgement exceeds project bound',step=transition['step'])
        windows.append((state,previous,request));previous=ack+settle;state=transition['target']
    windows.append((state,previous,end));results=[];unknown=False
    for state,a,b in windows:
        period=Fraction(reference,contract['states'][state]['frequency_hz'])
        if b-a<3*period:
            unknown=True;results.append(dict(state=state,status='inconclusive',reason='short stable clock window'));continue
        rising=[e['tick'] for e in edges if e['level'] and a<=e['tick']<=b]
        if len(rising)<3:
            return dict(status='fail',reason='missing clock edges in a complete stable window',state=state)
        if rising[0]-a>period+tolerance or b-rising[-1]>period+tolerance:
            return dict(status='fail',reason='clock gap at a stable window boundary',state=state)
        periods=[y-x for x,y in zip(rising,rising[1:])]
        if any(abs(p-period)>tolerance for p in periods):
            return dict(status='fail',reason='measured clock period differs from selected state',state=state,periods=periods)
        results.append(dict(state=state,status='pass',period_ticks=str(period),observed_periods=len(periods)))
    return dict(status='inconclusive' if unknown else 'pass',windows=results,
                reason='sampled digital clock periods and pulse bounds checked; no analog or PLL qualification')


class EdgeRecorder:
    """Sample once per independent reference tick; never sample on the core clock."""
    def __init__(self,reference_hz):
        if type(reference_hz) is not int or reference_hz<=0:raise ValueError('reference_hz must be positive')
        self.reference_hz=reference_hz;self.start=None;self.last=None;self.level=None
        self.edges=[];self.complete=True

    def sample(self,tick,level):
        if type(tick) is not int or (self.last is not None and tick<=self.last):
            raise ValueError('reference sample ticks must increase')
        if self.start is None:self.start=tick
        if self.last is not None and tick!=self.last+1:self.complete=False
        self.last=tick
        if type(level) is not bool:self.complete=False;self.level=None;return
        if self.level is not None and level!=self.level:self.edges.append(dict(tick=tick,level=level))
        self.level=level

    def capture(self):
        return dict(reference_hz=self.reference_hz,complete=self.complete and self.start is not None,
                    start_tick=self.start,end_tick=self.last,edges=list(self.edges))
