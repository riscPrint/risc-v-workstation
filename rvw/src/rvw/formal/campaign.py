"""Run self-contained SBY jobs and retain conditional per-property observations."""
from argparse import Namespace
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import tomllib
import uuid

from rvw.common.capture import Capture, CaptureError
from rvw.common.sby import execute
from rvw.results import validate
from . import common
from .tools import Toolchain

NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]*")


def _job(text, source, capture):
    """Freeze listed file inputs. Refuse task tags and embedded file sections."""
    sections = {}
    section = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('['):
            if line not in ('[options]', '[engines]', '[script]', '[files]') or line in sections:
                raise ValueError("use one task with options, engines, script and files sections")
            section = line
            sections[section] = []
        elif section is None:
            raise ValueError("job content outside a section")
        else:
            sections[section].append(raw)
    if set(sections) != {'[options]', '[engines]', '[script]', '[files]'}:
        raise ValueError("missing SBY section")
    options = dict(line.strip().split(maxsplit=1) for line in sections['[options]'])
    mode = options.get('mode')
    if mode not in ('bmc', 'prove'):
        raise ValueError("campaign supports bmc and prove jobs only")
    engines = []
    for line in sections['[engines]']:
        fields = line.split()
        if not fields or any(not NAME.fullmatch(f) for f in fields):
            raise ValueError("use engine and solver names without task tags or options")
        engines.append(':'.join(fields))
    frozen = []
    for line in sections['[files]']:
        fields = line.split()
        if len(fields) == 1:
            target, original = Path(fields[0]).name, fields[0]
        elif len(fields) == 2:
            target, original = fields
        else:
            raise ValueError("invalid SBY files row")
        if not NAME.fullmatch(target) or any(row.split()[0] == target for row in frozen):
            raise ValueError("file targets must be unique plain basenames")
        item = capture.file(source.parent / original)
        common.check_path("captured file", item.copy)
        frozen.append(f"{target} {item.copy}")
    sections['[files]'] = frozen
    return '\n\n'.join(k + '\n' + '\n'.join(v) for k, v in sections.items()) + '\n', mode, ','.join(engines)


def run(args):
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        raise ValueError("timeout must be finite and positive")
    out = Path(args.out).absolute()
    common.check_path("--out", out)
    out.mkdir(parents=True, exist_ok=False)
    capture = Capture(out / 'inputs')
    manifest = capture.file(Path(args.manifest).absolute())
    plan = tomllib.loads(manifest.copy.read_text())
    properties = plan.get('property', [])
    if not properties:
        raise ValueError("manifest needs [[property]] rows")
    ids = [p['id'] for p in properties]
    if any(not NAME.fullmatch(i) for i in ids) or len({i.lower() for i in ids}) != len(ids):
        raise ValueError("property ids must be unique plain names")
    tests = []
    # Prepare every job before executing the first. Later source edits cannot replace a job.
    jobs = []
    for prop in properties:
        for key in ('requirements', 'assumptions'):
            if not isinstance(prop.get(key), list) or not all(isinstance(s, str) for s in prop[key]):
                raise ValueError(f"{prop['id']}: declare {key} as a string array")
        if not isinstance(prop.get('config'), str) or not prop['config']:
            raise ValueError("each property needs a configuration identity")
        common.check_ident('property top', prop['top'])
        source = Path(args.manifest).absolute().parent / prop['sby']
        item = capture.file(source)
        directory = out / prop['id']
        directory.mkdir()
        text, mode, engines = _job(item.copy.read_text(), source, capture)
        tools = Toolchain(capture, Namespace(engine=engines), directory / 'tools')
        job = directory / 'job.sby'
        job.write_text(text)
        jobs.append((prop, directory, job, mode, tools))
    for prop, directory, job, mode, tools in jobs:
        command = tools.command(['sby', '-f', '-d', 'sby', str(job)])
        with common.sigterm_raises():
            rc, seconds = execute(command, directory, directory / 'run.log', args.timeout, env=tools.env)
        log = directory / 'sby' / 'logfile.txt'
        text = log.read_text(errors='replace') if log.exists() else ''
        # This runner observes a job result. It does not assert input closure or non-vacuity.
        assertions = common.count_asserts(directory / 'sby' / 'model' / 'design_prep.il', prop['top'])
        status = common.final_status(rc, text, assertions)
        if assertions != 1:
            status = 'error'
        try:
            tools.verify()
        except (ValueError, CaptureError):
            status = 'unknown'
        meaning = {'pass': 'bounded_pass' if mode == 'bmc' else 'unbounded_engine_pass',
                   'fail': 'counterexample', 'timeout': 'timeout', 'unknown': 'unknown'}.get(status, 'error')
        mapped = status if status in ('pass', 'fail', 'timeout') else 'error'
        tests.append({'id': prop['id'], 'status': mapped, 'seed': None,
                      'signature': None if mapped == 'pass' else 'formal:' + meaning,
                      'wall_s': seconds, 'run': str((directory / 'run.log').relative_to(out)),
                      'formal_status': meaning, 'requirements': prop['requirements'],
                      'assumptions': prop['assumptions'], 'configuration': prop['config'],
                      'job_sha256': hashlib.sha256(job.read_bytes()).hexdigest(),
                      'inconclusive': 'SBY job observation: input closure, property attribution and vacuity are not checked',
                      'wall_clock_timeout': status == 'timeout'})
    created = datetime.now(timezone.utc).isoformat()
    result = {'schema': 'rvw.results/1', 'run_id': uuid.uuid4().hex, 'suite': 'formal-sby',
              'core': plan.get('core', 'external'), 'config': plan.get('config', 'external'),
              'created': created, 'source': {'manifest_sha256': manifest.sha256},
              'tests': tests, 'input_capture': capture.record()}
    verdict = {'schema': 'rvw.verdict/2', 'verdict': 'inconclusive', 'tests': 'incomplete',
               'not_accepted_reason': None,
               'inconclusive': [{'id': t['id'], 'why': t['inconclusive']} for t in tests],
               'reasons': ['Job observations do not establish a design acceptance gate.']}
    for name, value in (('results.json', result), ('verdict.json', verdict)):
        problems = validate(value)
        if problems:
            raise ValueError('; '.join(problems))
        common.write_json(out / name, value)
    # An append-only history is formed by keeping each fresh campaign directory.
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for test in tests:
            print(f"{test['id']}: {test['formal_status']}")
    return 1


def history(args):
    """Read retained C3 campaigns. Keep configuration and assumptions in every sample."""
    from rvw.results import load_results
    rows = {}
    for path in args.paths:
        suite = load_results(path)
        if suite.suite != 'formal-sby':
            raise ValueError(f"{path}: not an SBY campaign")
        for entry in suite.tests:
            rows.setdefault(entry.id, []).append({
                'run_id': suite.run_id, 'created': suite.created,
                'formal_status': entry.extra['formal_status'],
                'configuration': entry.extra['configuration'],
                'requirements': entry.extra['requirements'],
                'assumptions': entry.extra['assumptions'],
                'job_sha256': entry.extra['job_sha256']})
    for samples in rows.values():
        samples.sort(key=lambda row: (row['created'], row['run_id']))
    print(json.dumps({'schema': 'rvw.formal-history/1', 'properties': rows}, indent=2))
    return 0
