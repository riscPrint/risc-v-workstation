"""CPU-capped SBY property regression, independent of the SVA frontend."""
from argparse import Namespace
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tomllib
import uuid

from rvw.common.capture import Capture, CaptureError
from rvw.common.sby import execute
from rvw.common.project import load_project
from rvw.results import SuiteResults, validate, write_junit
from .campaign import NAME, _job
from .tools import Toolchain
from . import common


def task_config(text, task=None):
    """Select named SBY tasks and tags. Refuse unimplemented preprocessing."""
    if re.search(r'^\s*--pycode', text, re.M):
        raise ValueError('unsupported:sby_python')
    match = re.search(r'^\[tasks\]\s*\n(.*?)(?=^\[|\Z)', text, re.M | re.S)
    tags = set()
    if match:
        rows = [r.split('#', 1)[0].split() for r in match[1].splitlines()]
        tasks = {r[0]: set(r) for r in rows if r}
        if task not in tasks:
            raise ValueError(f'unsupported:sby_task: select one of {sorted(tasks)}')
        tags = tasks[task]
        text = text[:match.start()] + text[match.end():]
    elif task:
        raise ValueError('unsupported:sby_task: file has no tasks')
    lines = []
    for line in text.splitlines():
        conditional = re.match(r'^\s*(~?[\w.-]+):\s+(.*)$', line)
        if conditional:
            tag, content = conditional.groups()
            if (tag.removeprefix('~') in tags) != tag.startswith('~'):
                lines.append(content)
        else:
            lines.append(line)
    return '\n'.join(lines) + '\n'


def observe(prop, directory, job, mode, tools, timeout, depth):
    rc, seconds = execute(tools.command(['sby', '-j', '1', '-f', '-d', 'sby', str(job)]),
                          directory, directory / 'run.log', timeout, env=tools.env)
    log = directory / 'sby' / 'logfile.txt'
    text = log.read_text(errors='replace') if log.exists() else ''
    count = common.count_asserts(directory / 'sby' / 'model' / 'design_prep.il', prop['top'])
    status = common.final_status(rc, text, count)
    if count != 1:
        status = 'error'
    try:
        tools.verify()
    except (ValueError, CaptureError):
        status = 'unknown'
    outcome = {'pass': 'bounded-pass' if mode == 'bmc' else 'proven', 'fail': 'failed',
               'timeout': 'timeout', 'unknown': 'unknown'}.get(status, 'error')
    # An explicit solver PREUNSAT diagnostic is evidence of inconsistent
    # assumptions at a checked step. Never present that job as a proof.
    if 'Status: PREUNSAT' in text:
        outcome, status = 'vacuous', 'unknown'
    traces = sorted(str(p.relative_to(directory.parent)) for p in
                    (directory / 'sby').glob('engine_*/trace*.vcd'))
    return {'id': prop['id'], 'status': status if status in ('pass', 'fail', 'timeout') else 'error',
            'seed': None, 'signature': None if status == 'pass' else 'formal:' + outcome,
            'wall_s': seconds, 'run': str((directory / 'run.log').relative_to(directory.parent)),
            'formal_status': outcome, 'mode': mode, 'depth': depth if mode == 'bmc' else None,
            'traces': traces, 'task': prop.get('task'), 'requirements': prop.get('requirements', []),
            'assumptions': prop.get('assumptions', []), 'configuration': prop.get('config', 'external'),
            'job_sha256': hashlib.sha256(job.read_bytes()).hexdigest(),
            'activation': 'not_measured',
            'inconclusive': 'Engine observation; transitive input closure, attribution and non-vacuity are not certified.'}


# Signal handlers must only be installed in the calling thread. execute owns
# process-group cleanup if a worker is interrupted by its timeout.


def run(args):
    if args.jobs < 1 or not math.isfinite(args.timeout) or args.timeout <= 0:
        raise ValueError('jobs and timeout must be positive')
    out = Path(args.out).absolute()
    out.mkdir(parents=True, exist_ok=False)
    capture = Capture(out / 'inputs')
    selected = args.manifest
    if not selected:
        project = load_project(getattr(args, 'project', None), capture=capture)
        selected = project.get('formal', 'regress') if project else None
    if not selected:
        raise ValueError('give a manifest or declare [formal] regress in rvw.toml')
    manifest = capture.file(Path(selected).absolute())
    plan = tomllib.loads(manifest.copy.read_text())
    properties = plan.get('property', [])
    ids = [p['id'] for p in properties]
    if not ids or any(not NAME.fullmatch(i) for i in ids) or len(set(i.lower() for i in ids)) != len(ids):
        raise ValueError('declare nonempty [[property]] rows with unique plain ids')
    prepared = []
    results = {}
    for prop in properties:
        directory = out / prop['id']
        directory.mkdir()
        common.check_ident('top', prop['top'])
        source = Path(selected).absolute().parent / prop['sby']
        item = capture.file(source)
        try:
            config = task_config(item.copy.read_text(), prop.get('task'))
            try:
                config, mode, engines = _job(config, source, capture)
            except ValueError as error:
                raise ValueError(f'unsupported:sby_configuration: {error}') from error
            if ',' in engines:
                raise ValueError('unsupported:engine_portfolio: use one engine per property to honor CPU cap')
            depth_match = re.search(r'^\s*depth\s+(\d+)\s*$', config, re.M)
            depth = int(depth_match[1]) if depth_match else 20  # SBY default
            if depth < 1:
                raise ValueError('unsupported:depth')
            job = directory / 'job.sby'
            job.write_text(config)
            tools = Toolchain(capture, Namespace(engine=engines), directory / 'tools')
            prepared.append((prop, directory, job, mode, tools, args.timeout, depth))
        except ValueError as error:
            if 'unsupported:' not in str(error):
                raise
            results[prop['id']] = {'id': prop['id'], 'status': 'error', 'seed': None,
                                   'signature': 'formal:unsupported', 'wall_s': 0, 'run': None,
                                   'formal_status': 'unsupported', 'diagnostic': str(error),
                                   'inconclusive': str(error)}
    cap = min(args.jobs, os.cpu_count() or 1)
    with ThreadPoolExecutor(max_workers=cap) as pool:
        for result in pool.map(lambda item: observe(*item), prepared):
            results[result['id']] = result
    suite = {'schema': 'rvw.results/1', 'run_id': uuid.uuid4().hex, 'suite': 'formal-regress',
             'core': plan.get('core', 'external'), 'config': plan.get('config', 'external'),
             'created': datetime.now(timezone.utc).isoformat(),
             'source': {'manifest_sha256': manifest.sha256}, 'workers': cap,
             'tests': [results[i] for i in ids], 'input_capture': capture.record()}
    problems = validate(suite)
    if problems:
        raise ValueError('; '.join(problems))
    common.write_json(out / 'results.json', suite)
    write_junit(SuiteResults.from_dict(suite), out / 'junit.xml')
    # Engine proofs and bounded passes remain conditional suite observations.
    result = {'schema': 'rvw.formal-regress/1', 'status': 'unknown', 'suite': 'results.json',
              'junit': 'junit.xml', 'workers': cap, 'properties': suite['tests']}
    common.write_json(out / 'result.json', result)
    print(json.dumps(result, indent=2) if args.json else '\n'.join(
        f"{p['id']}: {p['formal_status']}" for p in suite['tests']))
    return 1
