"""Bounded retirement sequence candidates through CLI and MCP."""
import json
from .actions import generate


def execute_json(action='actions', goal=None, work_dir=None, registers=None, distances=None, memory=False):
    if action != 'actions':
        raise ValueError('unknown sequence candidate action')
    if isinstance(registers,str):
        registers = [int(r) for r in registers.split(',')]
    return generate(goal,work_dir,registers,distances or [1,2,4],memory)


def run(args):
    try:
        result = execute_json(goal=args.goal,work_dir=args.work_dir,registers=args.registers,
                              distances=args.distances,memory=args.memory)
        code = 0 if result['status']=='generated' else 3
    except (OSError,ValueError,TypeError) as exc:
        result,code = {'status':'error','message':str(exc)},2
    print(json.dumps(result,indent=2))
    return code


def register(sub):
    parser = sub.add_parser('actions',help='generate bounded retirement sequence actions; no measured hits')
    parser.add_argument('--goal',required=True)
    parser.add_argument('--work-dir',required=True)
    parser.add_argument('--registers',required=True)
    parser.add_argument('--distances',nargs='+',type=int,default=[1,2,4])
    parser.add_argument('--memory',action='store_true',help='declare writable aligned program data support')
    parser.add_argument('--json',action='store_true')
    parser.set_defaults(func=run)
