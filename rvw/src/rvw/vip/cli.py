"""Protocol agent inventory and design database bench skeletons."""
import json
import sys
from .catalog import agents, buses, skeleton
from rvw.query.db import QueryError


def register(sub):
    p=sub.add_parser('vip',help='list protocol agents and generate bus bench skeletons')
    commands=p.add_subparsers(dest='vip_command',required=True)
    q=commands.add_parser('list',help='list protocol agents and supported Spinal bus types')
    q.set_defaults(func=_run)
    q=commands.add_parser('buses',help='list supported typed buses in a design database')
    q.add_argument('--db',required=True); q.set_defaults(func=_run)
    q=commands.add_parser('bench',help='generate a cocotb bench skeleton for one typed bus')
    q.add_argument('--db',required=True); q.add_argument('--bus')
    q.add_argument('--out',required=True); q.add_argument('--clock',default='clk'); q.add_argument('--reset',default='reset_n')
    q.set_defaults(func=_run)


def _run(a):
    try:
        if a.vip_command=='list': result=agents()
        elif a.vip_command=='buses': result=buses(a.db)
        else: result=skeleton(a.db,a.out,a.bus,a.clock,a.reset)
        print(json.dumps(result,indent=2)); return 0
    except (QueryError,OSError,ValueError) as exc:
        print('rvw vip: '+str(exc),file=sys.stderr); return 2
