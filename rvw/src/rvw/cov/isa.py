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
        if item['version'] is not None and (not isinstance(item['version'], str) or not item['version']):
            raise ValueError(f'{name}: version must be a non-empty string or null')
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


def pinned_files(data, root):
    source = data['source']
    if not re.fullmatch('[0-9a-f]{40}', source['revision']):
        raise ValueError('source revision must be a full commit ID')
    files = {}
    for name, digest in source['files'].items():
        text = captured.read_text(Path(root) / name)
        if sha256(text.encode()).hexdigest() != digest:
            raise ValueError(f'{name}: pinned source hash mismatch')
        files[name] = text
    return files


def opcode_records(files):
    records = {}
    for file, text in sorted(files.items()):
        if not file.startswith('extensions/'):
            continue
        for line in text.splitlines():
            words = line.split('#', 1)[0].split()
            if not words or words[0] == '$import':
                continue
            if words[0] == '$pseudo_op':
                # XLEN-specific definitions of the same instruction, not aliases.
                if file != 'extensions/rv32_i' or words[1].split('::')[-1] != words[2]:
                    continue
                words = words[2:]
            name, *tokens = words
            mask = value = 0
            args = []
            for token in tokens:
                if '=' not in token:
                    args.append(token)
                    continue
                bits, raw = token.split('=')
                hi, lo = map(int, bits.split('..')) if '..' in bits else (int(bits), int(bits))
                part = ((1 << (hi - lo + 1)) - 1) << lo
                mask |= part
                value |= int(raw, 0) << lo
            item = {'name': name, 'mask': mask, 'value': value, 'args': args, 'source': file}
            if name in records and records[name] != item:
                raise ValueError(f'duplicate instruction {name}; select one XLEN definition')
            records[name] = item
    return list(records.values())


@captured.command
def plan(manifest, root):
    import csv
    data = load_manifest(manifest)
    files = pinned_files(data, root)
    instructions = opcode_records(files)
    if not instructions:
        raise ValueError('no opcode definitions selected')
    args = {row[0]: [int(row[1]), int(row[2])] for row in csv.reader(files['arg_lut.csv'].splitlines(), skipinitialspace=True)}
    groups = [{'name': 'isa_instruction', 'fields': ['isa_instruction'],
               'bins': [[i['name']] for i in instructions]}]
    for insn in instructions:
        for arg in insn['args']:
            if arg not in args:
                raise ValueError(f'unknown opcode argument {arg}')
            hi, lo = args[arg]
            # Encoded fields, not reconstructed signed immediates or FP values.
            values = list(range(32)) if arg in ('rd', 'rs1', 'rs2', 'rs3') else (
                [0, 1, 2, 3, 4, 7] if arg == 'rm' else None)
            if values is None:
                continue
            groups.append({'name': f"isa_{insn['name']}_{arg}", 'fields': [f'isa_{arg}'],
                           'when': {'isa_instruction': insn['name']}, 'bins': [[v] for v in values]})
    from .semantic import groups as semantic_groups
    groups += semantic_groups(data, instructions)
    return {'groups': groups, 'isa_plan': {'manifest': data, 'instructions': instructions, 'args': args,
            'scope': 'Selected opcode encodings, fields and declared semantic domains; not exhaustive legal-combination or compliance coverage.',
            'unavailable': data.get('unavailable', [])}}


def observe_encoding(obs, isa_plan):
    if obs['event'] != 'retire':
        return
    insn = int(obs['insn'], 0) if isinstance(obs['insn'], str) else obs['insn']
    found = [i for i in isa_plan['instructions'] if insn & i['mask'] == i['value']]
    if len(found) != 1:
        return  # Ambiguous encodings earn no hit.
    item = found[0]
    if obs.get('trap'):
        obs['fault_instruction'] = item['name']
        return
    obs['isa_instruction'] = item['name']
    for arg in item['args']:
        hi, lo = isa_plan['args'][arg]
        obs[f'isa_{arg}'] = (insn >> lo) & ((1 << (hi - lo + 1)) - 1)


@captured.command
def spec_diff(before, after, old_root, new_root):
    """Compare two proposals without adopting either one."""
    old, new = load_manifest(before), load_manifest(after)
    a = {i['name']: i for i in opcode_records(pinned_files(old, old_root))}
    b = {i['name']: i for i in opcode_records(pinned_files(new, new_root))}
    added, removed = sorted(b.keys() - a.keys()), sorted(a.keys() - b.keys())
    changed = sorted(k for k in a.keys() & b.keys() if a[k] != b[k])
    declarations = {k: {'before': old.get(k), 'after': new.get(k)} for k in
                    ('isa', 'extensions', 'options', 'consumers', 'source', 'specifications', 'unavailable', 'semantics')
                    if old.get(k) != new.get(k)}
    needs_review = bool(declarations or added or removed or changed)
    return {'schema': 'rvw.isa-diff/1', 'status': 'inconclusive' if needs_review else 'unchanged',
            'adoption_required': needs_review, 'declarations': declarations,
            'instructions': {'added': added, 'removed': removed, 'changed': changed},
            'affected_checkers': ['ISA manifest validation', 'functional opcode coverage',
                                  *sorted(set(old.get('consumers', {})) | set(new.get('consumers', {})))] if needs_review else [],
            'tests_to_review': sorted(set(added + removed + changed)),
            'obligations': 'Semantic obligations and test presence are not determined by opcode diffs.',
            'notes': ['Read-only comparison. No pin, model or project file is updated.',
                      'specifications can pin profile, debug and platform documents; this command compares their declarations only.']}
