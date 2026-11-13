"""Finite SVA lowering to native Yosys formal statements.

Each sequence is a set of finite sample paths. Every antecedent match creates
an independent obligation. A check waits until the latest consequent deadline.
"""
from dataclasses import dataclass
import itertools
import re
from pathlib import Path

from .sva import _group, _expression

LIMIT = 64
PATH_LIMIT = 512


class Unsupported(ValueError):
    def __init__(self, construct, detail=''):
        self.construct = construct
        super().__init__(f'unsupported:{construct}' + (f': {detail}' if detail else ''))


def split(text, operator):
    depth = 0
    start = 0
    result = []
    for match in re.finditer(r'\(|\)|' + operator, text):
        if match[0] == '(':
            depth += 1
        elif match[0] == ')':
            depth -= 1
        elif depth == 0:
            result.append(text[start:match.start()].strip())
            result.append(match[0])
            start = match.end()
    result.append(text[start:].strip())
    return result


def unwrap(text):
    text = text.strip()
    while text.startswith('('):
        body, end = _group(text, 0)
        if end != len(text):
            break
        text = body.strip()
    return text


def bounds(text):
    parts = text.split(':')
    if not all(p.isdecimal() for p in parts):
        raise Unsupported('unbounded_range', text)
    lo, hi = int(parts[0]), int(parts[-1])
    if len(parts) > 2 or not 0 <= lo <= hi <= LIMIT:
        raise Unsupported('range_limit', text)
    return lo, hi


def checked(paths):
    if len(paths) > PATH_LIMIT or any(len(p) > LIMIT + 1 for p in paths):
        raise Unsupported('sequence_capacity', f'maximum {LIMIT} delays and {PATH_LIMIT} paths')
    return paths


def concat(left, right, delay):
    if not left or not right:
        raise Unsupported('empty_sequence')
    if delay == 0:
        return left[:-1] + (f'({left[-1]}) && ({right[0]})',) + right[1:]
    return left + ('1',) * (delay - 1) + right


def sequence(text, names=None, stack=()):
    names = names or {}
    text = unwrap(text)
    first = re.match(r'first_match\s*\(', text)
    if first:
        body, end = _group(text, first.end() - 1)
        if end != len(text):
            raise Unsupported('first_match_action')
        paths = sequence(body, names, stack)
        result = []
        for path in paths:
            candidates = [path]
            # Exclude every earlier endpoint. Distribute each negated prefix
            # into paths, so the existing Boolean history monitor can use it.
            for earlier in paths:
                if len(earlier) >= len(path):
                    continue
                expanded = []
                for candidate in candidates:
                    for i, atom in enumerate(earlier):
                        row = list(candidate)
                        row[i] = f'({row[i]}) && !({atom})'
                        expanded.append(tuple(row))
                candidates = checked(expanded)
            result.extend(candidates)
            checked(result)
        return result
    if text.startswith('##'):
        text = '1 ' + text
    parts = split(text, r'\bor\b')
    if len(parts) > 1:
        return checked([p for item in parts[::2] for p in sequence(item, names, stack)])
    # These operators bind less tightly than concatenation. Each path keeps
    # its endpoint. In particular intersect requires the same endpoint.
    for operator in ('within', 'intersect', 'throughout'):
        parts = split(text, rf'\b{operator}\b')
        if len(parts) > 1:
            if len(parts) != 3:
                raise Unsupported('sequence_association', text)
            left, right = (sequence(item, names, stack) for item in parts[::2])
            result = []
            for a, b in itertools.product(left, right):
                if operator == 'throughout':
                    if len(a) != 1:
                        raise Unsupported('throughout_expression')
                    result.append(tuple(f'({a[0]}) && ({x})' for x in b))
                elif operator == 'intersect':
                    if len(a) == len(b):
                        result.append(tuple(f'({x}) && ({y})' for x, y in zip(a, b)))
                else:
                    for offset in range(len(b) - len(a) + 1):
                        padded = ('1',) * offset + a + ('1',) * (len(b) - len(a) - offset)
                        result.append(tuple(f'({x}) && ({y})' for x, y in zip(padded, b)))
                checked(result)
            # No equal-length intersection means the sequence never matches.
            return result or [('0',)]

    parts = split(text, r'##\s*(?:\[[^\]]*\]|\d+)')
    if len(parts) > 1:
        paths = sequence(parts[0], names, stack)
        for token, term in zip(parts[1::2], parts[2::2]):
            raw = token[2:].strip().strip('[]')
            lo, hi = bounds(raw)
            rhs = sequence(term, names, stack)
            paths = checked([concat(a, b, n) for a, b, n in itertools.product(paths, rhs, range(lo, hi + 1))])
        return paths
    repeat = re.fullmatch(r'(.*?)\[\*\s*([^\]]+)\]', text, re.S)
    if repeat:
        lo, hi = bounds(repeat[2].strip())
        if lo == 0:
            raise Unsupported('empty_repetition')
        unit = sequence(repeat[1], names, stack)
        result = []
        current = [()]
        for count in range(1, hi + 1):
            current = checked([a + b for a in current for b in unit])
            if count >= lo:
                result.extend(current)
                checked(result)
        return result
    if text in names:
        if text in stack:
            raise Unsupported('recursive_sequence', text)
        return sequence(names[text], names, (*stack, text))
    if re.search(r'\[\s*(?:=|->)|##|\[\*', text):
        raise Unsupported('sequence_operator', text)
    reserved = re.search(r'\b(throughout|within|intersect|first_match|strong|weak|until|until_with|s_until|s_until_with|eventually|s_eventually|nexttime|s_nexttime|implies|iff|and|not|if|else|case|accept_on|reject_on|sync_accept_on|sync_reject_on)\b', text)
    if reserved:
        raise Unsupported(reserved[0])
    try:
        from .sampled import validate
        validate(text)
    except Unsupported:
        raise
    except ValueError as error:
        raise Unsupported('expression', str(error)) from error
    return [(text,)]


