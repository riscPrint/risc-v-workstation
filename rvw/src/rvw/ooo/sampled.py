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
    cp,tp,pp=map(Path,(config,trace,points))
    description=json.loads(cp.read_text())
    if description.get('schema')=='rvw.arch-core/1' and json.loads(tp.read_bytes().splitlines()[0])['config']!=description['config']:
        raise ValueError('project description does not match C2 selected config')
    c=configuration(description);ops=_instructions(tp.read_bytes(),c.custom_instructions)
    sp=json.loads(pp.read_text())
    if sp.get('schema')!='rvw.csim-simpoints/1' or sp.get('instructions')!=len(ops):
        raise ValueError('simulation points must match the C2 instruction count')
    with tempfile.TemporaryDirectory(prefix='rvw-ooo-points-') as tmp:
        normalized,fmt,info=prepare(tp,'c2',Path(tmp))
        if sha256(normalized.read_bytes()).hexdigest()!=sp.get('sha256'):
            raise ValueError('simulation-point trace hash mismatch')
    selected=sp['points']
    if not selected or not math.isclose(sum(p['weight'] for p in selected),1,abs_tol=1e-9):
        raise ValueError('simulation-point weights must sum to one')
    rows=[];cpi=0
    for p in selected:
        start,n,weight=p['start_instruction'],p['instructions'],p['weight']
        if type(start) is not int or type(n) is not int or start<0 or n<1 or start+n>len(ops) or not math.isfinite(weight) or weight<=0:
            raise ValueError('invalid simulation point')
        capture=max(0,start-warmup);observer=Window(start-capture)
        r=simulate(ops[capture:start+n],c,max_cycles,backend='python',observer=observer)
        measured=observer.cycles()
        if measured<1:
            raise ValueError('sample has no measured cycle')
        rows.append(dict(point=p,warmup=start-capture,cycles=measured,instret=n,
                         ipc=n/measured,model_cycles_including_warmup=r['cycles']))
        cpi+=weight*measured/n
    report=dict(schema='rvw.ooo-sampled/1',status='reported',
                config_sha256=sha256(cp.read_bytes()).hexdigest(),trace_sha256=sha256(tp.read_bytes()).hexdigest(),
                points_sha256=sha256(pp.read_bytes()).hexdigest(),samples=rows,
                sampled_cpi=cpi,sampled_ipc=1/cpi,estimated_cycles=cpi*len(ops),
                accuracy_status='inconclusive',
                limits=['each point starts cold before its bounded warmup',
                        'measurement starts at warmup retirement; shared boundary cycles count once',
                        'end-of-sample drain and absent future work can bias timing',
                        'sampling error is unmeasured unless a full run is requested'])
    if full:
        whole=simulate(ops,c,max_cycles)
        report['full_cycles']=whole['cycles']
        report['signed_cycle_error_percent']=100*(cpi*len(ops)/whole['cycles']-1)
    return store(out,report)
