"""Select generated suite families from explicit project capabilities."""
import json
from pathlib import Path

from rvw.mcp.spec import ToolSpec, schema


def plan(features, catalog=None):
    """Return requirements and exclusions. This does not run or qualify a DUT."""
    declared = json.loads(Path(features).read_text())
    if declared.get('schema') != 'rvw.regress-features/1':
        raise ValueError('expected rvw.regress-features/1')
    supported = declared.get('capabilities', [])
    if not isinstance(supported, list) or not all(isinstance(x, str) for x in supported):
        raise ValueError('capabilities must be an explicit list of strings')
    supported = set(supported)
    if 'isa' in declared:
        from rvw.cov.isa import extensions
        xlen, names = extensions(declared['isa'])
        supported.add(f'xlen:{xlen}')
        supported.update('ext:' + name for name in names)
    modes = declared.get('privilege_modes', '')
    if modes not in ('', 'M', 'MU', 'MSU'):
        raise ValueError('privilege_modes must be M, MU or MSU')
    supported.update('mode:' + mode for mode in modes)
    for mode in declared.get('satp_modes', []):
        if mode not in ('sv32', 'sv39', 'sv48', 'sv57'):
            raise ValueError('unknown satp mode')
        supported.add('satp:' + mode)
    pmp = declared.get('pmp_regions', 0)
    harts = declared.get('harts', 1)
    if type(pmp) is not int or pmp < 0 or type(harts) is not int or harts < 1:
        raise ValueError('invalid PMP or hart count')
    if pmp:
        supported.add('pmp')
    if pmp >= 4:
        supported.add('pmp:4')
    if pmp >= 8:
        supported.add('pmp:8')
    if harts >= 2:
        supported.add('harts:2')
    for bit in declared.get('irq_inputs', []):
        if bit in (3, 7, 9, 11):
            supported.add({3: 'irq:msip', 7: 'irq:mtip', 9: 'irq:seip', 11: 'irq:meip'}[bit])
    if len([x for x in supported if x.startswith('xlen:')]) > 1:
        raise ValueError('contradictory XLEN declarations')
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
    choice = p.add_mutually_exclusive_group(required=True)
    choice.add_argument('--features', type=Path, help='project-owned feature declaration')
    choice.add_argument('--act4', type=Path, help='project-owned ACT4 profile')
    p.add_argument('--catalog', type=Path, help='project-owned suite requirement catalog')
    p.add_argument('--json', action='store_true')
    def run(args):
        try:
            if args.act4:
                from rvw.regress.act4 import selection
                result = selection(args.act4)
            else:
                result = plan(args.features, args.catalog)
        except (ValueError, OSError, KeyError) as exc:
            import sys
            print(f'rvw regress plan: {exc}', file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(result))
        else:
            if args.act4:
                print('all compatible tests (UDB metadata)' if result['test_selection'] == 'all-applicable' else ', '.join(result['extensions']))
            for row in result.get('suites', []):
                print(f"{row['name']}: {'applicable' if row['applicable'] else 'excluded'} ({row['reason']})")
        return 0
    p.set_defaults(func=run)


def mcp_tools():
    return [ToolSpec('regress_plan', 'List generated suite applicability from explicit project capabilities. Missing declarations exclude suites. No DUT evidence is earned.',
                     schema({'features': {'type': 'string'}, 'catalog': {'type': 'string'}}, ['features']),
                     plan, annotations={'readOnlyHint': True}, side_effects='read-only', native_tools=())]
