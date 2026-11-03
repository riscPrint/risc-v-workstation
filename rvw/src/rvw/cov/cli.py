"""Agent-friendly coverage commands, auto-discovered by rvw."""
import json
import os
import tempfile
from pathlib import Path
import sqlite3
import subprocess

from rvw.common import jsonout
from rvw.results import write_json
from rvw.results.generation import publish

from . import code, captured
from rvw.common.capture import CaptureError
from rvw.common.proc import run_group

ERRORS = (ValueError, OSError, KeyError, IndexError, TypeError, StopIteration, sqlite3.Error,
          subprocess.CalledProcessError, subprocess.TimeoutExpired)


def error_json(exc):
    return {"schema": "rvw.coverage-error/1", "error": str(exc),
            **({'status': exc.status, 'cause': exc.cause} if isinstance(exc, CaptureError) else {})}


def emit(args, obj):
    if args.json:
        # Serialized fully first: a JsonOutputError (a ValueError) leaves stdout empty, and execute
        # then writes the one error document.
        jsonout.write(obj, indent=2, sort_keys=True)
    else:
        print(obj['schema'])
        if 'summary' in obj:
            print(json.dumps(obj['summary'], sort_keys=True))
            for module, stats in sorted(obj['modules'].items(), key=lambda kv: (kv[1]['percent'] or 0, kv[0])):
                print(f"{module}: {stats['hit']}/{stats['eligible']} points, {stats['excluded']} excluded")
        elif 'selected' in obj:
            print('Selected: ' + ', '.join(obj['selected']))
        elif 'tests' in obj and isinstance(obj['tests'], list):
            print('\n'.join(obj['tests']))
        elif 'groups' in obj:
            for name, g in obj['groups'].items():
                print(f"{name}: {g['observed_bins']} observed bins, {len(g['holes'])} holes")
        elif 'counts' in obj:
            print(json.dumps(obj['counts'], sort_keys=True))
        elif obj['schema'].startswith('rvw.coverage-exclusions/'):
            print(f"{sum(p['unreachable'] for p in obj['points'])} proven unreachable points")
        else:
            print(f"{len(obj.get('points', []))} points")
        if getattr(args, 'out', None):
            print(f'Wrote {args.out}')


