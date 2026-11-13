"""Project-declared register-only custom op timing, with no semantics claim."""
import re


def validate(rules, latencies):
    if not isinstance(rules, list):
        raise ValueError('custom instructions must be a list')
    for rule in rules:
        if set(rule) != {'name', 'mask', 'match', 'sources', 'writes_rd'}:
            raise ValueError('custom rule requires name, mask, match, sources, writes_rd')
        if not isinstance(rule['name'], str) or not re.fullmatch('custom_[a-zA-Z0-9_]+', rule['name']) or rule['name'] not in latencies:
            raise ValueError('custom rule requires its own latency class')
        mask, match = rule['mask'], rule['match']
        if any(type(v) is not int or not 0 <= v < 2**32 for v in (mask, match)) or match & ~mask:
            raise ValueError('invalid custom mask or match')
        if mask & 0x7f != 0x7f or match & 0x7f not in (0x0b,0x2b,0x5b,0x7b):
            raise ValueError('custom rules must select a reserved custom major opcode')
        if not isinstance(rule['sources'], list) or len(set(rule['sources'])) != len(rule['sources']) or any(s not in ('rs1','rs2') for s in rule['sources']):
            raise ValueError('custom sources must select rs1 and/or rs2')
        if type(rule['writes_rd']) is not bool:
            raise ValueError('custom writes_rd must be boolean')
    for i, a in enumerate(rules):
        for b in rules[i+1:]:
            if not (a['match'] ^ b['match']) & (a['mask'] & b['mask']):
                raise ValueError('custom opcode rules overlap')


def decode(row, rules):
    matches = [r for r in rules if row['insn'] & r['mask'] == r['match']]
    if not matches:
        return None
    rule = matches[0]
    if row['mem_rmask'] or row['mem_wmask'] or row['pc_next'] != row['pc'] + 4:
        raise ValueError('custom timing supports register-only fallthrough operations')
    sources = []
    for name in rule['sources']:
        register = row['insn'] >> (15 if name == 'rs1' else 20) & 31
        if row[name] != register:
            raise ValueError('custom C2 source register does not match encoding')
        sources.append(register)
    dest = row['insn'] >> 7 & 31 if rule['writes_rd'] else 0
    if row['rd'] != dest:
        raise ValueError('custom C2 destination does not match encoding')
    return rule['name'], tuple(sources), dest
