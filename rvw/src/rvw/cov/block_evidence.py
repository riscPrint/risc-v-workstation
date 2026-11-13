"""Check declared block reuse conditions against recorded C1 evidence."""
from hashlib import sha256
import json
from pathlib import Path
from rvw.results import load_run
from . import captured


def source_id(sources):
    return sha256(json.dumps(sources,sort_keys=True,separators=(',',':')).encode()).hexdigest()


@captured.command
def check(evidence,integration):
    evidence, integration=Path(evidence).resolve(),Path(integration).resolve()
    record=json.loads(captured.read_text(evidence));context=json.loads(captured.read_text(integration))
    if record.get('schema')!='rvw.block-evidence/1' or context.get('schema')!='rvw.block-integration/1':
        raise ValueError('expected block evidence and block integration schemas')
    result={'schema':'rvw.block-reuse/1','status':'inconclusive','holes':[], 'runs':[],
            'new_wiring_covered':False,'evidence_sha256':captured.sha256(evidence),
            'integration_sha256':captured.sha256(integration),
            'notes':['Only recorded block evidence can transfer. Integration wiring needs separate checks.',
                     'Assumptions are project declarations checked against the integration description. Runtime enforcement is not established.']}
    def resolve(root,value):
        path=Path(value)
        return path if path.is_absolute() else root/path
    sources={name:pin['sha256'] for name,pin in record['sources'].items()}
    if not sources or set(sources)!=set(context['sources']):
        result['holes'].append('source input set differs')
    else:
        for name,pin in record['sources'].items():
            if captured.sha256(resolve(evidence.parent,pin['path']))!=pin['sha256']:
                result['holes'].append('evidence source changed: '+name)
            if captured.sha256(resolve(integration.parent,context['sources'][name]))!=pin['sha256']:
                result['holes'].append('integration source differs: '+name)
    identifier=source_id(sources);result['source_id']=identifier
    matches=[config for config in record['configurations'] if config['parameters']==context['parameters']]
    if len(matches)!=1:
        result['holes'].append('need one exactly tested parameter configuration')
    if result['holes']:
        result['status']='incompatible'
        return result
    config=matches[0]
    for name,value in config['assumptions'].items():
        if name not in context['environment'] or context['environment'][name]!=value:
            result['holes'].append('integration assumption differs or is missing: '+name)
    if result['holes']:
        result['status']='incompatible'
        return result
    result['unchecked_environment_fields']=sorted(context['environment'].keys()-config['assumptions'].keys())
    expected={'source_id':identifier,'parameters':config['parameters'],'assumptions':config['assumptions']}
    if not config['runs']:
        result['holes'].append('no block execution evidence')
    for pin in config['runs']:
        path=resolve(evidence.parent,pin['path'])
        try:
            if captured.sha256(path)!=pin['sha256']:
                raise ValueError('C1 record hash differs')
            run=load_run(path)
            if run.why_inconclusive or run.status!='pass':
                raise ValueError('block C1 execution is not a conclusive pass')
            if run.extra.get('details',{}).get('block_evidence')!=expected:
                raise ValueError('C1 block source/parameter/assumption receipt differs')
            result['runs'].append({'path':str(path),'sha256':pin['sha256'],'status':'recorded_pass'})
        except (OSError,ValueError) as exc:
            result['holes'].append(str(path)+': '+str(exc))
    if not result['holes']:
        result['status']='eligible_for_reuse'
    return result


def execute_json(action='block-check',evidence=None,integration=None):
    if action!='block-check':
        raise ValueError('unknown block evidence action')
    return check(evidence,integration)


def run(args):
    try:
        result=check(args.evidence,args.integration)
        code={'eligible_for_reuse':0,'incompatible':1,'inconclusive':3}[result['status']]
    except (OSError,ValueError,KeyError,TypeError) as exc:
        result,code={'status':'error','message':str(exc)},2
    print(json.dumps(result,indent=2))
    return code


def register(sub):
    parser=sub.add_parser('block-check',help='check exact tested block parameters and integration assumptions')
    parser.add_argument('--evidence',required=True)
    parser.add_argument('--integration',required=True)
    parser.add_argument('--json',action='store_true')
    parser.set_defaults(func=run)
