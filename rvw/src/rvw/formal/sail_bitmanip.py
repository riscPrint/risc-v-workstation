"""Compile pinned Sail RV32 binary bit-manipulation rules, not full-machine state."""
import re
from pathlib import Path

from .sail_subset import sha
from .sail_zicond import generate as compile_rules

HASHES = {
    'zba': '3e00db7e450e7ab30d3b429573e77b20f4127cade244d89b9955aa88b7c26fcb',
    'zbb': 'f1da764702541715c7f381cae59e56ac9b0011eb0726ecf7ffe5ecbb216ebbbe',
    'zbs': 'f50483e9792fdc8ca95f546194b993df353f53b9835447e1254ed053228479b7',
    'zbc': 'f6392032c44f9ddbf5bbacadba5d98e0392345d589c3dd8b3d42a33843784fb6',
}
PRELUDE = 'default Order dec\n$include <prelude.sail>\n'


def extract(model):
    rules, sources = {}, {}
    support = Path(model) / 'model/prelude/prelude.sail'
    if sha(support) != PRELUDE_HASH:
        raise ValueError('prelude source does not match pinned Sail rule')
    helper_text = support.read_text()
    zeros_helper = helper_text[helper_text.index('val zeros :'):helper_text.index('val ones :')]
    bool_mapping = helper_text[helper_text.index('mapping bool_bit :'):helper_text.index('// Useful for some proofs')]
    bool_helper = next(line for line in helper_text.splitlines() if line.startswith('function bool_to_bit(')) + '\n'
    bit_helpers = helper_text[helper_text.index('function not_bit('):helper_text.index('val sub_vec =')]
    shift_helpers = helper_text[helper_text.index('infix 7 >>'):helper_text.index('val reverse_bits :')]
    sources['prelude'] = dict(path='model/prelude/prelude.sail', sha256=PRELUDE_HASH)
    for ext, digest in HASHES.items():
        path = Path(model) / f'model/extensions/B/{ext}_insts.sail'
        if sha(path) != digest:
            raise ValueError(f'{ext} source does not match pinned Sail rule')
        text = path.read_text()
        sources[ext] = dict(path=str(path.relative_to(model)), sha256=digest)
        family = {'zba': 'ZBA_RTYPE', 'zbb': 'ZBB_RTYPE', 'zbs': 'ZBS_RTYPE', 'zbc': 'CLMUL'}[ext]
        body = re.search(r'function clause execute ' + family + r'\([^\n]+\) = \{(.*?)\n\}', text, re.S)[1]
        if ext == 'zba':
            expression = re.search(r'X\(rd\) = ([^;]+);', body)[1]
            variants = [(f'sh{i}add', expression.replace('shamt', f'0b{i:02b}'), i << 1) for i in (1, 2, 3)]
            enc = re.search(r'mapping clause encdec = ZBA_RTYPE\([^\n]+\)\s*<-> ([^\n]+)', text)[1]
        elif ext in ('zbb', 'zbs'):
            arms = re.findall(r'^    ([A-Z]+)\s*=> ([^,\n]+)', body, re.M)
            variants = [(op.lower(), expr, op) for op, expr in arms]
        else:
            variants = [(name.lower(), '', name) for name in ('CLMUL', 'CLMULH', 'CLMULR')]
        for name, expr, selector in variants:
            if ext == 'zbc':
                body = re.search(r'function clause execute ' + selector + r'\([^\n]+\) = \{(.*?)\n\}', text, re.S)[1]
                expr = body.replace('X(rd) = ', '').replace(';\n  RETIRE_SUCCESS', '').strip()
                expr = expr.replace('2 * xlen - 1', '63').replace('xlen - 1', '31').replace('xlen', '32')
            if ext != 'zba':
                pattern = family + r'\(rs2, rs1, rd, ' + selector + r'\)' if ext != 'zbc' else selector + r'\(rs2, rs1, rd\)'
                enc = re.search(r'mapping clause encdec = ' + pattern + r'\s*<-> ([^\n]+)', text)[1]
            tokens = enc.split(' @ ')
            bits = ''
            for token in tokens:
                if token.startswith('0b'):
                    bits += token[2:]
                elif token in ('encdec_reg(rs2)', 'encdec_reg(rs1)', 'encdec_reg(rd)'):
                    bits += '0' * 5
                elif token == 'shamt' and ext == 'zba':
                    bits += f'{selector >> 1:02b}'
                else:
                    raise ValueError('unsupported Sail encoding component: ' + token)
            if len(bits) != 32:
                raise ValueError('Sail encoding must have 32 bits')
            expr = expr.replace('X(rs1)', 'a').replace('X(rs2)', 'b').replace('rs1_val', 'a').replace('rs2_val', 'b')
            expr = expr.replace('log2_xlen - 1', '4')
            for op, cast in [('>_s', 'signed'), ('<_s', 'signed'), ('>_u', 'unsigned'), ('<_u', 'unsigned')]:
                expr = expr.replace(f'a {op} b', f'{cast}(a) {op[0]} {cast}(b)')
            if name in ('rol', 'ror'):
                rotate_name = 'rotatel' if name == 'rol' else 'rotater'
                rotate = re.search(r'function ' + rotate_name + r'\(value, shift\) =\n  ([^\n]+)', shift_helpers)[1]
                expr = rotate.replace('value', 'a').replace('shift', 'unsigned(b[4..0])').replace("'m", '32')
            if name == 'bext':
                expr = expr.replace('(a & mask) != zeros()', 'not_bool((a & mask) == zeros())')
                expr = re.sub(r'zero_extend\(bool_to_bit\((.*)\)\)', r'if \1 then 0x00000001 else 0x00000000', expr)
            prelude = PRELUDE + zeros_helper + bool_mapping + bool_helper + bit_helpers + shift_helpers + "\nval zero_extend : forall 'n 'm, 'm >= 'n. (implicit('m), bits('n)) -> bits('m)\nfunction zero_extend(m, v) = sail_zero_extend(v, m)\n"
            if ext == 'zbs':
                expr = 'let mask : bits(32) = 0x00000001 << b[4..0]; ' + expr
                expr = expr.replace('zeros()', '0x00000000')
            if ext == 'zbc':
                arithmetic = Path(model) / 'model/core/arithmetic.sail'
                if sha(arithmetic) != ARITHMETIC_HASH:
                    raise ValueError('arithmetic source does not match pinned Sail rule')
                sources['arithmetic'] = dict(path='model/core/arithmetic.sail', sha256=ARITHMETIC_HASH)
                helper = arithmetic.read_text()
                start = helper.index('val carryless_mul :')
                stop = helper.index('// Equivalent reverse carry-less multiply.')
                fixed = helper[start:stop].replace("forall 'n, 'n > 0. ", '').replace("'n", '32')
                fixed = re.sub(r'foreach \(i from 0 to \(32 - 1\)\) \{(.*?)\n  \};',
                               lambda match: '\n'.join(re.sub(r'\bi\b', str(i), match[1]) for i in range(32)), fixed, flags=re.S)
                fixed = fixed.replace('zero_extend(b)', '(0x00000000 @ b)')
                left, right = fixed.split('// Reverse carry-less multiply.')
                fixed = left.replace('zeros()', '0x0000000000000000') + right.replace('zeros()', '0x00000000')
                prelude += fixed
            rules[name] = dict(expression='{ ' + expr + ' }', prelude=prelude, match=int(bits, 2),
                               extension=ext, source=sources[ext], encoding=enc,
                               execute=body, lowerings=['XLEN=32', 'operand renaming', 'signed/unsigned comparisons',
                                          'fixed-width rotate helper expansion', 'bit result to 32-bit literals',
                                          'inequality to negated equality', '32-step carryless loop unrolling',
                                          'fixed-width zero extension and zero literals'])
    return rules, sources


PRELUDE_HASH = 'c5a3825e88088bdad0a14abf9f8645894621148fe2cc23ebdd1e6d3ea549da8f'
ARITHMETIC_HASH = 'e96d68eadd62816e02e5bed6ff428aa2098df37294675f066284370eb21dfcde'


def generate(model, compiler, out):
    model = Path(model)
    rules, sources = extract(model)
    return compile_rules(model, compiler, out, rules=rules, metadata=dict(
        schema='rvw.sail-bitmanip/1', rule=sources,
        implementation_options=dict(xlen=32, extensions=list(HASHES), enabled=True,
                                    memory=False, privilege=False),
        lowerings=['RV32 binary result slices; see each property trace']))


def main(args):
    import json
    try:
        result = generate(args.model, args.compiler, args.out)
        print(json.dumps(result) if args.json else str(Path(args.out) / 'manifest.json'))
        return 0
    except (ValueError, OSError) as exc:
        print(json.dumps(dict(status='error', error=str(exc))))
        return 2