def sampled(expression, clock, prefix):
    from .sampled import emit
    return emit(expression, clock, prefix)


@dataclass
class Property:
    name: str
    kind: str
    clock: str
    disable: str | None
    antecedents: list[tuple] | None
    consequents: list[tuple]
    offset: int = 0

    def monitor(self, prefix, simulation=False):
        # Compare all branches at a common deadline. Overlapping starts are kept
        # in history, so a new request cannot overwrite an older obligation.
        branches = self.antecedents or [('1',)]
        horizon = max(len(a) - 1 + self.offset + max(map(len, self.consequents)) - 1
                      for a in branches)
        atoms = sorted({x for p in branches + self.consequents for x in p})
        lines = []
        for i, atom in enumerate(atoms):
            lowered, declarations = sampled(atom, self.clock, f'{prefix}_s{i}')
            lines.extend(declarations)
            lines.append(f'wire {prefix}_a{i} = !(!({lowered}));')
            if horizon:
                lines += [f'reg [{horizon-1}:0] {prefix}_h{i};',
                          f'always @(posedge {self.clock}) {prefix}_h{i} <= '
                          + (f'{{{prefix}_h{i}[{horizon-2}:0], {prefix}_a{i}}};' if horizon > 1
                             else f'{prefix}_a{i};')]
        def sample(atom, age):
            i = atoms.index(atom)
            return f'{prefix}_h{i}[{age-1}]' if age else f'{prefix}_a{i}'
        def match(path, start):
            return '(' + ' && '.join(sample(atom, horizon - start - i) for i, atom in enumerate(path)) + ')'
        checks = []
        for a in branches:
            start = len(a) - 1 + self.offset
            rhs = '(' + ' || '.join(match(c, start) for c in self.consequents) + ')'
            checks.append(f'(!{match(a, 0)} || {rhs})' if self.antecedents is not None else rhs)
        condition = ' && '.join(checks)
        enable = '1'
        if horizon:
            lines.append(f'reg [{horizon-1}:0] {prefix}_valid = 0;')
            sensitivity = f'posedge {self.clock}'
            if self.disable:
                lines.append(f'wire {prefix}_cancel = ({self.disable});')
                sensitivity += f' or posedge {prefix}_cancel'
            shift = (f'{{{prefix}_valid[{horizon-2}:0], 1\'b1}}' if horizon > 1 else "1'b1")
            lines.append(f'always @({sensitivity}) ' +
                         (f'if ({prefix}_cancel) {prefix}_valid <= 0; else ' if self.disable else '') +
                         f'{prefix}_valid <= {shift};')
            enable = f'{prefix}_valid[{horizon-1}]'
        if self.disable:
            enable += f' && !({self.disable})'
        action = f'{self.kind} ({condition});'
        if simulation:
            yes = 'cover' if self.kind == 'cover' else 'pass'
            no = 'miss' if self.kind == 'cover' else 'fail'
            action = (f'if (({condition}) === 1\'b1) $display("RVW_SVA {prefix} {self.kind} {yes}"); '
                      f'else $display("RVW_SVA {prefix} {self.kind} {no}");')
        lines.append(f'always @(posedge {self.clock}) if ({enable}) begin : {prefix}_check\n'
                     f'  {action}\nend')
        return '\n'.join(lines), horizon


