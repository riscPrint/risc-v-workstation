"""Own-model timing on ComponentSims simulation points."""
from hashlib import sha256
import json
import math
from pathlib import Path
import tempfile
from rvw.arch.ledger import store
from rvw.csim.study import prepare
from .core import _instructions,simulate
from .project import configuration


class Window:
    def __init__(self,warmup):
        self.warmup=warmup;self.retired=0;self.start=None;self.shared=False
    def observe(self,committed,rob,recovery,next_pc):
        self.retired+=len(committed)
        if self.start is None and self.retired>=self.warmup:
            self.start=self.cycle
            self.shared=self.retired>self.warmup
    def cycles(self):
        return self.cycle-self.start+int(self.shared or self.warmup==0)


def sampled(config,trace,points,out,warmup=10000,max_cycles=1000000,full=False):
    if type(warmup) is not int or warmup<0:
        raise ValueError('warmup must be nonnegative')
    from .windows import collect, digest
    cp,tp,pp=map(Path,(config,trace,points))
    description=json.loads(cp.read_text())
    c=configuration(description)
    sp=json.loads(pp.read_text())
    if sp.get('schema')!='rvw.csim-simpoints/1' or type(sp.get('instructions')) is not int or sp['instructions']<1:
        raise ValueError('simulation points must declare a positive C2 instruction count')
    selected=sp['points']
    if not selected or not math.isclose(sum(p['weight'] for p in selected),1,abs_tol=1e-9):
        raise ValueError('simulation-point weights must sum to one')
    for p in selected:
        start,n,weight=p['start_instruction'],p['instructions'],p['weight']
        if type(start) is not int or type(n) is not int or start<0 or n<1 or start+n>sp['instructions'] or not math.isfinite(weight) or weight<=0:
            raise ValueError('invalid simulation point')
    count,windows,header=collect(tp,selected,warmup,c.custom_instructions)
    if count!=sp['instructions']:
        raise ValueError('simulation points must match the C2 instruction count')
    if description.get('schema')=='rvw.arch-core/1' and header['config']!=description['config']:
        raise ValueError('project description does not match C2 selected config')
    trace_hash=digest(tp)
    if sp.get('source_c2_sha256'):
        if trace_hash!=sp['source_c2_sha256']:
            raise ValueError('simulation-point trace hash mismatch')
    else:
        with tempfile.TemporaryDirectory(prefix='rvw-ooo-points-') as tmp:
            normalized,fmt,info=prepare(tp,'c2',Path(tmp))
            if digest(normalized)!=sp.get('sha256'):
                raise ValueError('simulation-point trace hash mismatch')
    rows=[];cpi=0
    for p,window in zip(selected,windows):
        start,n,weight=p['start_instruction'],p['instructions'],p['weight']
        capture=max(0,start-warmup);observer=Window(start-capture)
        r=simulate(window,c,max_cycles,backend='python',observer=observer)
        measured=observer.cycles()
        if measured<1:
            raise ValueError('sample has no measured cycle')
        rows.append(dict(point=p,warmup=start-capture,cycles=measured,instret=n,
                         ipc=n/measured,model_cycles_including_warmup=r['cycles']))
        cpi+=weight*measured/n
    report=dict(schema='rvw.ooo-sampled/1',status='reported',
                config_sha256=sha256(cp.read_bytes()).hexdigest(),trace_sha256=trace_hash,
                points_sha256=sha256(pp.read_bytes()).hexdigest(),samples=rows,
                sampled_cpi=cpi,sampled_ipc=1/cpi,estimated_cycles=cpi*count,
                accuracy_status='inconclusive',
                limits=['complete C2 structure validated; only selected warmup and sample instructions decoded',
                        'each point starts cold before its bounded warmup',
                        'measurement starts at warmup retirement; shared boundary cycles count once',
                        'end-of-sample drain and absent future work can bias timing',
                        'sampling error is unmeasured unless a full run is requested'])
    if full:
        whole=simulate(_instructions(tp.read_bytes(),c.custom_instructions),c,max_cycles)
        report['full_cycles']=whole['cycles']
        report['signed_cycle_error_percent']=100*(cpi*count/whole['cycles']-1)
    return store(out,report)
