"""Top-level UVM bench commands."""
import json
from pathlib import Path
from . import flow


def command(a):
    try:
        if a.action == 'features':
            from .features import table, markdown
            report = table(a.results)
            print(markdown(report))
            return 0
        if a.action == 'build':
            report = flow.build(a.manifest, a.out, archive=a.archive, verilator=a.verilator, timeout=a.timeout)
        elif a.action == 'list':
            report = {'tests': flow.load(a.manifest)['tests']}
        elif a.action == 'run':
            report = flow.run(a.build, a.out, test=a.test, seed=a.seed, timeout=a.timeout)
        elif a.action == 'regress':
            report = flow.regress(a.build, a.out, tests=a.tests, seeds=a.seeds, timeout=a.timeout)
        else:
            report = flow.coverage_merge(a.inputs, a.out, tool=a.tool, timeout=a.timeout)
        print(json.dumps(report))
        return 0 if report.get('status', 'pass') == 'pass' and all(t['status'] == 'pass' for t in report.get('tests', []) if isinstance(t, dict)) else 2
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({'error': str(exc)}))
        return 2


def register(sub):
    p = sub.add_parser('uvm', help='build and run project-owned UVM benches')
    commands = p.add_subparsers(dest='action', required=True)
    f = commands.add_parser('features', help='derive engine feature table from C3 conformance results')
    f.add_argument('results', type=Path)
    f.set_defaults(func=command)
    for name in ('build', 'run', 'list', 'regress', 'coverage-merge'):
        c = commands.add_parser(name, help={'build': 'compile a pinned Accellera bench', 'run': 'run one declared test', 'list': 'list declared tests', 'regress': 'run test and seed matrix as C3', 'coverage-merge': 'merge native Verilator coverage'}[name])
        if name in ('build', 'list'):
            c.add_argument('manifest', type=Path)
        if name != 'list':
            c.add_argument('--out', type=Path, required=True)
            c.add_argument('--timeout', type=float, default=600)
        if name == 'build':
            c.add_argument('--archive', type=Path)
            c.add_argument('--verilator', default='verilator')
        if name in ('run', 'regress'):
            c.add_argument('--build', type=Path, required=True)
        if name == 'run':
            c.add_argument('--test', required=True)
            c.add_argument('--seed', type=int, default=1)
        if name == 'regress':
            c.add_argument('--tests', nargs='+')
            c.add_argument('--seeds', type=int, nargs='+', default=[1])
        if name == 'coverage-merge':
            c.add_argument('inputs', type=Path, nargs='+')
            c.add_argument('--tool', default='verilator_coverage')
        c.set_defaults(func=command)
