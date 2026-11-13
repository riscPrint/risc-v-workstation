"""Expose structural results without promoting them to CDC/RDC signoff."""
from collections import Counter


def summarize(report, required_libraries=()):
    recognized = {f['library'] for f in report.get('findings',[]) if f.get('library')}
    recognized.update(c['library']['class_name'] for c in report.get('crossings',[]) if c.get('library'))
    missing = sorted(set(required_libraries)-recognized)
    protected = [c for c in report.get('crossings',[]) if c.get('kind') in ('sync_2ff','synchronous_related')]
    protected += [c for c in report.get('rdc',{}).get('crossings',[]) if c.get('status') == 'protected']
    status = 'inconclusive'
    reason = None
    if missing:
        reason = 'Declared synchronizers not recognized: '+', '.join(missing)
    elif report.get('registers',0)<=0 or report.get('clock_count',0)<2:
        reason = 'Multi-domain structural check needs registers in at least two clock domains.'
    elif report.get('findings'):
        status = 'findings'
    elif protected:
        status = 'protected'
    else:
        reason = 'No classified crossing found in the multi-domain database.'
    return dict(status=status,reason=reason,recognized_libraries=sorted(recognized),
                findings=dict(Counter(f['rule'] for f in report.get('findings',[]))),
                protected=len(protected),no_reset_hazard=sum(c.get('status')=='no_hazard' for c in report.get('rdc',{}).get('crossings',[])),scope='Structural CDC/RDC findings and recognized protection; protocol and reset release remain unproved.')
