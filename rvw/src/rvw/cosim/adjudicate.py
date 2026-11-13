"""Run independent references without converting disagreement to a pass."""
import json
from pathlib import Path


def adjudicate(results):
    if set(results) != {'spike', 'sail'}:
        raise ValueError('adjudication requires Spike and Sail reports')
    report = dict(schema='rvw.cosim-adjudication/1', references=results,
                  matched_references=[name for name, row in results.items() if row['status'] == 'match'])
    identities = [r.get('reproduction', {}) for r in results.values()]
    for field in ('elf_sha256', 'trace_sha256', 'platform_sha256'):
        if any(not row.get(field) for row in identities) or identities[0][field] != identities[1][field]:
            return dict(report, status='inconclusive', cause='reference_input_identity_missing_or_different')
    if any(r['status'] not in ('match', 'mismatch') for r in results.values()):
        return dict(report, status='inconclusive', cause='reference_not_conclusive')
    failed = {name: r for name, r in results.items() if r['status'] == 'mismatch'}
    if not failed:
        counts = [r['instructions'] for r in results.values()]
        complete = all(r.get('trace_complete') and not r.get('uncompared_instructions', 0) for r in results.values())
        return dict(report, status='match' if complete and counts[0] == counts[1] else 'inconclusive',
                    scope='common complete compared trace' if complete and counts[0] == counts[1] else 'reference coverage differs')
    boundary = min(r['mismatch']['instruction_index'] for r in failed.values())
    at = {name: r for name, r in failed.items() if r['mismatch']['instruction_index'] == boundary}
    follows = [name for name, r in results.items() if name not in at and r['instructions'] > boundary]
    disagreements = bool(follows)
    if len(at) == 2:
        a, b = [r['mismatch'] for r in at.values()]
        fields = set(a['differences']) | set(b['differences'])
        def expected(m, key):
            return m['differences'][key]['expected'] if key in m['differences'] else m.get('actual', {}).get(key)
        disagreements = any(expected(a, key) != expected(b, key) for key in fields)
    return dict(report, status='disagreement' if disagreements else 'mismatch',
                first_boundary=boundary, dut_matches_at_boundary=follows,
                scope='first reported instruction boundary; original reports retained')


def execute_json(**options):
    from .cli import execute_json as check
    return adjudicate({model: check('check', model=model, **options) for model in ('spike', 'sail')})


def register(subs):
    cmd = subs.add_parser('adjudicate', help='compare DUT with Spike and Sail in one flow')
    for name in ('elf', 'trace'):
        cmd.add_argument('--'+name, type=Path, required=True)
    cmd.add_argument('--core')
    cmd.add_argument('--platform', type=Path)
    cmd.add_argument('--sail-config', type=Path)
    cmd.add_argument('--timeout', type=float, default=120)
    cmd.add_argument('--strict', action='store_true')
    cmd.add_argument('--json', action='store_true')
    cmd.set_defaults(func=run)


def run(args):
    options = {key: getattr(args, key) for key in ('elf', 'trace', 'core', 'platform', 'sail_config', 'timeout', 'strict')}
    options['project'] = getattr(args, 'project', None)
    result = execute_json(**options)
    print(json.dumps(result))
    return {'match': 0, 'mismatch': 1, 'disagreement': 1, 'inconclusive': 3}[result['status']]


def mcp_tools():
    from rvw.mcp.spec import ToolSpec, schema
    from rvw.mcp.worker import handler
    properties = {key: {'type': 'string'} for key in ('elf', 'trace', 'core', 'platform', 'project', 'sail_config')}
    properties.update(timeout={'type': 'number', 'exclusiveMinimum': 0, 'default': 120}, strict={'type': 'boolean', 'default': False})
    return [ToolSpec('cosim_adjudicate', 'Check a DUT trace against Spike and Sail. Preserve both reports and identify which reference the DUT matches at a disagreement. No majority vote.',
                     schema(properties, ['elf', 'trace']), handler('rvw.cosim.adjudicate'), long=True)]
