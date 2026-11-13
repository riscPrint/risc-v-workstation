"""Generate verification cases from explicit, versioned project obligations.

Generation never executes RTL or invents a reference result. Vectors and mutants
are authored by the project separately from this generator.
"""
import datetime as dt
import hashlib
import itertools
import json
from pathlib import Path
from rvw.results import write_json


def same(left, right):
    return json.dumps(left, sort_keys=True, allow_nan=False) == json.dumps(right, sort_keys=True, allow_nan=False)


def generate(declaration, out):
    obj = json.loads(Path(declaration).read_text())
    if obj.get('schema') != 'rvw.verification-obligations/1':
        raise ValueError('expected rvw.verification-obligations/1')
    if not isinstance(obj.get('specifications'), dict) or not obj['specifications'] or not all(
            isinstance(k,str) and k and isinstance(v,str) and v for k,v in obj['specifications'].items()):
        raise ValueError('explicit specification versions are required')
    obligations = obj.get('obligations')
    if not isinstance(obligations,list) or not obligations:
        raise ValueError('at least one obligation is required')
    cases, seen = [], set()
    for obligation in obligations:
        name = obligation.get('id')
        if not isinstance(name,str) or not name or name in seen:
            raise ValueError('obligation IDs must be unique and nonempty')
        seen.add(name)
        kind = obligation.get('kind')
        if kind == 'extension':
            operands = obligation.get('operand_bins')
            if not isinstance(operands,dict) or not operands or not all(
                    isinstance(v,list) and v for v in operands.values()):
                raise ValueError('extension requires nonempty operand_bins')
            for values in itertools.product(*operands.values()):
                cases.append({'obligation': name, 'kind': 'operand', 'operands': dict(zip(operands,values))})
            for key, case_kind in [('exceptions','exception'),('dependencies','dependency')]:
                if not isinstance(obligation.get(key),list) or not obligation[key]:
                    raise ValueError(f'extension requires explicit {key}')
                cases.extend({'obligation':name,'kind':case_kind,'scenario':value} for value in obligation[key])
        elif kind == 'envcfg':
            # The project defines implemented fields and legal writes per spec.
            for key in ('csr','field','legal_writes','contexts','transitions','enabled','disabled'):
                if key not in obligation:
                    raise ValueError(f'envcfg requires {key}')
            if obligation['csr'] not in ('menvcfg','senvcfg','henvcfg'):
                raise ValueError('envcfg CSR must be menvcfg, senvcfg or henvcfg')
            for key in ('legal_writes','contexts','transitions'):
                if not isinstance(obligation[key],list) or not obligation[key]:
                    raise ValueError(f'envcfg requires nonempty {key}')
            for write,context,transition,enabled in itertools.product(
                    obligation['legal_writes'],obligation['contexts'],obligation['transitions'],(False,True)):
                cases.append({'obligation':name,'kind':'envcfg','csr':obligation['csr'],
                              'field':obligation['field'],'write':write,'context':context,
                              'transition':transition,'enabled':enabled,
                              'expected_behavior':obligation['enabled' if enabled else 'disabled']})
        else:
            raise ValueError('kind must be extension or envcfg')
        vectors, mutants = obligation.get('reference_vectors'), obligation.get('mutants')
        if not isinstance(vectors,list) or not vectors or not isinstance(mutants,list) or not mutants:
            raise ValueError('independent reference_vectors and mutants are required')
        ids = set()
        for vector in vectors:
            if not isinstance(vector,dict) or not {'id','inputs','expected','author'} <= vector.keys() or not vector['author']:
                raise ValueError('reference vector needs id, inputs, expected and author')
            if vector['id'] in ids:
                raise ValueError('duplicate vector ID')
            ids.add(vector['id'])
            cases.append({'obligation':name,'kind':'reference','vector':vector})
        for mutant in mutants:
            if not isinstance(mutant,dict) or not {'id','vector','observed','author'} <= mutant.keys() or not mutant['author']:
                raise ValueError('mutant needs id, vector, observed and author')
            matching = [v for v in vectors if v['id'] == mutant['vector']]
            if len(matching) != 1 or same(mutant['observed'], matching[0]['expected']):
                raise ValueError('mutant must differ from its independent reference vector')
            cases.append({'obligation':name,'kind':'mutant','mutant':mutant})
    for i,case in enumerate(cases):
        case.update(id=f'case-{i:06d}', status='not_run')
    report = {'schema':'rvw.verification-plan/1','status':'generated',
              'specifications':obj['specifications'],'cases':cases,
              'source':str(Path(declaration).resolve())}
    with Path(out).open('x') as dst:
        json.dump(report,dst,indent=2)
        dst.write('\n')
    return report


def check_vectors(plan, observations, out):
    """Check project observations against supplied independent vectors.

    A vector match is bounded data comparison. It is not CPU qualification.
    """
    plan_path = plan
    plan = json.loads(Path(plan).read_text())
    observed = json.loads(Path(observations).read_text())
    if plan.get('schema') != 'rvw.verification-plan/1' or not isinstance(observed,dict):
        raise ValueError('expected plan and observation object keyed by case ID')
    rows = []
    for case in plan['cases']:
        if case['kind'] != 'reference':
            continue
        present = case['id'] in observed
        status = 'error' if not present else 'pass' if same(observed[case['id']], case['vector']['expected']) else 'fail'
        rows.append({'id':case['id'],'kind':'extension-vector','status':status,
                     'signature':None if status=='pass' else 'uvm-plan:'+status,
                     **({'inconclusive':'missing vector observation'} if not present else {})})
    if not rows:
        raise ValueError('no reference vectors in plan')
    report = {'schema':'rvw.results/1','suite':'verification-vectors','core':'project',
              'config':'declared-vectors','tests':rows,
              'run_id':Path(out).stem,'created':dt.datetime.now(dt.timezone.utc).isoformat(),
              'source':{'identity_complete':False, 'plan_sha256':hashlib.sha256(Path(plan_path).read_bytes()).hexdigest(),
                        'observations_sha256':hashlib.sha256(Path(observations).read_bytes()).hexdigest()}}
    if Path(out).exists():
        raise ValueError('output exists')
    write_json(out,report)
    return report
