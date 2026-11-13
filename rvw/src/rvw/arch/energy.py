"""Abstract system energy from workload counts and declared state residency."""
from hashlib import sha256
import json
import math
from pathlib import Path
from .ledger import store


def number(value):
    if type(value) not in (int,float) or not math.isfinite(value) or value<0:
        raise ValueError('energy values must be finite and nonnegative')
    return value


def energy(plan,out):
    p=Path(plan).resolve();spec=json.loads(p.read_text())
    if spec.get('schema')!='rvw.system-energy-plan/1':raise ValueError('expected system energy plan')
    rp=p.parent/spec['run'];run=json.loads(rp.read_text())
    if run.get('schema')!='rvw.ooo-run/1' or type(run.get('cycles')) is not int or run['cycles']<1:
        raise ValueError('positive-cycle own-model run required')
    freq=number(spec['clock_ghz'])
    if not freq:raise ValueError('clock must be positive')
    duration=run['cycles']/freq;rows=[]
    for name,c in spec['components'].items():
        if c['kind'] not in ('cpu','cache','memory','interconnect') or not c.get('source'):
            raise ValueError('component requires a system kind and source')
        states=c['state_cycles'];power=c['state_mw']
        if not states or set(states)!=set(power) or any(type(v) is not int or v<0 for v in states.values()) or sum(states.values())!=run['cycles']:
            raise ValueError('state cycles must partition the workload cycles')
        static=sum(states[k]*number(power[k])/freq for k in states)
        events={}
        for event,coefficient in c.get('event_pj',{}).items():
            if event not in run.get('events',{}):raise ValueError('missing activity event: '+event)
            count=run['events'][event]
            if type(count) is not int or count<0:raise ValueError('activity count must be nonnegative integer')
            events[event]=count*number(coefficient)
        transitions=c.get('transitions',[])
        transition=0
        for t in transitions:
            if t['from'] not in states or t['to'] not in states or type(t['count']) is not int or t['count']<0:
                raise ValueError('invalid state transition')
            transition+=t['count']*number(t['energy_pj'])
        rows.append(dict(name=name,kind=c['kind'],source=c['source'],state_cycles=states,
                         state_energy_pj=static,event_energy_pj=events,transition_energy_pj=transition,
                         total_energy_pj=static+sum(events.values())+transition))
    if not rows:raise ValueError('nonempty system topology required')
    total=sum(r['total_energy_pj'] for r in rows)
    return store(out,dict(schema='rvw.system-energy/1',status='reported',
                         kind='abstract_system_energy',plan_sha256=sha256(p.read_bytes()).hexdigest(),
                         run_sha256=sha256(rp.read_bytes()).hexdigest(),trace_sha256=run.get('trace_sha256'),
                         duration_ns=duration,components=rows,total_energy_pj=total,average_power_mw=total/duration,
                         calibration_status='not_performed',accuracy_status='inconclusive',
                         limits=['state residency and coefficients are project declarations, not inferred hardware measurements',
                                 'event energies must exclude energy already included in state power',
                                 'all components use the declared common clock; transition timing is not simulated',
                                 'abstract system energy is not cell-level power or physical PPA']))
