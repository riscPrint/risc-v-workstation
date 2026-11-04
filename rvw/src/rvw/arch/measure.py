"""Repeat both engines with fresh evidence and summarize observed variation."""
from pathlib import Path

from . import core
from .statistics import interval
from rvw.results import write_json


def measure(out, project=None, bench=None, timeout=3600, repeats=3):
    if type(repeats) is not int or not 2 <= repeats <= 10:
        raise ValueError('repeats must be between 2 and 10')
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    reports = []
    identity = None
    for repeat in range(repeats):
        report = core.calibrate(project, bench, out / f'repeat-{repeat}', timeout)
        base, _, _ = core.checked_report(report['base'])
        candidate, _, _ = core.checked_report(report['candidate'])
        current = (base['core'], base['config'], base['memory_latency'],
                   candidate['description_sha256'], candidate['model_sha256'], candidate['tool']['sha256'],
                   sorted((r['id'], r['elf_sha256'], r['instret']) for r in base['benchmarks']))
        if identity is not None and current != identity:
            raise ValueError('measurement inputs or tools changed between repeats')
        identity = current
        reports.append(report)
    names = [r['id'] for r in reports[0]['benchmarks']]
    rows = []
    for name in names:
        samples = [next(r for r in report['benchmarks'] if r['id'] == name) for report in reports]
        rows.append({'id': name, **{key: interval([r[key] for r in samples]) for key in
                                   ('base_cycles', 'candidate_cycles', 'ipc_ratio', 'cycle_gap_percent')}})
    result = {'schema': 'rvw.arch-measure/1', 'status': 'reported', 'benchmarks': rows,
              'reports': reports, 'limits': 'Fixed seed 1. Bootstrap intervals measure observed repeat variation only. Zero width does not establish accuracy. No fidelity verdict.'}
    write_json(out / 'measure.json', result)
    return result
