"""Validate a complete C2 stream while decoding only selected timing windows."""
from hashlib import sha256
from rvw.cosim.trace import Trace
from .core import _instruction


def digest(path):
    h=sha256()
    with open(path,'rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def collect(path, points, warmup, custom_instructions=()):
    windows=[(max(0,p['start_instruction']-warmup),p['start_instruction']+p['instructions']) for p in points]
    captured=[[] for _ in windows]
    trace=Trace(path)
    count,ended=0,False
    try:
        if trace.multihart:
            raise ValueError('multi-hart timing is unsupported')
        for row in trace:
            if row.get('event')=='end':
                if row['status']!='pass':
                    raise ValueError('trace end is not pass')
                ended=True
                continue
            if row.get('event')=='irq' and row['levels']==0:
                continue
            if 'event' in row or any(row[k] for k in ('trap','intr','halt','mem_fault')):
                raise ValueError('traps, interrupts and external events are unsupported')
            selected=[i for i,(lo,hi) in enumerate(windows) if lo<=count<hi]
            if selected:
                op=_instruction(row,trace.header['xlen'],custom_instructions)
                for i in selected:
                    captured[i].append(op)
            count+=1
        if not ended:
            raise ValueError('missing C2 end marker')
        return count,captured,trace.header
    finally:
        trace.close()
