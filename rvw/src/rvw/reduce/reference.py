"""Strict Spike mismatch predicate for C1-passing reduction trials."""
from rvw.cosim.cli import execute_json as cosim
from rvw.regress.random_stream import complete


def check(run, elf, platform):
    if run.inconclusive:
        return dict(status='inconclusive', message=run.inconclusive)
    if run.get('status') != 'pass':
        return dict(status='different', message='candidate does not pass C1')
    trace = run.artifact('rvfi_trace')
    if trace is None:
        return dict(status='inconclusive', message='candidate has no C2 trace')
    comparison = cosim('check', elf=str(elf), trace=str(trace), platform=str(platform),
                       model='spike', strict=True, core=run.get('core'))
    fields = sorted(comparison.get('mismatch', {}).get('differences', {}))
    if (comparison.get('status') == 'mismatch' and fields
            and not comparison.get('synchronized') and not comparison.get('applied_masks')):
        return dict(status='mismatch', signature='cosim:'+','.join(fields), comparison=comparison)
    if complete(comparison, run.result) and not comparison.get('applied_masks'):
        return dict(status='different', comparison=comparison)
    return dict(status='inconclusive', comparison=comparison,
                message='reference check is incomplete or synchronized')
