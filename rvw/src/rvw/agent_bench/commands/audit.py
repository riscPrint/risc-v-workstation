"""Read-only native evidence admission."""
import json
from pathlib import Path
from rvw.agent_bench.audit import audit_run
from rvw.mcp.spec import ToolSpec, schema


def register(sub):
    p = sub.add_parser('audit-run', help='Check native C1/C2 identity, completion and required artifact presence')
    p.add_argument('--run-dir', type=Path, required=True)
    p.add_argument('--elf', type=Path, required=True)
    p.add_argument('--expected', type=Path, help='Evaluator task identity JSON')
    p.add_argument('--require', action='append', default=[])
    p.set_defaults(func=execute)


def execute(args):
    result = audit_run(args.run_dir, args.elf, args.require,
                       json.loads(args.expected.read_text()) if args.expected else None)
    print(json.dumps(result, indent=2))
    return 0 if result['status'] == 'evidence_consistent' else 3


def mcp_tools():
    string = {'type': 'string'}
    return [ToolSpec('agent_bench_audit_run', 'Check actual C1/C2 identities, ELF hash and run end before using evidence. '
                     'Required artifact checks cover presence only. Cannot grant repair credit.',
                     schema({'run_dir': string, 'elf': string,
                             'required_artifacts': {'type': 'array', 'items': string},
                             'expected_identity': {'type': 'object'}}, ['run_dir', 'elf']),
                     audit_run, annotations={'readOnlyHint': True}, side_effects='read-only', native_tools=())]
