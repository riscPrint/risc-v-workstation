"""Extract Yosys assertion enable guards without guessing property antecedents."""
from .cores import expressions, render
import re


def metadata(model, top, kind):
    active, found = None, {}
    for line in model.splitlines():
        if line.startswith('; yosys-smt2-module '):
            active = line.split()[-1]
        match = re.match(r'; yosys-smt2-' + kind + r' (\d+) (\S+)', line)
        if match and active in (None, top):
            found[match[1]] = match[2]
    return found


def guards(model, top):
    names = metadata(model, top, 'assert')
    functions = {f[1]: f for f in expressions(model) if f[0] == 'define-fun'}
    result = []
    for index, name in names.items():
        definition = functions.get(f'|{top}_a {index}|')
        if not definition:
            continue
        body = definition[-1]
        if (not isinstance(body, list) or len(body) != 3 or body[0] != 'or'
                or not isinstance(body[2], list) or len(body[2]) != 2 or body[2][0] != 'not'):
            continue
        function = f'|rvw_activation_{index}|'
        form = ['define-fun', function, definition[2], 'Bool', body[2][1]]
        result.append({'property_id': f'{top}:{name}', 'function': function,
                       'definition': render(form), 'scope': 'Yosys assertion enable guard; not a full logical antecedent or assumption adequacy'})
    return result
