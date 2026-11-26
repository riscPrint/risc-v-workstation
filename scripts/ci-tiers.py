#!/usr/bin/env python3
"""Run inventory-backed CI tiers. Native presence is not qualification."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
TIERS = json.loads((ROOT / 'scripts/ci-tiers.json').read_text())
SCALA = ['SpinalWaves/spinalwaves', 'SpinalTrace/spinaltrace', 'SpinalDB/spinaldb',
         'SpinalChecks', 'SpinalKonata', 'SpinalBlocks/spinalblocks', 'RiscvSim',
         'SpinalProbes', 'SpinalSoc']


def emit(text):
    print(text, flush=True)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as stream:
            stream.write(text + '\n')


def tool_status(tier):
    if not TIERS[tier]['tools']:
        emit('- Optional native tools: none.')
        return []
    from rvw.doctor.inventory import report
    records = {r['name']: r for r in report()}
    missing = []
    for name in TIERS[tier]['tools']:
        row = records[name]
        if row['status'] != 'installed':
            missing.append(name)
            emit(f"- SKIP tool {name}: absent; {row['install_command']}. Runtime NOT RUN.")
        else:
            emit(f'- Tool {name}: present. Presence only.')
    if not TIERS[tier]['tools']:
        emit('- Optional native tools: none.')
    return missing


def commands(tier, component):
    py = sys.executable
    pytest = [py, '-m', 'pytest']
    if tier in ('fast', 'native-light') or component == 'python':
        args = ['rvw/tests', '--strict-markers', '-q', '-ra', '--durations=20']
        if tier == 'fast':
            args += ['-m', 'fast']
        else:
            args += ['-p', 'ci_plugin']
        return [('python', ROOT, pytest + args + ['--junitxml=ci-results.xml'])]
    if component == 'scala':
        selected = os.environ.get('CI_SCALA_PROJECT')
        projects = [selected] if selected else SCALA
        if any(p not in SCALA for p in projects):
            raise ValueError('unknown Scala CI project')
        return [(p, ROOT / p, ['sbt', '-batch', '-J-XX:ActiveProcessorCount=2',
                                 'spinalblocks/test' if p.startswith('SpinalBlocks/') else 'riscvsim/test' if p == 'RiscvSim' else 'test', *(['inputs/test'] if p == 'SpinalKonata' else [])]) for p in projects]
    if component == 'rust':
        return [('rust', ROOT / 'SpinalTrace', ['cargo', 'test', '--locked', '-p', 'spinaltrace-rs'])]
    if component == 'javascript':
        return [('javascript', ROOT / 'vscode', ['bash', '-e', '-c', 'npm ci; npm run typecheck; npm run build; npm test'])]
    if component == 'components':
        return [('ComponentSims', ROOT, pytest + ['ComponentSims/tests', '-q', '-ra', '--junitxml=component-results.xml'])]
    raise ValueError('unknown tier component')


def needs_python_report(tier, component):
    return tier in ('fast', 'native-light') or (tier == 'nightly' and component == 'python')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tier', choices=TIERS, required=True)
    parser.add_argument('--component', default='python', choices=['python', 'scala', 'rust', 'javascript', 'components'])
    parser.add_argument('--plan', action='store_true')
    parser.add_argument('--tools-only', action='store_true')
    args = parser.parse_args()
    if args.tools_only:
        tool_status(args.tier)
        return 0
    if args.tier == 'examples':
        plan = [('examples', ROOT, [sys.executable, 'scripts/ci-examples.py'])]
    else:
        plan = commands(args.tier, args.component)
    if args.plan:
        print(json.dumps({'tools': TIERS[args.tier]['tools'], 'commands': [(n, str(p.relative_to(ROOT)), c) for n,p,c in plan]}, indent=2))
        return 0
    from rvw.common.proc import run_group
    os.environ['RVW_CI_TIER'] = args.tier
    os.environ['PYTHONPATH'] = str(ROOT / 'scripts')
    emit(f'## CI tier: {args.tier}; component: {args.component}')
    missing = tool_status(args.tier)
    if args.tier == 'examples' and missing:
        emit('Examples: 0 passed, 0 failed, 1 skipped. Required tools are absent.')
        return 0
    failed = False
    for name, cwd, command in plan:
        if not shutil.which(command[0]):
            emit(f'{name}: 0 passed, 0 failed, 1 skipped. Executable {command[0]} is absent.')
            continue
        lock = 'sbt' if command[0] == 'sbt' else 'suite'
        argv = [str(ROOT / 'scripts/with-lock.sh'), lock, 'nice', '-n', '10', *command]
        emit(f'### {name}')
        result = run_group(argv, cwd=cwd, timeout=TIERS[args.tier]['seconds'], capture=True)
        (ROOT / ('ci-' + name.replace('/', '-') + '.log')).write_text(result.stdout + result.stderr)
        print(result.stdout, end='')
        print(result.stderr, end='', file=sys.stderr)
        failed |= result.returncode != 0 or result.timed_out
        emit(f'{name}: exit {result.returncode}; timeout={result.timed_out}.')
        if args.component != 'python' and args.tier == 'nightly':
            import runpy
            summary = runpy.run_path(str(ROOT / 'scripts/ci-test-summary.py'))
            reports = list(cwd.glob('**/target/test-reports/*.xml')) if args.component == 'scala' else [ROOT / 'component-results.xml'] if args.component == 'components' else []
            for report in reports:
                if not report.is_file():
                    emit(f'{name}: test report missing; counts unavailable.')
                    failed = True
                    continue
                text, code = summary['summarize'](report)
                emit(text + '\n' + summary['details'](report))
                failed |= bool(code)
            if not reports:
                emit(summary['language_details'](result.stdout, name))
        if needs_python_report(args.tier, args.component):
            report = ROOT / 'ci-results.xml'
            if report.exists():
                import runpy
                summary = runpy.run_path(str(ROOT / 'scripts/ci-test-summary.py'))
                text, code = summary['summarize'](report)
                text += '\n' + summary['details'](report)
                emit(text)
                failed |= bool(code)
            else:
                emit('Test report absent. Counts unavailable; job failed.')
                failed = True
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
