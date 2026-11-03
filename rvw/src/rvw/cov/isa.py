"""Core-owned ISA declarations and pinned opcode coverage plans.

This is a coverage planner, not a reference model or an ISA compliance checker.
"""
from hashlib import sha256
import json
from pathlib import Path
import re

from . import captured


def extensions(isa):
    match = re.fullmatch(r'rv(32|64)([iemafdqclbjtpv]+)((?:_[a-z][a-z0-9]*)*)', isa)
    if not match:
        raise ValueError(f'expected an unversioned, expanded ISA string: {isa}')
    return int(match[1]), set(match[2]) | set(filter(None, match[3].split('_')))


@captured.command
def load_manifest(path):
    data = json.loads(captured.read_text(path))
    if data.get('schema') != 'rvw.isa/1':
        raise ValueError('expected rvw.isa/1')
    xlen, names = extensions(data['isa'])
    if set(data['extensions']) != names:
        raise ValueError('extension declarations contradict ISA string')
    for name, item in data['extensions'].items():
        if not isinstance(item, dict) or 'version' not in item:
            raise ValueError(f'{name}: declare version (null if not verified)')
        if set(item.get('requires', [])) - names:
            raise ValueError(f'{name}: missing required extensions')
    for consumer, isa in data.get('consumers', {}).items():
        if isa != data['isa']:
            raise ValueError(f'{consumer}: ISA contradicts manifest')
    if not isinstance(data.get('options'), dict):
        raise ValueError('declare implementation options')
    return data


@captured.command
def check_manifest(path):
    data = load_manifest(path)
    unknown = [name for name, item in data['extensions'].items() if item['version'] is None]
    return {'schema': 'rvw.isa-check/1', 'isa': data['isa'],
            'status': 'inconclusive' if unknown else 'declared',
            'unverified_versions': unknown, 'consumers': data.get('consumers', {}),
            'notes': ['Consumer strings are declarations; tools are not probed.']}
