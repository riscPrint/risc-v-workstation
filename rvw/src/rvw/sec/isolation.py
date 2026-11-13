"""Paired privilege-boundary and protection timing campaigns."""
import json
from pathlib import Path
from .pairs import run as run_pairs
from .common import publish

KINDS=('pmp','epmp','register-state','predictor-state','cache-state')


def run(manifest,out):
    source=Path(manifest).resolve();plan=json.loads(source.read_text())
    if plan.get('isolation_kind') not in KINDS:
        raise ValueError('declare pmp, epmp, register-state, predictor-state or cache-state')
    if not plan.get('program') or not plan.get('boundary'):
        raise ValueError('declare project program and privilege boundary')
    if plan['contract']!='sandboxing': raise ValueError('isolation requires sandboxing contract')
    if plan.get('contract_start_pc') is None:
        raise ValueError('declare contract_start_pc after the privilege boundary')
    if not plan.get('policy'):
        raise ValueError('declare protection policy and expected denied region or state cleanup')
    if not plan.get('observations'):
        raise ValueError('declare post-boundary timing or state observation channels')
    result=run_pairs(source,out)
    return publish(out,'isolation',result['findings'],result['complete'],
                   isolation_kind=plan['isolation_kind'],boundary=plan['boundary'],
                   policy=plan['policy'],errors=result.get('errors',[]),
                   contract_start_pc=plan['contract_start_pc'])
