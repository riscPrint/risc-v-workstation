"""Lint settings are project data. No backend suppression switches are accepted."""
import hashlib
import json
from pathlib import Path
import sqlite3
import re

from rvw.common.project import load_project, ProjectError
from rvw.query.db import run_on, QueryError
from . import native, structural


BACKENDS = ('verilator', 'verible', 'yosys', 'structural', 'rules')
BACKEND_OF = {'verilator': 'verilator', 'verible': 'verible', 'yosys': 'yosys', 'cdc': 'structural',
              'rdc': 'structural', 'lint': 'rules', 'sdc': 'sdc'}


def register(sub):
    p = sub.add_parser('lint', help='native lint and structural CDC/RDC inventory')
    p.add_argument('--settings', help='lint settings JSON; else project lint.settings')
    p.add_argument('--benchmark', help='same-input CDC qualification manifest')
    p.add_argument('--protocol', help='selected event-enable CDC safety manifest')
    p.add_argument('--out', help='fresh protocol result directory')
    p.add_argument('--depth', type=int, default=24)
    p.add_argument('--engine', default='smtbmc:yices')
    p.add_argument('--timeout', type=float, default=60)
    p.add_argument('--simulate', type=int, default=0, metavar='SAMPLES')
    p.add_argument('--seed', type=int, default=1)
    p.add_argument('--mode', choices=['bmc', 'prove'], default='bmc')
    p.add_argument('--emit', metavar='DIR', help='write CDC protocol assertions and obligations to a new directory')
    p.add_argument('--sarif', metavar='PATH', help='also write the findings as SARIF 2.1.0')
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=run)


