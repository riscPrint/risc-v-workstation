"""Conservative register-name candidates. These never create proof assumptions."""
import re


def suggest(gold, gate, matched):
    """Match only unique leaf names and widths among unmatched registers."""
    used_gold = {row['gold'] for row in matched}
    used_gate = {row['gate'] for row in matched}
    def index(registers, used):
        result = {}
        for name, bits in registers.items():
            if name in used:
                continue
            leaf = re.split(r'[./]', name)[-1]
            result.setdefault((leaf, len(bits)), []).append(name)
        return result
    a, b = index(gold, used_gold), index(gate, used_gate)
    return [{'gold': a[key][0], 'gate': b[key][0], 'width': key[1],
             'method': 'unique_leaf'} for key in sorted(a.keys() & b.keys())
            if len(a[key]) == len(b[key]) == 1]
