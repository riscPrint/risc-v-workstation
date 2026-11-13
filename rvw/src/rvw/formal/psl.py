"""A finite Verilog-flavor PSL adapter to the shared SVA frontend.

The accepted language is deliberately explicit. Unsupported temporal constructs
never fall through as Boolean HDL expressions.
"""
import json
from pathlib import Path
import re

from .property_library import ident
from .temporal import Unsupported, lower, split, unwrap


def statements(text):
    text = re.sub(r'//[^\n]*|/\*.*?\*/', '', text, flags=re.S)
    depth, start = 0, 0
    result = []
    for index, char in enumerate(text):
        if char in '({[':
            depth += 1
        elif char in ')}]':
            depth -= 1
            if depth < 0:
                raise Unsupported('psl_delimiter')
        elif char == ';' and depth == 0:
            result.append(text[start:index].strip())
            start = index + 1
    if depth or text[start:].strip():
        raise Unsupported('psl_statement', 'unclosed delimiter or missing semicolon')
    return [row for row in result if row]


def sequence(text):
    text = unwrap(text)
    if text.startswith('{') and text.endswith('}'):
        body = text[1:-1]
        # The initial subset permits flat finite SERE concatenations only.
        if '{' in body or '}' in body:
            raise Unsupported('psl_nested_sere')
        parts = body.split(';')
        return ' ##1 '.join(sequence(part) for part in parts)
    if re.search(r'\[\s*\+\s*\]', text):
        raise Unsupported('psl_unbounded_repetition')
    if any(c in text for c in '{};'):
        raise Unsupported('psl_sere')
    if re.search(r'\b(next|always|never|eventually|until|before|abort|vunit|forall|exists)\b', text):
        raise Unsupported('psl_temporal', text)
    text = re.sub(r'\[\*\s*(\d+)\s+to\s+(\d+)\s*\]', r'[*\1:\2]', text)
    return text


def temporal(text):
    text = unwrap(text)
    parts = split(text, r'\|->|\|=>|(?<![|<])\->')
    if len(parts) == 3:
        operator = '|->' if parts[1] == '->' else parts[1]
        return f'{sequence(parts[0])} {operator} {temporal(parts[2])}'
    if len(parts) != 1:
        raise Unsupported('psl_nested_implication')
    next_ = re.fullmatch(r'next(?:\[(\d+)\])?\s*(.+)', text, re.S)
    if next_:
        delay = int(next_[1] or 1)
        if not 1 <= delay <= 64:
            raise Unsupported('psl_next_depth')
        return f'1 ##{delay} {sequence(next_[2])}'
    if re.search(r'\b(eventually|until|before|abort|next_e|next_a|within|whilenot|vunit|forall|exists)\b', text):
        raise Unsupported('psl_temporal', text)
    return sequence(text)


def translate(source, clock=None):
    rows = statements(source)
    declared = None
    properties = []
    names = set()
    for row in rows:
        default = re.fullmatch(r'default\s+clock\s*=\s*\(\s*posedge\s+(\w+)\s*\)', row)
        if default:
            if declared is not None:
                raise Unsupported('psl_duplicate_clock')
            declared = ident(default[1])
            continue
        prop = re.fullmatch(r'(?:(\w+)\s*:\s*)?(assert|assume|cover)\s+(.+)', row, re.S)
        if not prop:
            raise Unsupported('psl_directive', row)
        name, kind, expression = prop.groups()
        name = ident(name or f'psl_{len(properties)}')
        if name in names:
            raise Unsupported('psl_duplicate_property', name)
        names.add(name)
        if kind in ('assert', 'assume'):
            always = re.fullmatch(r'always\s+(.+)', unwrap(expression), re.S)
            if not always:
                raise Unsupported('psl_always_required')
            expression = temporal(always[1])
        else:
            if not expression.strip().startswith('{'):
                raise Unsupported('psl_cover_sequence')
            expression = sequence(expression)
        properties.append((name, kind, expression))
    if clock is not None:
        clock = ident(clock)
    if clock and declared and clock != declared:
        raise Unsupported('psl_clock_conflict')
    clock = clock or declared
    if not clock or not properties:
        raise Unsupported('psl_clock_or_properties')
    output = '\n'.join(f'{name}: {kind} property (@(posedge {clock}) {expr});'
                       for name,kind,expr in properties) + '\n'
    lower('module rvw_psl;\n' + output + '\nendmodule')
    return output


def run(args):
    output = translate(Path(args.source).read_text(), args.clock)
    Path(args.out).write_text(output)
    print(json.dumps(dict(schema='rvw.psl-lowering/1', status='generated', output=args.out)))
    return 0
