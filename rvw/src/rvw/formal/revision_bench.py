"""Measure fresh target proofs with and without cone-matched helper assertions."""
from pathlib import Path
import json
import statistics
import time
from .ic3_lemmas import run as lemmas
from .portfolio import race


def measure(base, revised, root, out, *, timeout=10, trials=3):
    if type(trials) is not int or not 1 <= trials <= 20:
        raise ValueError('trials must be in 1..20')
    out=Path(out);out.mkdir(parents=True,exist_ok=False)
    start=time.monotonic()
    exported=lemmas(base,root,out/'export',timeout=timeout)
    export_s=time.monotonic()-start
    (out/'export/result.json').write_text(json.dumps(exported,indent=2)+'\n')
    library=out/'export/library.json'
    report={'schema':'rvw.formal-revision-bench/1','status':'inconclusive','export_wall_s':export_s,
            'base_source_sha256':[s['sha256'] for s in base['sources']],
            'revised_source_sha256':[s['sha256'] for s in revised['sources']], 'trials':[],
            'limits':'Alternating fresh target proofs. Reused lemmas remain assertions and need matching transition cones. '
            'Reported savings include target preparation and reuse overhead, but exclude one-time library export. '
            'This local sample does not predict another design. No cached verdict is returned.'}
    if exported['status']!='pass' or not library.exists():
        return {**report,'reason':'base_export_not_proved'}
    for i in range(trials):
        for variant in (['cold','reuse'] if i%2==0 else ['reuse','cold']):
            target=out/f'{i}-{variant}';start=time.monotonic()
            if variant=='cold':
                r=race({**revised,'engines':revised.get('engines',['smtbmc:yices'])},root,target,timeout=timeout)
            else:
                r=lemmas(revised,root,target,library=library,timeout=timeout)
            elapsed=time.monotonic()-start
            (target/'result.json').write_text(json.dumps(r,indent=2)+'\n')
            report['trials'].append({'trial':i,'variant':variant,'status':r['status'],
                'wall_s':elapsed,'selected_lemmas':len(r.get('entries',[])) if variant=='reuse' else 0,
                'result':str(target.relative_to(out)/'result.json')})
    if all(r['status']=='pass' for r in report['trials']):
        cold=statistics.median(r['wall_s'] for r in report['trials'] if r['variant']=='cold')
        warm=statistics.median(r['wall_s'] for r in report['trials'] if r['variant']=='reuse')
        report.update(status='pass',cold_median_s=cold,reuse_median_s=warm,saved_s=cold-warm,
                      speedup=cold/warm if warm else None)
    return report
