"""Verification-plan status, JSON and CLI entry points."""
import json
from rvw.results import write_json
from .model import VPlan


def execute_json(action='status',plan=None,previous=None,out=None):
    if action!='status': raise ValueError('unknown verification plan action')
    result=VPlan(plan).status(previous)
    if out: write_json(out,result)
    return result


def run(args):
    try:
        result=execute_json(plan=args.plan,previous=args.previous,out=args.out)
        serialized=json.dumps(result,indent=2,allow_nan=False)
        # Exit code carries the rolled-up verdict: 0 pass, 1 fail, 3 any other.
        code={'pass':0,'fail':1}.get(result.get('verdict'),3)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        result,code={'schema':'rvw.plan-error/1','status':'error','message':str(exc)},2
        serialized=json.dumps(result,indent=2)
    if args.json: print(serialized)
    elif code==2: print(result['message'])
    else:
        for feature in result['features']:
            print(f"{feature['id']}: {feature['status']}; {feature['hole_count']} holes")
        if result['unassigned_requirements']:
            print('Unassigned requirements: '+', '.join(result['unassigned_requirements']))
        print('Verdict: '+result['verdict'])
    return code


def register(subparsers):
    parser=subparsers.add_parser('plan',help='project verification requirements, evidence holes and trend')
    sub=parser.add_subparsers(dest='plan_command',required=True)
    status=sub.add_parser('status',help='roll up recorded coverage, tests, formal properties and checks')
    status.add_argument('plan')
    status.add_argument('--previous')
    status.add_argument('--out')
    status.add_argument('--json',action='store_true')
    status.set_defaults(func=run)
