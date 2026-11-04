"""Reviewed bit layouts and finite legality crosses from the pinned manifest."""
from itertools import product
from math import prod

CLASSES = ['zero', 'positive', 'negative', 'minimum', 'maximum']


def groups(settings, instructions):
    names = {i['name'] for i in instructions}
    forms = settings.get('forms', {})
    if set(forms) - names:
        raise ValueError('semantic form instruction not in pinned opcode plan')
    result = []
    for name, fields in forms.items():
        if not fields:
            raise ValueError('semantic form needs fields')
        for field, layout in fields.items():
            width = layout['width']
            if type(width) is not int or not 2 <= width <= 64:
                raise ValueError('semantic field width must be 2..64')
            if type(layout.get('signed', False)) is not bool or type(layout.get('offset', 0)) is not int:
                raise ValueError('invalid semantic field signed/offset')
            used, inputs = set(), set()
            for hi, lo, dest in layout['bits']:
                if any(type(v) is not int for v in (hi, lo, dest)) or not 0 <= lo <= hi <= 31 or not 0 <= dest <= dest + hi - lo < width:
                    raise ValueError('invalid semantic bit slice')
                source = set(range(lo, hi + 1))
                target = set(range(dest, dest + hi - lo + 1))
                if used & target or inputs & source:
                    raise ValueError('overlapping semantic bit slices')
                used |= target
                inputs |= source
            if not used:
                raise ValueError('semantic field needs bit slices')
            if layout.get('bank') not in (None, 'integer', 'float'):
                raise ValueError('invalid register bank')
            bins = layout['bins']
            if bins == 'boundaries':
                if not layout.get('signed') or layout.get('offset', 0) or width - 1 not in used:
                    raise ValueError('boundary classes require signed field without offset')
                bins = CLASSES
            elif not isinstance(bins, list) or not bins or len(set(bins)) != len(bins):
                raise ValueError('semantic field needs distinct bins')
            result.append({'name': f'form_{name}_{field}', 'fields': [f'form_{field}'],
                           'when': {'isa_instruction': name}, 'bins': [[v] for v in bins]})
    for cross in settings.get('crosses', []):
        name, fields = cross['instruction'], cross['fields']
        if name not in forms or not fields or len(set(fields)) != len(fields) or set(fields) - set(forms[name]):
            raise ValueError('cross needs declared instruction fields')
        domains = [forms[name][f]['bins'] for f in fields]
        domains = [CLASSES if d == 'boundaries' else d for d in domains]
        if prod(map(len, domains)) > 100000:
            raise ValueError('semantic cross exceeds 100000 combinations')
        expected = set(product(*domains))
        classified = {}
        for row in cross['combinations']:
            key = tuple(row['bin'])
            if key not in expected or key in classified or row['status'] not in ('legal', 'illegal', 'unavailable') or not row.get('reason'):
                raise ValueError('invalid semantic cross classification')
            classified[key] = row['status']
        if classified.keys() != expected:
            raise ValueError('semantic cross classification is not exhaustive')
        # Retain every bin, including illegal/unavailable targets. No declaration
        # is a proof exclusion. Observations can expose an illegal combination.
        result.append({'name': f"cross_{cross['id']}", 'fields': [f'form_{f}' for f in fields],
                       'when': {'isa_instruction': name}, 'bins': [list(v) for v in sorted(expected, key=str)],
                       'classifications': cross['combinations']})
    return result


def observe(obs, plan, insn, name):
    forms = plan['manifest'].get('semantics', {}).get('forms', {})
    for field, layout in forms.get(name, {}).items():
        value = 0
        for hi, lo, dest in layout['bits']:
            value |= ((insn >> lo) & ((1 << (hi - lo + 1)) - 1)) << dest
        width = layout['width']
        if layout.get('signed') and value & (1 << (width - 1)):
            value -= 1 << width
        value += layout.get('offset', 0)
        if layout['bins'] == 'boundaries':
            mask = sum(((1 << (hi - lo + 1)) - 1) << dest for hi, lo, dest in layout['bits'])
            maximum = mask & ((1 << (width - 1)) - 1)
            value = {0: 'zero', -(1 << (width - 1)): 'minimum',
                     maximum: 'maximum'}.get(value, 'negative' if value < 0 else 'positive')
        obs[f'form_{field}'] = value
