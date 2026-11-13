"""SoC verification CLI and MCP entry points."""
import json
from rvw.query.db import QueryError
from rvw.soc.verify import verify, table


def register(sub):
    p = sub.add_parser('verify', help='generate SoC checks and run bound verification consumers')
    p.add_argument('source')
    p.add_argument('--out', required=True)
    p.add_argument('--manifest')
    p.add_argument('--timeout', type=float, default=120)
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=run)


def run(args):
    try:
        result = verify(args.source, args.out, args.manifest, args.timeout)
        print(json.dumps(result) if args.json else table(result))
        return {'pass':0, 'fail':1, 'inconclusive':3}[result['status']]
    except (OSError, ValueError, TypeError, KeyError, QueryError) as exc:
        print(json.dumps(dict(status='error', error=str(exc))))
        return 2


def mcp_tools():
    from rvw.mcp.spec import ToolSpec, schema
    return [ToolSpec('soc_verify', 'Generate SoC checks and run bound consumers. Missing evidence remains inconclusive.',
        schema({'source':{'type':'string'}, 'out':{'type':'string'}, 'manifest':{'type':'string'},
                'timeout':{'type':'number'}}, ['source','out']), verify, long=True, side_effects='writes-files', native_tools=())]
