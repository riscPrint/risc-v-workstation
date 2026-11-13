"""Detection-power regression against an exact, project-pinned mutant plan."""
import json
from pathlib import Path
from .core_mutation import run_campaign,mutant_set_identity,KILLS


def check_expected(result, expected):
    """Require the baseline and every pinned killer. Missing work cannot pass."""
    if expected.get('schema')!='rvw.mutation-expectations/1' or not expected.get('mutants'):
        raise ValueError('nonempty pinned mutant expectations required')
    ids=[r['id'] for r in expected['mutants']]
    if len(ids)!=len(set(ids)):raise ValueError('duplicate expected mutant')
    if expected['mutant_set_sha256']!=result['mutant_set_sha256']:raise ValueError('expected mutant set identity differs')
    rows={r['id']:r for r in result['mutants']}
    observations=[]
    for pin in expected['mutants']:
        row=rows.get(pin['id'])
        if not row: status='inconclusive'
        elif row['state'] not in KILLS:
            status='lost' if row['state'] in ('survived','equivalent (proved)') else 'inconclusive'
        elif row['first_killer']!=pin['killer'] or row['state']!=pin['outcome']:status='changed'
        else:status='detected'
        observations.append(dict(id=pin['id'],status=status,expected=pin,
                                 observed=None if not row else dict(state=row['state'],killer=row['first_killer'])))
    baseline=result.get('baseline') or {}
    status=('inconclusive' if baseline.get('state')!='survived' else
            'fail' if any(r['status'] in ('lost','changed') for r in observations) else
            'inconclusive' if any(r['status']=='inconclusive' for r in observations) else 'pass')
    return dict(schema='rvw.mutation-regression/1',status=status,mutants=observations)


def execute(work_dir, expectations, budget_s=120):
    """Always rerun pinned mutants. Historical results alone cannot pass a regression."""
    out=Path(work_dir).resolve()
    expected=json.loads(Path(expectations).read_text())
    plan=json.loads((out/'plan.json').read_text())
    check_expected(dict(mutant_set_sha256=mutant_set_identity(plan),mutants=[],baseline=None),expected)
    # A regression attempt gets a new result record. Logs are overwritten by the
    # campaign. Keep the old result beside the attempt for diagnosis.
    state=out/'results.json'
    if state.exists():state.replace(out/'previous-results.json')
    result=run_campaign(out,budget_s)
    return check_expected(result,expected)
