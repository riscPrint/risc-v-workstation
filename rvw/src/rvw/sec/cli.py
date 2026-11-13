"""Simulation security command entry points."""
import json
from rvw.common.subcommands import register_commands
from .ift import run


def register(subparsers):
    p = subparsers.add_parser('sec', help='digital security tests in simulation')
    sub = p.add_subparsers(dest='sec_command', required=True)
    q = sub.add_parser('ift', help='run a Boolean taint shadow design in Verilator')
    for name in ('rtl','top','policy','stimulus','out'):
        q.add_argument('--'+name, required=True)
    q.add_argument('--mode', choices=('precise','conservative'), default='precise')
    q.add_argument('--db')
    q.set_defaults(func=execute)
    register_commands('rvw.sec',sub)


def execute(args):
    try:
        r = run(**{k:getattr(args,k) for k in ('rtl','top','policy','stimulus','out','mode','db')})
        print(json.dumps(r,indent=2))
        return {'violation':1,'inconclusive':3}.get(r['status'],0)
    except (ValueError,OSError,KeyError) as e:
        print(str(e)); return 2
