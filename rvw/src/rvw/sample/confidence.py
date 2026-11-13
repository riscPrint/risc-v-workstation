"""Attach measured calibration error without inventing a confidence interval."""
from pathlib import Path
import json
import math


def statement(path, identity, interval, max_k, warmup):
    if path is None:
        return 'unmeasured; run validation on this core and workload class'
    data=json.loads(Path(path).read_text())
    if data.get('schema')!='rvw.sample-validation/1' or data.get('status')!='reported':
        raise ValueError('confidence requires a completed native validation report')
    calibrated=data.get('identity',{})
    if any(k not in calibrated or calibrated[k]!=identity[k] for k in ('platform','mapping','adapter_files')):
        raise ValueError('calibration platform, mapping or adapter differs')
    if data.get('warmup')!=warmup:
        raise ValueError('calibration warmup differs')
    rows=[r for r in data['rows'] if r['interval']==interval and r['max_k']==max_k]
    if not rows or any(r['status']!='estimated' for r in rows):
        raise ValueError('calibration does not cover these sampling settings')
    errors=[abs(r['signed_error_percent']) for r in rows]
    if any(not math.isfinite(e) for e in errors):
        raise ValueError('finite measured errors required')
    return dict(method='empirical calibration error; no statistical confidence interval',
                max_observed_error_percent=max(errors),calibration_elf_sha256=data['elf_sha256'],
                scope='the measured validation prefix only',
                limits=['not a guaranteed error bound for this long program',
                        'revalidate after any RTL build or configuration change',
                        'workload-class transfer is unqualified'])
