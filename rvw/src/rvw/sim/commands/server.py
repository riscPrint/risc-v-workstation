"""Local service for an existing native JSONL adapter."""
import json
import signal
from rvw.sim.server import request, serve


def register(sub):
    parser = sub.add_parser('server', help='serve one native adapter through a local Unix socket')
    parser.add_argument('--socket', required=True)
    parser.add_argument('--command', required=True, help='JSON argument array ending in serve')
    parser.add_argument('--timeout', type=float, default=600)
    parser.set_defaults(func=run)


def run(args):
    def stop(signum, frame):
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGHUP, stop)
    try:
        return serve(args.socket, json.loads(args.command), args.timeout)
    except (OSError, ValueError) as error:
        print(json.dumps({'error': str(error)}))
        return 2


def mcp_tools():
    from rvw.mcp.spec import ToolSpec, schema
    return [ToolSpec('sim_server_request', 'Submit a serial job to a running local native simulation server. An op:shutdown request closes it.',
                    schema({'endpoint': {'type': 'string'}, 'job': {'type': 'object'},
                            'timeout': {'type': 'number', 'exclusiveMinimum': 0}}, ['endpoint', 'job']), request, long=True, side_effects="writes-files", native_tools=(), result_envelope=True)]