def load(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    cfg = json.loads(data)
    allowed = {'schema', 'config', 'top', 'files', 'db', 'backends', 'waivers', 'timeout_s', 'intent', 'rules', 'sdc'}
    if not isinstance(cfg, dict) or set(cfg) - allowed or cfg.get('schema') != 'rvw.lint-settings/1':
        raise ValueError('invalid lint settings schema or keys')
    for key in ('config', 'top'):
        if not isinstance(cfg.get(key), str) or not cfg[key].strip():
            raise ValueError(f'{key} must be a nonempty string')
    backends = cfg.get('backends', ['verilator', 'verible', 'structural'])
    if (not isinstance(backends, list) or not backends or
            not all(isinstance(b, str) for b in backends) or len(set(backends)) != len(backends)
            or set(backends) - set(BACKENDS)):
        raise ValueError('backends must select ' + ', '.join(BACKENDS))
    files = cfg.get('files', [])
    if not isinstance(files, list) or not all(isinstance(f, str) and f for f in files):
        raise ValueError('files must be a list of paths')
    cfg['files'] = [str((path.parent / f).resolve()) for f in files]
    for file in cfg['files']:
        if not Path(file).is_file():
            raise ValueError(f'RTL file not found: {file}')
    if set(backends) & {'verilator', 'verible', 'yosys'} and not files:
        raise ValueError('native lint needs files')
    if set(backends) & {'structural', 'rules', 'sdc'} and not isinstance(cfg.get('db'), str):
        raise ValueError('structural, rules and sdc analysis need db')
    from . import rules
    rules.settings(cfg.get('rules'))
    if cfg.get('db'):
        cfg['db'] = str((path.parent / cfg['db']).resolve())
    timeout = cfg.get('timeout_s', 120)
    if type(timeout) not in (int, float) or not 0 < timeout <= 3600:
        raise ValueError('timeout_s must be positive and at most 3600')
    waivers = cfg.get('waivers', [])
    if not isinstance(waivers, list):
        raise ValueError('waivers must be a list')
    for w in waivers:
        if (not isinstance(w, dict) or set(w) != {'rule', 'endpoint', 'reason', 'config', 'finding_id'}
                or not all(isinstance(v, str) and v.strip() for v in w.values())
                or w['config'] != cfg['config']
                or len(w['finding_id']) != 64
                or any(c not in '0123456789abcdef' for c in w['finding_id'])):
            raise ValueError('waiver needs exact rule, endpoint, finding_id, reason and matching config')
    cfg['backends'] = backends
    return cfg, dict(path=str(path), sha256=hashlib.sha256(data).hexdigest())


def report(path):
    cfg, identity = load(path)
    runs = {}
    for backend in BACKENDS:
        if backend not in cfg['backends']:
            runs[backend] = dict(status='not_run', reason='not selected', findings=[])
        elif backend == 'structural':
            def checked(db):
                if db.meta.get('config') and db.meta['config'] != cfg['config']:
                    raise ValueError('settings config does not match database config')
                if db.meta.get('toplevel') and db.meta['toplevel'] != cfg['top']:
                    raise ValueError('settings top does not match database toplevel')
                return structural.analyze(db, cfg.get('intent', {}))
            runs[backend] = run_on(cfg['db'], checked)
        elif backend == 'rules':
            from . import rules
            runs[backend] = run_on(cfg['db'], lambda db: rules.analyze(db, cfg.get('rules')))
        elif backend == 'yosys':
            from . import yosys
            if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', cfg['top']):
                raise ValueError('yosys top must be a plain identifier')
            runs[backend] = yosys.run(cfg['files'], cfg['top'], cfg.get('timeout_s', 120))
        else:
            runs[backend] = native.run(backend, cfg['files'], cfg['top'], cfg.get('timeout_s', 120))
    waivers = [{**w, 'matches': 0} for w in cfg.get('waivers', [])]
    for backend, run in runs.items():
        for f in run['findings']:
            # Bind the waiver to all diagnostic data, including source and message.
            f['id'] = hashlib.sha256(json.dumps(
                dict(config=cfg['config'], top=cfg['top'], backend=backend, finding=f),
                sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            f['disposition'] = 'active'
            for w in waivers:
                if (f['rule'] == w['rule'] and f['endpoint'] == w['endpoint']
                        and f['id'] == w['finding_id']):
                    w['matches'] += 1
                    f['disposition'] = 'waived'
                    f['waiver_reason'] = w['reason']
    # A waiver that matches nothing in a backend that ran is stale: an error, not a silent pass.
    stale = []
    for w in waivers:
        backend = BACKEND_OF.get(w['rule'].split('.')[0], 'structural')
        if w['matches']:
            w['stale'] = False
        elif runs.get(backend, {}).get('status', 'not_run') == 'not_run':
            w['stale'] = None
        else:
            w['stale'] = True
            stale.append(dict(rule='lint.stale_waiver', severity='error', endpoint=w['endpoint'],
                              disposition='active', waived_rule=w['rule'], finding_id=w['finding_id'],
                              message=f"Waiver matches no {w['rule']} finding: {w['reason']}"))
    active = sum(f['disposition'] == 'active' for r in runs.values() for f in r['findings']) + len(stale)
    incomplete = any(r['status'] != 'completed' for r in runs.values())
    status = 'findings' if active else ('inconclusive' if incomplete else 'clean')
    return dict(schema='rvw.lint/1', config=cfg['config'], top=cfg['top'], settings=identity,
                inputs=[dict(path=f, sha256=hashlib.sha256(Path(f).read_bytes()).hexdigest()) for f in cfg['files']],
                status=status, active_findings=active, backends=runs, waivers=waivers, waiver_findings=stale)


def run(args):
    try:
        if (args.protocol or args.benchmark) and getattr(args, 'project', None):
            load_project(args.project)
        if (args.protocol or args.benchmark) and (getattr(args, 'emit', None) or getattr(args, 'sarif', None)):
            raise ValueError('--emit and --sarif need --settings or a project, not --protocol or --benchmark')
        if not (args.protocol or args.benchmark) and (args.out or args.simulate):
            raise ValueError('--out and --simulate need --protocol or --benchmark')
        if args.benchmark:
            if args.settings or args.protocol or not args.out or args.simulate:
                raise ValueError('--benchmark needs --out and cannot use --settings, --protocol or --simulate')
            from . import compare
            return compare.run(args)
        if args.protocol:
            if args.settings or not args.out:
                raise ValueError('--protocol needs --out and cannot use --settings')
            from . import protocol
            return protocol.run(args)
        path = args.settings
        if not path:
            selected = load_project(getattr(args, 'project', None))
            path = selected.get('lint', 'settings') if selected else None
        elif getattr(args, 'project', None):
            load_project(args.project)  # invalid explicit selections never fall back
        if not path:
            raise ValueError('select --settings or a project with lint.settings')
        result = report(path)
        if getattr(args, 'sarif', None):
            from . import sarif
            result['sarif'] = sarif.write(result, args.sarif)
        if getattr(args, 'emit', None):
            from . import emit
            result['emitted'] = emit.write(result, [i['path'] for i in result['inputs']], args.emit)
        code = 1 if result['status'] == 'findings' else (3 if result['status'] == 'inconclusive' else 0)
    except (ValueError, OSError, QueryError, ProjectError, sqlite3.DatabaseError) as exc:
        result, code = dict(status='error', error=str(exc)), 2
    print(json.dumps(result, indent=2) if args.json else
          f"Lint: {result['status']}" + (f" ({result['error']})" if 'error' in result else
          f"; active findings: {result['active_findings']}"))
    return code
