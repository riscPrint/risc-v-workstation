"""Project description projection. Shared dimensions cannot silently diverge."""
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
import runpy


CPU_FIELDS = {'fetch_width':'fetchWidth', 'fetch_entries':'fetchQueueSize',
              'rename_width':'renameWidth', 'rob_entries':'numROBEntries',
              'issue_width':'issueWidth', 'load_entries':'LQEntries',
              'store_entries':'SQEntries', 'commit_width':'commitWidth',
              'physical_registers':'numPhysIntRegs'}


@lru_cache(maxsize=1)
def validator():
    return runpy.run_path(str(Path(__file__).resolve().parents[4] / "Arch/model.py"))["validate_description"]


def parameters(description):
    if description.get('schema') != 'rvw.arch-core/1' or description.get('kind') != 'o3':
        raise ValueError('own-model projection requires an O3 rvw.arch-core/1 description')
    validator()(description)
    if not isinstance(description.get('ooo'), dict):
        raise ValueError('project description requires an ooo parameter table')
    cpu = description['cpu']
    own = deepcopy(description['ooo'])
    if 'latencies' not in own:
        raise ValueError('ooo.latencies must declare the project execution timing')
    shared = {key: cpu[field] for key, field in CPU_FIELDS.items()}
    if 'numPhysFloatRegs' in cpu:
        shared['physical_float_registers'] = cpu['numPhysFloatRegs']
    shared['issue_entries'] = sum(queue['entries'] for queue in description['queues'])
    for key, value in shared.items():
        if key in own and own[key] != value:
            raise ValueError(f'ooo.{key} conflicts with the shared description')
        own[key] = value
    frontend = own.setdefault('frontend', {})
    for key, field in [('decode_width', 'decodeWidth'), ('ftq_entries', 'numFTQEntries')]:
        if field not in cpu:
            raise ValueError(f'cpu.{field} must be explicit for own-model projection')
        if key in frontend and frontend[key] != cpu[field]:
            raise ValueError(f'ooo.frontend.{key} conflicts with the shared description')
        frontend[key] = cpu[field]
    return own


def configuration(data):
    from .core import Config
    return Config(**(parameters(data) if data.get('schema') == 'rvw.arch-core/1' else data))
