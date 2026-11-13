"""Compile pinned Sail state slices without editing shared command registries."""
import json
from pathlib import Path
import sys

from rvw.mcp.spec import ToolError, ToolSpec, schema


def register(subparsers):
    from rvw.formal.sail_state_slices import main
    command = subparsers.add_parser('sail-state', help='compile pinned Sail FP, CSR and privileged entry slices')
    for name in ('model', 'compiler', 'out'):
        command.add_argument('--' + name, required=True)
    command.add_argument('--json', action='store_true')
    command.set_defaults(func=main)


def run(job, **args):
    argv = [sys.executable, '-m', 'rvw', 'formal', 'sail-state']
    for name, value in args.items():
        argv += ['--' + name, str(value)]
    code = job.run(argv)
    if code:
        raise ToolError('Sail state generation failed', {'exit_code': code, 'log_tail': job.tail(30)})
    result = json.loads((Path(args['out']) / 'manifest.json').read_text())
    if result.get('schema') != 'rvw.sail-state-slices/1' or result.get('status') != 'generated':
        raise ToolError('invalid Sail state manifest')
    return result


def mcp_tools():
    return [ToolSpec('formal_sail_state',
                     'Generate pinned Sail FP sign results, CSR intents and privileged entry decisions. Excludes full machine state.',
                     schema({name: {'type': 'string'} for name in ('model', 'compiler', 'out')},
                            ['model', 'compiler', 'out']), run, long=True)]
