"""Native full-prefix comparison and fixed-ROI warm-up experiments."""
from pathlib import Path
import json
from . import flow


def load(manifest):
    manifest = Path(manifest).resolve()
    spec = json.loads(manifest.read_text())
    if spec.get('schema') != 'rvw.sample-study/1':
        raise ValueError('expected rvw.sample-study/1')
    for key in ('elf','platform','shim','mapping'):
        spec[key] = str((manifest.parent/spec[key]).resolve())
    spec['mapping'] = json.loads(Path(spec['mapping']).read_text())
    spec.setdefault('timeout',120)
    return spec


def validate(manifest, out, intervals=(10000,50000), clusters=(1,4,8), warmup=1000):
    """Run the same bounded prefix fully and through each sampling setting."""
    if not intervals or not clusters:
        raise ValueError('at least one interval and cluster setting required')
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    spec = load(manifest)
    profile = flow.profile(spec, out)
    _, total = flow.simpoint.bbvs(profile, spec['instructions'])
    full = flow.run_point(spec, out/'full', dict(start_instruction=0,
                          instructions=total, weight=1), 0)
    rows = []
    for interval in intervals:
        for k in clusters:
            sampled = flow.run(manifest, out/f'i{interval}-k{k}', interval=interval, max_k=k, warmup=warmup)
            ipc = sampled['weighted_ipc']
            rows.append(dict(interval=interval,max_k=k,points=len(sampled['points']),
                             full_ipc=full['ipc'],sampled_ipc=ipc,
                             signed_error_percent=100*(ipc/full['ipc']-1) if ipc is not None else None,
                             status=sampled['status']))
    errors = [abs(r['signed_error_percent']) for r in rows if r['signed_error_percent'] is not None]
    report = dict(schema='rvw.sample-validation/1',status='reported' if len(errors)==len(rows) and rows else 'inconclusive',
                  elf_sha256=flow.digest(spec['elf']),platform_sha256=flow.digest(spec['platform']),
                  full=full,rows=rows,program_complete=flow.profile_complete(profile),warmup=warmup,identity=sampled.get('identity',{}),max_observed_error_percent=max(errors) if errors else None,
                  confidence='empirical error on this prefix only; no statistical confidence interval or long-program guarantee',
                  timing='N-1 retirement gaps for full and sampled intervals')
    flow.write(out/'validation.json',report)
    return report
