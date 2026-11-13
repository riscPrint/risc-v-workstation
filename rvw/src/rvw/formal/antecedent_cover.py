"""Separate bounded cover observations for a property's antecedent."""
from pathlib import Path
import re

from rvw.common.sby import execute
from . import common
from .campaign import _job
from .regression import task_config


def prepare(prop, selected, capture, directory):
    if not prop.get('activation_sby'):
        return None
    source = Path(selected).absolute().parent / prop['activation_sby']
    item = capture.file(source)
    config = task_config(item.copy.read_text(), prop.get('activation_task'))
    if len(re.findall(r'^\s*mode\s+cover\s*$', config, re.M)) != 1:
        raise ValueError('unsupported:activation_requires_cover_mode')
    temporary = re.sub(r'^(\s*mode\s+)cover\s*$', r'\1bmc', config, flags=re.M)
    config, _, engine = _job(temporary, source, capture)
    config = re.sub(r'^(\s*mode\s+)bmc\s*$', r'\1cover', config, flags=re.M)
    if ',' in engine:
        raise ValueError('unsupported:activation_engine_portfolio')
    path = directory / 'activation.sby'
    path.write_text(config)
    depth = re.search(r'^\s*depth\s+(\d+)\s*$', config, re.M)
    return path, engine, int(depth[1]) if depth else 20


def observe(job, engine, depth, tools, directory, timeout, top):
    rc, seconds = execute(tools.command(['sby', '-j', '1', '-f', '-d', 'activation-sby', str(job)]),
                          directory, directory / 'activation.log', timeout, env=tools.env)
    model = directory / 'activation-sby/model/design_prep.il'
    count = None
    if model.exists():
        # Reuse the hierarchy-aware counter without changing the proved model.
        copy = directory / 'activation-count.il'
        copy.write_text(model.read_text().replace('cell $cover ', 'cell $assert '))
        count = common.count_asserts(copy, top)
    log = directory / 'activation-sby/logfile.txt'
    text = log.read_text(errors='replace') if log.exists() else ''
    status = common.final_status(rc, text, count)
    if count != 1:
        status = 'error'
    tools.verify()
    return dict(status={'pass': 'reached', 'fail': 'not_reached_within_bound'}.get(status, status),
                depth=depth, wall_s=seconds, engine=engine,
                traces=sorted(str(p.relative_to(directory.parent))
                              for p in (directory / 'activation-sby').glob('engine_*/trace*.vcd')),
                scope='one bounded antecedent cover; not a proof of universal activation')
