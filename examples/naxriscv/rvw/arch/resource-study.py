#!/usr/bin/env python3
"""Score one frozen resource policy against existing RTL captures, without fitting.

Usage: resource-study.py CALIBRATION_PLAN DELTA_PLAN CONFIG NEW_OUTPUT
Plans use the documented rvw schemas. No RTL or Spike process is started.
Retain summary.json. Full calibration and delta reports stay in NEW_OUTPUT.
"""
import json
from math import sqrt
from pathlib import Path
import sys
from rvw.ooo.evidence import calibrate, digest
from rvw.ooo.delta import delta


def summarize(calibration, report):
    rows = report['rows']
    absolute = {split: dict(mae_percent=sum(abs(r['ipc_error_percent']) for r in samples)/len(samples),
                           samples=[dict(program=r['id'], rtl_ipc=r['rtl_ipc'], model_ipc=r['model']['ipc'],
                                         ipc_error_percent=r['ipc_error_percent'], model_events=r['model'].get('events', {})) for r in samples])
                for split, samples in calibration['samples'].items()}
    ranking = []
    config = calibration['samples']['training'][0]['model']['config']
    for variant in report['variants']:
        pairs = [r for r in rows if r['variant'] == variant['id']]
        field, value = next(iter(variant['changes'].items()))
        baseline = config
        for part in field.split('.'):
            baseline = baseline[part]
        step = value/baseline-1
        rtl = sum(r['model_base']['instret']/r['rtl_base_ipc'] for r in pairs)/sum(r['model_base']['instret']/r['rtl_variant_ipc'] for r in pairs)-1
        model = sum(r['model_base']['cycles'] for r in pairs)/sum(r['model_variant']['cycles'] for r in pairs)-1
        ranking.append(dict(variant=variant['id'], measured=abs(rtl/step), predicted=abs(model/step)))
    c = d = t = u = 0
    for i, a in enumerate(ranking):
        for b in ranking[i+1:]:
            x, y = a['predicted']-b['predicted'], a['measured']-b['measured']
            c += x*y > 0; d += x*y < 0; t += x == 0 and y != 0; u += y == 0 and x != 0
    denominator = sqrt((c+d+t)*(c+d+u))
    return dict(schema='rvw.nax-resource-study/1', within=sum(not r['wrong_delta'] for r in rows),
                nonzero_within=sum(not r['wrong_delta'] and r['measured_delta'] != 0 for r in rows),
                absolute=absolute, rank=dict(rows=ranking, kendall_tau_b=(c-d)/denominator if denominator else None,
                model_ties=t, method='same large steps as RTL; pooled cycles; not local sensitivity'),
                rows=[{k:r[k] for k in ('program','variant','measured_delta','predicted_delta','wrong_delta','absolute_error_pp','hashes','base_hashes')} for r in rows],
                engine_sha256=rows[0]['model_base']['engine_sha256'], config=config)


def main(calibration_plan, delta_plan, config, output):
    cp, dp, config, output = map(lambda p: Path(p).resolve(), (calibration_plan, delta_plan, config, output))
    output.mkdir(parents=True, exist_ok=False)
    plan = json.loads(cp.read_text())
    plan['config'] = str(config)
    plan['event_map'] = str((cp.parent/plan['event_map']).resolve())
    for sample in plan['samples']:
        for key in ('elf', 'trace', 'c1', 'events'):
            sample[key] = str((cp.parent/sample[key]).resolve())
    (output/'base-plan.json').write_text(json.dumps(plan))
    calibrate(output/'base-plan.json', output/'calibration.json')
    plan = json.loads(dp.read_text())
    plan.update(config=str(config), calibration=str(output/'calibration.json'))
    for sample in plan['samples']:
        for capture in [sample['base'], *sample['variants'].values()]:
            for key in ('elf', 'trace', 'c1'):
                capture[key] = str((dp.parent/capture[key]).resolve())
    (output/'delta-plan.json').write_text(json.dumps(plan))
    delta(output/'delta-plan.json', output/'delta')
    result = summarize(json.loads((output/'calibration.json').read_text()), json.loads((output/'delta/report.json').read_text()))
    result['inputs'] = dict(calibration_plan=digest(cp), delta_plan=digest(dp), config=digest(config))
    (output/'summary.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main(*sys.argv[1:])
