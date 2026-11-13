"""Detailed RTL warming with a fixed measured interval."""
from pathlib import Path
from . import flow
from .validation import load


def sweep(manifest, out, start, length, lengths=(0,100,1000,10000), target_percent=1.0):
    if start < 1 or length < 2 or target_percent < 0:
        raise ValueError('positive ROI start, length >= 2 and nonnegative target required')
    lengths = sorted(set(lengths))
    if not lengths or any(type(w) is not int or not 0 <= w <= start for w in lengths):
        raise ValueError('warmup lengths must be integers in [0,start]')
    out = Path(out).resolve()
    out.mkdir(parents=True,exist_ok=True)
    spec = load(manifest)
    if start+length > spec['instructions']:
        raise ValueError('fixed ROI exceeds the profile budget')
    # This full-prefix observation is the timing reference at the exact same ROI.
    full = flow.run_point(spec,out/'baseline',dict(start_instruction=0,instructions=start+length,weight=1),0)
    import json
    expected = json.loads((out/'baseline/expected.json').read_text())[start:start+length]
    baseline = flow.compare(out/'baseline/rvfi.jsonl',json.loads((out/'baseline/expected.json').read_text()),start,length)
    rows=[]
    for w in lengths:
        work=out/f'w{w}'
        try:
            measured=flow.run_point(spec,work,dict(start_instruction=start,instructions=length,weight=1),w)
            actual=json.loads((work/'expected.json').read_text())[w:]
            if actual != expected:
                raise ValueError('fixed ROI reference effects differ')
            bias=100*(measured['cpi']/baseline['cpi']-1)
            rows.append(dict(warmup=w,capture=start-w,cpi=measured['cpi'],ipc=measured['ipc'],
                             signed_cpi_bias_percent=bias,absolute_bias_percent=abs(bias),
                             within_target=abs(bias)<=target_percent,status='matched'))
        except (ValueError,OSError) as exc:
            rows.append(dict(warmup=w,status='excluded',reason=str(exc)))
    within=[r['warmup'] for r in rows if r.get('within_target')]
    report=dict(schema='rvw.sample-warmup/1',status='reported' if all(r['status']=='matched' for r in rows) else 'inconclusive',
                start=start,length=length,baseline=baseline,rows=rows,target_percent=target_percent,
                smallest_observed_within_target=min(within) if within else None,
                warming='detailed RTL execution; functional cache/predictor injection unavailable',
                limits=['one fixed ROI; no general warmup threshold', 'baseline starts with architectural reset state',
                        'retirement-span timing excludes latency before the first measured retirement'])
    flow.write(out/'warmup.json',report)
    return report
