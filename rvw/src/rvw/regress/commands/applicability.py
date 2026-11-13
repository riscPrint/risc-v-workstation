"""Select generated suite families from explicit project capabilities."""
import json
from pathlib import Path

from rvw.mcp.spec import ToolSpec, schema


def plan(features, catalog=None):
    """Return requirements and exclusions. This does not run or qualify a DUT."""
    declared = json.loads(Path(features).read_text())
    if declared.get('schema') != 'rvw.regress-features/1':
        raise ValueError('expected rvw.regress-features/1')
    supported = declared.get('capabilities')
    if not isinstance(supported, list) or not all(isinstance(x, str) for x in supported):
        raise ValueError('capabilities must be an explicit list of strings')
    supported = set(supported)
    source = Path(catalog) if catalog else Path(__file__).parents[1] / 'suite_requirements.json'
    suites = json.loads(source.read_text())
    rows = []
    names = set()
    for suite in suites:
        name, needs = suite['name'], suite['requires']
        if name in names or not isinstance(needs, list) or not all(isinstance(x, str) for x in needs):
            raise ValueError('invalid or duplicate suite requirements')
        names.add(name)
        missing = sorted(set(needs) - supported)
        rows.append(dict(suite, applicable=not missing, missing=missing,
                         reason='all requirements declared' if not missing else 'missing: ' + ', '.join(missing)))
    return dict(schema='rvw.regress-plan/1', features=str(Path(features).resolve()),
                capabilities=sorted(supported), suites=rows,
                applicable=sum(r['applicable'] for r in rows), total=len(rows),
                evidence='selection only; no DUT execution')


def register(commands):
    p = commands.add_parser('plan', help='list applicable generated suites and missing features')
    p.add_argument('--features', type=Path, required=True, help='project-owned feature declaration')
    p.add_argument('--catalog', type=Path, help='project-owned suite requirement catalog')
    p.add_argument('--json', action='store_true')
    def run(args):
        try:
            result = plan(args.features, args.catalog)
        except (ValueError, OSError, KeyError) as exc:
            import sys
            print(f'rvw regress plan: {exc}', file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(result))
        else:
            for row in result['suites']:
                print(f"{row['name']}: {'applicable' if row['applicable'] else 'excluded'} ({row['reason']})")
        return 0
    p.set_defaults(func=run)


def mcp_tools():
    return [ToolSpec('regress_plan', 'List generated suite applicability from explicit project capabilities. Missing declarations exclude suites. No DUT evidence is earned.',
                     schema({'features': {'type': 'string'}, 'catalog': {'type': 'string'}}, ['features']),
                     plan, annotations={'readOnlyHint': True})]
