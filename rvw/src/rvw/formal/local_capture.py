"""Typed per-attempt captures for finite named-property implications."""
import re

from .sampled import PATTERN, emit, validate
from .sva import _group
from .temporal import Unsupported, split, unwrap

DECL = re.compile(r'^\s*(logic|reg|int|integer)(?:\s+(signed|unsigned))?'
                  r'(?:\s*\[\s*(\d+)\s*:\s*(\d+)\s*\])?\s+'
                  r'([A-Za-z_][A-Za-z0-9_]*(?:\s*,\s*[A-Za-z_][A-Za-z0-9_]*)*)\s*;')


def declarations(body):
    variables = {}
    while match := DECL.match(body):
        kind, sign, high, low, names = match.groups()
        if kind in ('int','integer') and high is not None:
            raise Unsupported('local_type')
        width = abs(int(high)-int(low))+1 if high is not None else 32 if kind in ('int','integer') else 1
        if width > 4096:
            raise Unsupported('local_width')
        signed = sign == 'signed' or (sign is None and kind in ('int','integer'))
        for name in (part.strip() for part in names.split(',')):
            if name in variables:
                raise Unsupported('duplicate_local', name)
            variables[name] = (width, signed)
        body = body[match.end():]
    if re.match(r'\s*(logic|reg|int|integer|bit|byte|shortint|longint)\b',body):
        raise Unsupported('local_declaration')
    return variables, body


def pattern(variables):
    return re.compile(r'(?<![\w.$])(?:' + '|'.join(map(re.escape,variables)) + r')(?![\w$])')


def capture(antecedent, variables, clock, prefix, sequence_names):
    text = antecedent.strip()
    if not text.startswith('('):
        raise Unsupported('local_capture_antecedent')
    parts = split(unwrap(text), r',')
    if len(parts) < 3:
        raise Unsupported('local_capture_antecedent')
    predicate = parts[0]
    local = pattern(variables)
    if local.search(predicate):
        raise Unsupported('local_before_assignment')
    if any(re.search(r'\b' + re.escape(name) + r'\b',predicate) for name in sequence_names):
        raise Unsupported('local_capture_sequence')
    validate(predicate)
    bound, lines = {}, []
    for index, assignment in enumerate(parts[2::2]):
        match = re.fullmatch(r'([A-Za-z_]\w*)\s*=\s*(?!=)(.+)', assignment, re.S)
        if not match or match[1] not in variables:
            raise Unsupported('local_assignment', assignment)
        name, expression = match.groups()
        for call in PATTERN.finditer(expression):
            argument, _ = _group(expression, call.end()-1)
            if local.search(argument):
                raise Unsupported('local_sampled_use')
        def previous(match):
            variable = match[0]
            if variable not in bound:
                raise Unsupported('local_before_assignment', variable)
            return bound[variable]
        expression = local.sub(previous, expression)
        lowered, history = emit(expression, clock, f'{prefix}_expression{index}')
        lines.extend(history)
        wire = f'{prefix}_value{index}'
        width, signed = variables[name]
        lines.append(f'wire {"signed " if signed else ""}[{width-1}:0] {wire} = ({lowered});')
        bound[name] = wire
    return predicate, bound, lines


def resolve(paths, variables, bound, offset):
    local = pattern(variables)
    result = []
    for path in paths:
        row = []
        for index, atom in enumerate(path):
            for call in PATTERN.finditer(atom):
                argument, _ = _group(atom, call.end()-1)
                if local.search(argument):
                    raise Unsupported('local_sampled_use')
            age = index + offset
            def replace(match):
                name = match[0]
                if name not in bound:
                    raise Unsupported('local_before_assignment', name)
                if atom[match.end():].lstrip().startswith(('[','.')):
                    raise Unsupported('local_select')
                if age > 64:
                    raise Unsupported('local_history_limit')
                return f'$past({bound[name]},{age})' if age else bound[name]
            row.append(local.sub(replace,atom))
        result.append(tuple(row))
    return result
