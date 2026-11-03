"""Lint settings are project data. No backend suppression switches are accepted."""
import hashlib
import json
from pathlib import Path
import sqlite3

from rvw.common.project import load_project, ProjectError
from rvw.query.db import run_on, QueryError
from . import native, structural


def register(sub):
    p = sub.add_parser('lint', help='native lint and structural CDC/RDC inventory')
    p.add_argument('--settings', help='lint settings JSON; else project lint.settings')
    p.add_argument('--json', action='store_true')
    p.set_defaults(func=run)


def load(path):
    path = Path(path).resolve()
    data = path.read_bytes()
    cfg = json.loads(data)
    allowed = {'schema', 'config', 'top', 'files', 'db', 'backends', 'waivers', 'timeout_s'}
    if not isinstance(cfg, dict) or set(cfg) - allowed or cfg.get('schema') != 'rvw.lint-settings/1':
        raise ValueError('invalid lint settings schema or keys')
    for key in ('config', 'top'):
        if not isinstance(cfg.get(key), str) or not cfg[key].strip():
            raise ValueError(f'{key} must be a nonempty string')
    backends = cfg.get('backends', ['verilator', 'verible', 'structural'])
    if (not isinstance(backends, list) or not backends or
            not all(isinstance(b, str) for b in backends) or len(set(backends)) != len(backends)
            or set(backends) - {'verilator', 'verible', 'structural'}):
        raise ValueError('backends must select verilator, verible or structural')
    files = cfg.get('files', [])
    if not isinstance(files, list) or not all(isinstance(f, str) and f for f in files):
        raise ValueError('files must be a list of paths')
    cfg['files'] = [str((path.parent / f).resolve()) for f in files]
    for file in cfg['files']:
        if not Path(file).is_file():
            raise ValueError(f'RTL file not found: {file}')
    if set(backends) & {'verilator', 'verible'} and not files:
        raise ValueError('native lint needs files')
    if 'structural' in backends and not isinstance(cfg.get('db'), str):
        raise ValueError('structural analysis needs db')
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
    for backend in ('verilator', 'verible', 'structural'):
        if backend not in cfg['backends']:
            runs[backend] = dict(status='not_run', reason='not selected', findings=[])
        elif backend == 'structural':
            def checked(db):
                if db.meta.get('config') and db.meta['config'] != cfg['config']:
                    raise ValueError('settings config does not match database config')
                if db.meta.get('toplevel') and db.meta['toplevel'] != cfg['top']:
                    raise ValueError('settings top does not match database toplevel')
                return structural.analyze(db)
            runs[backend] = run_on(cfg['db'], checked)
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
    active = sum(f['disposition'] == 'active' for r in runs.values() for f in r['findings'])
    incomplete = any(r['status'] != 'completed' for r in runs.values())
    status = 'findings' if active else ('inconclusive' if incomplete else 'clean')
    return dict(schema='rvw.lint/1', config=cfg['config'], top=cfg['top'], settings=identity,
                inputs=[dict(path=f, sha256=hashlib.sha256(Path(f).read_bytes()).hexdigest()) for f in cfg['files']],
                status=status, active_findings=active, backends=runs, waivers=waivers)


def run(args):
    try:
        path = args.settings
        if not path:
            selected = load_project(getattr(args, 'project', None))
            path = selected.get('lint', 'settings') if selected else None
        elif getattr(args, 'project', None):
            load_project(args.project)  # invalid explicit selections never fall back
        if not path:
            raise ValueError('select --settings or a project with lint.settings')
        result = report(path)
        code = 1 if result['status'] == 'findings' else (3 if result['status'] == 'inconclusive' else 0)
    except (ValueError, OSError, QueryError, ProjectError, sqlite3.DatabaseError) as exc:
        result, code = dict(status='error', error=str(exc)), 2
    print(json.dumps(result, indent=2) if args.json else
          f"Lint: {result['status']}" + (f" ({result['error']})" if 'error' in result else
          f"; active findings: {result['active_findings']}"))
    return code
