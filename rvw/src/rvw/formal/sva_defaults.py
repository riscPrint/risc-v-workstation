"""Expand simple module-local SVA clock and disable defaults."""
import re

from .sva import _group


def expand(source):
    from .temporal import Unsupported
    text = re.sub(r'//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"',
                  lambda m: ' ' * len(m[0]), source, flags=re.S)
    edits = []
    for module in re.finditer(r'\bmodule\b.*?\bendmodule\b', text, re.S):
        body = module[0]
        declarations = list(re.finditer(r'\bdefault\s+clocking\s+(?:\w+\s+)?@\s*\(([^()]*)\)\s*;\s*endclocking\b', body))
        disables = list(re.finditer(r'\bdefault\s+disable\s+iff\s*\(', body))
        if not declarations and not disables:
            continue
        if len(declarations) > 1 or len(disables) > 1:
            raise Unsupported('duplicate_default_control')
        # Defaults in nested procedural or generate scopes need their own resolver.
        named_scopes = list(re.finditer(r'\b(?:property|sequence)\s+\w+\s*;.*?\bend(?:property|sequence)\b', body, re.S))
        for default in declarations + disables:
            if any(scope.start() < default.start() < scope.end() for scope in named_scopes):
                raise Unsupported('nested_default_control')
            depth = 0
            for token in re.findall(r'\b(begin|end|generate|endgenerate|function|endfunction|task|endtask)\b', body[:default.start()]):
                depth += -1 if token in ('end', 'endgenerate', 'endfunction', 'endtask') else 1
            if depth:
                raise Unsupported('nested_default_control')
        clock = declarations[0][1].strip() if declarations else None
        disable = None
        if declarations:
            declaration = declarations[0]
            edits.append((module.start() + declaration.start(), module.start() + declaration.end(), ''))
        if disables:
            declaration = disables[0]
            disable, end = _group(body, declaration.end() - 1)
            semi = re.match(r'\s*;', body[end:])
            if not semi:
                raise Unsupported('default_disable_syntax')
            edits.append((module.start() + declaration.start(), module.start() + end + semi.end(), ''))
        named = {d[1] for d in re.finditer(r'\bproperty\s+(\w+)\s*;', body)}

        def explicit(expression):
            value = expression.strip().removesuffix(';').strip()
            if value in named:
                return value  # Resolve the named definition before applying controls.
            event = re.match(r'@\s*\(', value)
            if event:
                _, end = _group(value, event.end() - 1)
                prefix, rest = value[:end], value[end:].strip()
            else:
                prefix, rest = ('@(' + clock + ')' if clock else ''), value
            if disable is not None and not re.match(r'disable\s+iff\b', rest):
                rest = 'disable iff (' + disable + ') ' + rest
            return (prefix + ' ' + rest).strip()

        for declaration in re.finditer(r'\bproperty\s+\w+\s*;(.*?)\bendproperty\b', body, re.S):
            edits.append((module.start() + declaration.start(1), module.start() + declaration.end(1),
                          explicit(declaration[1]) + '; '))
        for statement in re.finditer(r'\b(?:assert|assume|cover)\s+property\s*\(', body):
            expression, end = _group(body, statement.end() - 1)
            edits.append((module.start() + statement.end(), module.start() + end - 1, explicit(expression)))
    for start, end, replacement in sorted(edits, reverse=True):
        source = source[:start] + replacement + source[end:]
    return source
