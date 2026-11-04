"""Conservative import boundary for the qualified slang SVA subset.

The native frontend handles parsing, types and lowering. This guard refuses syntax
outside the tested subset, including inactive or unused declarations.
"""
import re

_COMMENTS = re.compile(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"', re.S)
_ASSERT = re.compile(r'\b(assert|assume)\s+property\s*\(')
_FORBIDDEN = re.compile(r'`|\b(sequence|endsequence|endproperty|clocking|endclocking|bind|cover|restrict|let)\b')
_EXPR = re.compile(r"\s+|\$(?:past|rose|fell|stable|changed)\b|[A-Za-z_][A-Za-z0-9_]*|\d+(?:'[sS]?[bBoOdDhH][0-9a-fA-F_xXzZ?]+)?|'[01]|[()!~&|^+*/%<>=?:,\[\].-]")
_RESERVED = re.compile(r'\b(throughout|within|intersect|first_match|strong|weak|until|until_with|s_until|s_until_with|eventually|s_eventually|nexttime|s_nexttime|implies|iff|and|or|not|if|else|case|accept_on|reject_on|sync_accept_on|sync_reject_on)\b')


def _group(text, start):
    if start >= len(text) or text[start] != '(':
        raise ValueError('expected a parenthesized SVA expression')
    level = 1
    for end in range(start + 1, len(text)):
        level += (text[end] == '(') - (text[end] == ')')
        if level == 0:
            return text[start + 1:end], end + 1
    raise ValueError('unclosed SVA expression')


def _expression(text):
    tokens = list(_EXPR.finditer(text))
    if not text.strip() or ''.join(t.group() for t in tokens) != text:
        raise ValueError('unsupported SVA expression token')
    if _RESERVED.search(text) or any(s in re.sub(r'\s+', '', text) for s in ('|->', '|=>', '##', '[*', '[=', '[->')):
        raise ValueError('temporal SVA operators are unsupported')
    # User functions and multi-argument sampled calls have not been qualified.
    if re.search(r'(?<![$\w])\b[A-Za-z_]\w*\s*\(', text) or ',' in text:
        raise ValueError('SVA permits only single-argument sampled value functions')


def validate_sources(paths, clock):
    for path in paths:
        text = _COMMENTS.sub(lambda m: m.group() if m.group().startswith(chr(34)) else ' ',
                             path.read_text())
        try:
            if _FORBIDDEN.search(text):
                raise ValueError('macros, sequences, named properties, clocking blocks and cover are unsupported')
            spans = []
            for match in _ASSERT.finditer(text):
                body, end = _group(text, match.end() - 1)
                prefix = re.match(r'\s*@\(\s*posedge\s+' + re.escape(clock) + r'\s*\)\s*', body)
                if not prefix:
                    raise ValueError(f'SVA needs explicit @(posedge {clock})')
                expr = body[prefix.end():].strip()
                disable = re.match(r'disable\s+iff\s*', expr)
                if disable:
                    condition, offset = _group(expr, disable.end())
                    _expression(condition)
                    if '$' in condition:
                        raise ValueError('sampled functions in disable iff are unsupported')
                    expr = expr[offset:].strip()
                _expression(expr)
                if not re.match(r'\s*;', text[end:]):
                    raise ValueError('SVA action blocks are unsupported')
                spans.append((match.start(), end))
            for start, end in reversed(spans):
                text = text[:start] + ' ' * (end - start) + text[end:]
            if re.search(r'\b(assert|assume|property)\b', text):
                raise ValueError('only inline clocked assert/assume property is supported')
        except ValueError as error:
            raise ValueError(f'{path}: unsupported SVA subset: {error}') from error