def write_bytes(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


@captured.command
def calculate(args):
    """Calculate a command result, including requested output artifacts, for CLI and MCP."""
    if args.cov_command == 'merge':
        result = code.merge(args.inputs, args.source_root, args.source_map, args.hgldd, args.revision, args.scala_root)
        if args.dat:
            originals = [p for _, p, _ in code.inputs(args.inputs)]
            files = [str(captured.file(p).copy) for p in originals]
            output = Path(args.dat).resolve()
            if output in [Path(f).resolve() for f in originals]:
                raise ValueError('--dat must not overwrite an input')
            staged_dat = captured.current().root.parent / 'merged.dat'
            tool = captured.tool('verilator_coverage')
            completed = run_group([str(tool.path), '--write', str(staged_dat), *files], capture=True, timeout=60, env=captured.environment())
            if completed.returncode:
                raise ValueError(f'verilator_coverage failed ({completed.returncode})')
            exported = captured.file(staged_dat)
            official = code.read_counts(exported.copy)
            if {p['id']: p['count'] for p in result['points']} != official:
                raise ValueError('merged counts differ from verilator_coverage; refusing inconsistent output')
            captured.verify_tools()
            write_bytes(output, exported.copy.read_bytes())
    elif args.cov_command == 'isa-diff':
        from .isa import spec_diff
        result = spec_diff(args.before, args.after, args.old_source_root, args.source_root)
    elif args.cov_command == 'isa-check':
        from .isa import check_manifest
        result = check_manifest(args.manifest)
    elif args.cov_command == 'rtl':
        from .rtl import sample
        result = sample(args.config, args.traces)
    elif args.cov_command == 'functional':
        from .functional import functional
        result = functional(args.traces, args.config, args.platform, args.manifest, args.source_root)
    elif args.cov_command == 'prove':
        from .proof import prove
        result = prove(args.config, args.database, args.work_dir, args.timeout)
    elif args.cov_command == 'mutate':
        from .mutation import mutate
        roles = {}
        if args.test is not None:
            roles['detection_tests'] = args.test
        if args.equivalence_test is not None:
            roles['equivalence_tests'] = args.equivalence_test
        result = mutate(args.project, args.run, args.timeout, args.jobs, args.baseline,
                        **roles)
    else:
        data = json.loads(captured.read_text(args.database))
        if data.get('schema') != 'rvw.coverage/1':
            raise ValueError('expected rvw.coverage/1 database')
        if args.cov_command == 'report':
            result = code.report(data, args.exclusions)
            if args.annotate:
                if 'changed' in result['sources'].values():
                    raise ValueError('cannot annotate changed RTL; restore the covered source or recollect coverage')
                target = Path(args.annotate).absolute()
                def build_annotations(directory):
                    by_file = {}
                    for p in result['never_hit']:
                        by_file.setdefault(p['fields'].get('f', 'unknown'), []).append(p)
                    for file, points in by_file.items():
                        # JSONL annotations cannot overwrite or escape to the original source tree.
                        name = code.sha256(file.encode()).hexdigest()[:16] + '.jsonl'
                        (directory / name).write_text(''.join(json.dumps(p) + '\n' for p in points))
                        path = Path(data.get('sources', {}).get(file, {}).get('path') or Path(data['source_root']) / file)
                        if path.is_file():
                            holes = {int(p['fields'].get('l', 0)) for p in points}
                            (directory / name.replace('.jsonl', '.txt')).write_text(f'{file}\n' + ''.join(
                                f"{'NEVER' if n in holes else '     '} {n:6d} {line}\n"
                                for n, line in enumerate(captured.read_text(path, errors='replace').splitlines(), 1)))
                    result['annotations'] = {'store': str(target),
                                             'generation': directory.name.removeprefix('.building-')}
                    captured.verify_tools()
                    (directory / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
                publish(target, build_annotations)
        elif args.cov_command == 'rank':
            result = code.rank(data, args.exact)
        else:
            result = code.select(data, args.diff, args.repo)
    captured.verify_tools()
    result.setdefault("capture", captured.current().record())
    result["cache_key"] = None
    if getattr(args, "out", None):
        write_json(args.out, result)
    return result


def execute(args):
    try:
        result = calculate(args)
        emit(args, result)
        if result.get('status') == 'inconclusive':
            return 3
        return 1 if result.get('run_exit_code', 0) or result.get('counts', {}).get('error') else 0
    except ERRORS as exc:
        if args.json:
            jsonout.write(error_json(exc))
        else:
            print(f'coverage error: {exc}')
        return 3 if isinstance(exc, CaptureError) else 2


def register(subparsers):
    parser = subparsers.add_parser('cov', help='code, RVFI functional, formal and mutation coverage')
    sub = parser.add_subparsers(dest='cov_command', required=True)
    merge = sub.add_parser('merge', help='merge test=coverage.dat files or C1/C3 results')
    merge.add_argument('inputs', nargs='+')
    merge.add_argument('--source-root', default='.')
    merge.add_argument('--scala-root', help='resolve comment basenames to unique Scala files under this directory')
    merge.add_argument('--revision', help='BASE commit of raw coverage inputs, needed for safe change selection')
    merge.add_argument('--source-map', help='JSON explicit Verilog-range to Scala mapping')
    merge.add_argument('--hgldd', action='append', default=[], help='SpinalWaves HGLDD .dd file; repeatable')
    merge.add_argument('--dat', help='also write merged Verilator .dat')
    report = sub.add_parser('report', help='module, hierarchy, Scala locations and never-hit points')
    report.add_argument('database')
    report.add_argument('--exclusions')
    report.add_argument('--annotate', help='write never-hit point annotations as JSONL, one file per source')
    rank = sub.add_parser('rank', help='per-test contribution and deterministic greedy test set')
    rank.add_argument('database')
    rank.add_argument('--exact', action='store_true', help='prove minimum cardinality for at most 20 tests')
    select = sub.add_parser('select', help='select tests covering changed Scala source')
    select.add_argument('database')
    select.add_argument('--diff', required=True)
    select.add_argument('--repo', default='.')
    isa_diff = sub.add_parser('isa-diff', help='compare pinned ISA proposals without adopting changes')
    isa_diff.add_argument('before')
    isa_diff.add_argument('after')
    isa_diff.add_argument('--old-source-root', required=True)
    isa_diff.add_argument('--source-root', required=True)
    isa_check = sub.add_parser('isa-check', help='validate core-owned ISA declarations')
    isa_check.add_argument('manifest')
    functional = sub.add_parser('functional', help='merge C2 traces into declarative cover groups')
    functional.add_argument('traces', nargs='+')
    functional.add_argument('--manifest', help='core-owned rvw.isa/1 file')
    functional.add_argument('--source-root', help='local pinned riscv-opcodes checkout')
    functional.add_argument('--config', help='JSON coverage plan; adds or replaces named default groups')
    functional.add_argument('--platform', help="platform name or JSON (as rvw cosim) for the RVFI address convention; "
                            "default: the bundled platform named by the trace header's core")
    rtl = sub.add_parser('rtl', help='sample typed RTL bins and bounded sequences')
    rtl.add_argument('traces', nargs='+')
    rtl.add_argument('--config', required=True, help='rvw.rtl-plan/1 JSON plan')
    prove = sub.add_parser('prove', help='bounded cover and unbounded proof for chosen coverage points')
    prove.add_argument('database')
    prove.add_argument('--config', required=True)
    prove.add_argument('--work-dir', required=True, help='fresh output directory')
    prove.add_argument('--timeout', type=int, default=60)
    mutate = sub.add_parser('mutate', help='run/report an MCY project; heavy runs must use with-lock.sh boom')
    mutate.add_argument('project')
    mutate.add_argument('--run', action='store_true')
    mutate.add_argument('--baseline', help='bash script checking the unmutated test suite')
    mutate.add_argument('--timeout', type=int, default=120)
    mutate.add_argument('--jobs', type=int, default=1)
    mutate.add_argument('--test', action='append', help='detection test name; repeatable, defaults to saved roles on inspection or all non-equivalence tests on a fresh run')
    mutate.add_argument('--equivalence-test', action='append', help='equivalence test name; repeatable, defaults to saved roles on inspection or none on a fresh run; FAIL is not a kill')
    for command in (merge, report, rank, select, functional, rtl, prove, mutate, isa_check, isa_diff):
        command.add_argument('--json', action='store_true')
        command.add_argument('--out', help='write structured JSON result')
        command.set_defaults(func=execute)


def execute_json(action: str, **options) -> dict:
    from argparse import Namespace
    defaults = dict(inputs=[], source_root=".", source_map=None, hgldd=[], revision=None,
                    scala_root=None, dat=None, traces=[], config=None, database=None,
                    work_dir=None, timeout=60 if action == "prove" else 120, project=None,
                    run=False, jobs=1, baseline=None, test=None, equivalence_test=None,
                    exclusions=None, annotate=None, exact=False, diff=None, repo=".", out=None,
                    platform=None, manifest=None, before=None, after=None, old_source_root=None)
    unknown = options.keys() - defaults.keys()
    if unknown:
        raise TypeError(f"unknown options: {sorted(unknown)}")
    defaults.update(options)
    # Errors propagate: the MCP worker turns them into a ToolError, so the job fails with the
    # message (C7) instead of returning an error object as a successful result.
    return calculate(Namespace(cov_command=action, **defaults))
