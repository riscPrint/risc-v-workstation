"""rvw fault: sites, plan, run and report for fault injection campaigns."""
import json
import shlex
from pathlib import Path

from . import campaign


def register(subparsers):
    parser = subparsers.add_parser('fault', help='fault injection campaigns (stuck-at, transient) against C2')
    sub = parser.add_subparsers(dest='fault_command', required=True)
    s = sub.add_parser('sites', help='list register fault sites from a design database')
    _site_args(s)
    s.set_defaults(func=_sites)
    p = sub.add_parser('plan', help='write a seeded fault plan with its population')
    _site_args(p)
    p.add_argument('--kinds', default='stuck0,stuck1,flip')
    p.add_argument('--window', default='0:1000', help='START:END injection cycles')
    p.add_argument('--samples', type=int, default=100)
    p.add_argument('--seed', type=int, default=1)
    p.add_argument('--duration', type=int, help='cycles a stuck-at fault holds (default: permanent)')
    p.add_argument('--out', required=True, type=Path)
    p.set_defaults(func=_plan)
    r = sub.add_parser('run', help='run golden and faulty simulations through the core adapter and classify')
    r.add_argument('--plan', required=True, type=Path)
    r.add_argument('--adapter', required=True, help='adapter command (shell words), called with run --fault FILE')
    r.add_argument('--elf', required=True, type=Path)
    r.add_argument('--out', required=True, type=Path)
    r.add_argument('--jobs', type=int, default=1)
    r.add_argument('--max-cycles', type=int)
    r.add_argument('--timeout', type=float, default=600)
    r.add_argument('--detections', type=Path, help='JSON: {"mechanisms": [...], "status": {"fail": "self-test"}}')
    r.add_argument('--watchdog', action='store_true', help='count timeouts as detected (a declared watchdog)')
    r.set_defaults(func=_run)
    rep = sub.add_parser('report', help='recompute the report of a finished campaign directory')
    rep.add_argument('directory', type=Path)
    rep.set_defaults(func=_report)


def _site_args(parser):
    parser.add_argument('--db', required=True, type=Path, help='design database (rvw.designdb)')
    parser.add_argument('--include', action='append', help='path glob (repeatable; default all)')
    parser.add_argument('--exclude', action='append', default=[])
    parser.add_argument('--generated', action='store_true', help='include generated registers')


def _site_list(args):
    return campaign.sites(args.db, include=args.include or ['*'], exclude=args.exclude, generated=args.generated)


def _sites(args):
    try:
        found = _site_list(args)
    except (OSError, ValueError) as exc:
        print(json.dumps({'status': 'error', 'reason': str(exc)}))
        return 2
    print(json.dumps({'sites': found, 'bits': sum(s['width'] for s in found)}, indent=2))
    return 0 if found else 3


def _plan(args):
    import hashlib
    try:
        start, end = (int(v, 0) for v in args.window.split(':'))
        data = campaign.plan(_site_list(args), kinds=tuple(k for k in args.kinds.split(',') if k),
                             window=(start, end), samples=args.samples, seed=args.seed, duration=args.duration,
                             db_sha256=hashlib.sha256(args.db.read_bytes()).hexdigest())
    except (OSError, ValueError) as exc:
        print(json.dumps({'status': 'error', 'reason': str(exc)}))
        return 2
    args.out.write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps({'faults': len(data['faults']), 'population_total': data['population_total'],
                      'sampling': data['sampling'], 'plan': str(args.out)}))
    return 0


def _run(args):
    from . import api
    try:
        summary = api.run(args.plan, args.adapter, args.elf, args.out, jobs=args.jobs, max_cycles=args.max_cycles,
                          timeout=args.timeout, detections=args.detections, watchdog=args.watchdog)
    except (OSError, ValueError) as exc:
        print(json.dumps({'status': 'inconclusive', 'reason': str(exc)}))
        return 3
    print(json.dumps({k: summary[k] for k in ('counts', 'diagnostic_coverage', 'diagnostic_coverage_95', 'injected')}))
    return 1 if summary['counts']['silent_corruption'] else (3 if summary['unresolved'] else 0)


def _report(args):
    from . import api
    try:
        summary = api.report(args.directory)
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({'status': 'error', 'reason': str(exc)}))
        return 2
    print(json.dumps(summary, indent=2))
    return 0
