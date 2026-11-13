"""Per-instance parameters and declared SV types from the slang JSON AST (`read_slang --dump-ast`)."""
from __future__ import annotations

import json
import re

# AST symbol kinds that declare a value with a type.
VALUE_KINDS = {'Variable', 'Net', 'Port'}


def parse_ast(text: str) -> dict:
    """The AST is the first JSON object on stdout; slang prints its summary after it."""
    start = text.find('{')
    if start < 0:
        raise ValueError('slang printed no AST')
    obj, _ = json.JSONDecoder().raw_decode(text[start:])
    return obj


def instances(ast: dict) -> tuple[dict, dict]:
    """Return ({instance path: {parameter: value}}, {signal path: SV type}).

    Paths drop the toplevel name and join instance and generate block names with '.', as the
    netlist cell and net names do. Uninstantiated generate blocks are skipped."""
    params: dict[str, dict] = {}
    types: dict[str, str] = {}

    def body(members, prefix, path):
        for m in members or []:
            kind, name = m.get('kind'), m.get('name', '')
            if kind == 'Instance':
                child = f'{prefix}{name}'
                b = m.get('body', {})
                params[child] = {p['name']: p.get('value') for p in b.get('members', [])
                                 if p.get('kind') == 'Parameter' and not p.get('isLocal')}
                body(b.get('members'), child + '.', child)
            elif kind == 'GenerateBlock':
                if not m.get('isUninstantiated'):
                    body(m.get('members'), f'{prefix}{name}.' if name else prefix, path)
            elif kind == 'GenerateBlockArray':
                for i, g in enumerate(m.get('members') or []):
                    if g.get('kind') == 'GenerateBlock' and not g.get('isUninstantiated'):
                        index = g.get('constructIndex', i)
                        body(g.get('members'), f'{prefix}{name}[{index}].', path)
            elif kind in VALUE_KINDS and name and 'type' in m:
                # Named types print as `<symbol address> pkg::name`; drop the address.
                types.setdefault(prefix + name, re.sub(r'^\d+ ', '', m['type']))

    for top in ast.get('members', []):
        if top.get('kind') == 'Instance':
            b = top.get('body', {})
            params[''] = {p['name']: p.get('value') for p in b.get('members', [])
                          if p.get('kind') == 'Parameter' and not p.get('isLocal')}
            body(b.get('members'), '', '')
    return params, types
