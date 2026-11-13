"""Format exchange command and MCP endpoint."""
import json
from pathlib import Path



def convert(*args, **kwargs):
    from .exchange import convert as implementation
    return implementation(*args, **kwargs)


def register(subs):
    parser = subs.add_parser('exchange', help='exchange C2, RVVI-TEXT 0.5 and Spike commit logs')
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--from', dest='source_format', required=True, choices=['c2', 'rvvi', 'spike'])
    parser.add_argument('--to', dest='target_format', required=True, choices=['c2', 'rvvi', 'spike', 'observations'])
    parser.add_argument('--json', action='store_true')
    parser.set_defaults(func=run)


def execute_json(**options):
    try:
        return convert(**options)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return dict(schema='rvw.cosim-exchange/1', status='error', message=str(exc))


def run(args):
    result = execute_json(source=args.source, out=args.out, source_format=args.source_format,
                          target_format=args.target_format)
    print(json.dumps(result))
    return 2 if result['status'] == 'error' else 0


def mcp_tools():
    from rvw.mcp.spec import ToolSpec, schema
    from rvw.mcp.worker import handler
    return [ToolSpec('cosim_exchange', 'Exchange C2 and RVVI-TEXT 0.5 or Spike commit logs. '
                     'Sparse logs produce observations only. No independent check is claimed.',
        schema(dict(source={'type': 'string'}, out={'type': 'string'},
                    source_format={'type': 'string', 'enum': ['c2', 'rvvi', 'spike']},
                    target_format={'type': 'string', 'enum': ['c2', 'rvvi', 'spike', 'observations']}),
               ['source', 'out', 'source_format', 'target_format']),
        handler('rvw.cosim.exchange_cli'), long=True,
        side_effects='long-running; writes converted trace under out', native_tools=(),
        )]