def lower(source, simulation=False):
    from .bindings import expand
    source = expand(source)
    # Mask comments and strings without shifting source offsets.
    text = re.sub(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"',
                  lambda m: ' ' * len(m[0]), source, flags=re.S)
    if '`' in text:
        raise Unsupported('preprocessor', 'use preprocessed source')
    if re.search(r'\brvw_sva_\w*', text):
        raise Unsupported('reserved_identifier', 'rvw_sva_')
    names = {}
    edits = []
    # Names are module-local. Cross-module sequence definitions are refused.
    module_spans = list(re.finditer(r'\bmodule\b.*?\bendmodule\b', text, re.S))
    reports = []
    for module_index, module in enumerate(module_spans):
        names = {}
        properties = {}
        used_properties = set()
        for decl in re.finditer(r'\bproperty\s+(\w+)\s*;(.*?)\bendproperty\b', module[0], re.S):
            if decl[1] in properties:
                raise Unsupported('duplicate_property', decl[1])
            properties[decl[1]] = decl[2].strip().removesuffix(';').strip()
            edits.append((module.start() + decl.start(), module.start() + decl.end(), ''))
        for decl in re.finditer(r'\bsequence\s+(\w+)\s*;(.*?)\bendsequence\b', module[0], re.S):
            if decl[1] in names:
                raise Unsupported('duplicate_sequence', decl[1])
            names[decl[1]] = decl[2].strip().removesuffix(';').strip()
            edits.append((module.start() + decl.start(), module.start() + decl.end(), ''))
        for name, body in names.items():
            sequence(body, names, (name,))
        for index, prop in enumerate(re.finditer(r'\b(assert|assume|cover)\s+property\s*\(', module[0])):
            pos = module.start() + prop.start()
            body, end = _group(text, module.start() + prop.end() - 1)
            seen = set()
            while body.strip() in properties:
                name = body.strip()
                if name in seen:
                    raise Unsupported('recursive_property', name)
                seen.add(name)
                used_properties.add(name)
                body = properties[name]
            clock = re.match(r'\s*@\(\s*posedge\s+(\w+)\s*\)\s*', body)
            if not clock:
                raise Unsupported('clock_event', 'explicit posedge clock required')
            expr = body[clock.end():].strip()
            disable = None
            dm = re.match(r'disable\s+iff\s*', expr)
            if dm:
                disable, offset = _group(expr, dm.end())
                try:
                    _expression(disable)
                except ValueError as error:
                    raise Unsupported('disable_iff_expression', str(error)) from error
                if '$' in disable:
                    raise Unsupported('disable_iff_sampled_function')
                expr = expr[offset:].strip()
            parts = split(unwrap(expr), r'\|->|\|=>')
            if len(parts) not in (1, 3):
                raise Unsupported('nested_implication')
            antecedents = sequence(parts[0], names) if len(parts) == 3 else None
            consequent = sequence(parts[-1], names)
            item = Property(f'property_{module_index}_{index}', prop[1], clock[1], disable,
                            antecedents, consequent, int(len(parts) == 3 and parts[1] == '|=>'))
            emitted, horizon = item.monitor(f'rvw_sva_{module_index}_{index}', simulation=simulation)
            semi = re.match(r'\s*;', text[end:])
            if not semi:
                raise Unsupported('action_block')
            # A label before an assertion must not label a generated wire.
            before = text[module.start():pos]
            label = re.search(r'\b(\w+)\s*:\s*$', before)
            if label:
                item.name = label[1]
                pos = module.start() + label.start()
            edits.append((pos, end + semi.end(), emitted))
            reports.append({'id': item.name, 'kind': item.kind, 'clock': item.clock,
                            'disable_iff': disable, 'horizon': horizon,
                            'monitor': f'rvw_sva_{module_index}_{index}'})
        if set(properties) - used_properties:
            raise Unsupported('property', 'unused declarations need explicit checks')
    remainder = text
    for start, end, _ in sorted(edits, reverse=True):
        remainder = remainder[:start] + ' ' * (end - start) + remainder[end:]
    keyword = re.search(r'\b(sequence|endsequence|property|endproperty|clocking|bind|restrict|let)\b', remainder)
    if keyword:
        raise Unsupported(keyword[0])
    result = source
    for start, end, replacement in sorted(edits, reverse=True):
        result = result[:start] + replacement + result[end:]
    return result, reports


def run(args):
    import json
    output, properties = lower(Path(args.source).read_text())
    Path(args.out).write_text(output)
    print(json.dumps({'schema': 'rvw.sva-lowering/1', 'properties': properties}, indent=2))
    return 0
