"""Versioned pure R-type custom instructions and software/verification exports."""
import json
from pathlib import Path
import re

MASK = 0xfe00707f
OPS = {'add': '+', 'sub': '-', 'xor': '^', 'and': '&', 'or': '|', 'sll': '<<', 'srl': '>>'}


def expression(tree, xlen, a=None, b=None, depth=0):
    """Evaluate or emit the same explicit, finite bitvector expression tree."""
    if depth > 12:
        raise ValueError('semantic expression too deep')
    mask = (1 << xlen) - 1
    if isinstance(tree, str) and tree in ('rs1', 'rs2'):
        return ('a' if tree == 'rs1' else 'b') if a is None else a if tree == 'rs1' else b
    if type(tree) is int and 0 <= tree <= mask:
        return f"{xlen}'h{tree:x}" if a is None else tree
    if not isinstance(tree, list) or len(tree) != 3 or tree[0] not in OPS:
        raise ValueError('result needs an add/sub/xor/and/or/sll/srl bitvector tree')
    op = tree[0]
    lhs, rhs = [expression(t, xlen, a, b, depth + 1) for t in tree[1:]]
    if a is None:
        if op in ('sll', 'srl'):
            rhs = f'({rhs} & {xlen - 1})'
        return f'({lhs} {OPS[op]} {rhs})'
    if op == 'add': value = lhs + rhs
    elif op == 'sub': value = lhs - rhs
    elif op == 'xor': value = lhs ^ rhs
    elif op == 'and': value = lhs & rhs
    elif op == 'or': value = lhs | rhs
    elif op == 'sll': value = lhs << (rhs & (xlen - 1))
    else: value = lhs >> (rhs & (xlen - 1))
    return value & mask


def validate(data):
    if data.get('schema') != 'rvw.custom-isa/1' or not re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', data.get('version', '')):
        raise ValueError('custom ISA needs schema rvw.custom-isa/1 and semantic version')
    xlen = data['xlen']
    if type(xlen) is not int or xlen not in (32, 64):
        raise ValueError('custom ISA supports XLEN 32 or 64')
    instructions = data['instructions']
    if not isinstance(instructions, list) or not instructions:
        raise ValueError('instructions must be nonempty')
    names = set()
    for row in instructions:
        name = row['name']
        if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_]*', name) or name in names:
            raise ValueError('instructions need distinct simple names')
        names.add(name)
        for key in ('mask', 'match'):
            value = row[key]
            row[key] = int(value, 0) if isinstance(value, str) else value
            if type(row[key]) is not int or not 0 <= row[key] < 1 << 32:
                raise ValueError('encoding must fit 32 bits')
        if row['mask'] != MASK or row['match'] & ~MASK or row['match'] & 127 not in (0x0b, 0x2b, 0x5b, 0x7b):
            raise ValueError('only custom-opcode R-type encodings with free rd/rs1/rs2 are supported')
        if row.get('operands') != ['rd', 'rs1', 'rs2'] or row.get('state') != []:
            raise ValueError('declare operands [rd,rs1,rs2] and empty extra state')
        if row.get('effects') != {'memory': 'none', 'trap': 'none', 'pc': 'next'}:
            raise ValueError('declare memory/trap none and next PC')
        expression(row['result'], xlen)
    for i, row in enumerate(instructions):
        for other in instructions[:i]:
            if (row['match'] ^ other['match']) & (row['mask'] & other['mask']) == 0:
                raise ValueError('custom encoding conflict')
    return data


def load(path):
    return validate(json.loads(Path(path).read_text()))


def encode(row, rd, rs1, rs2):
    if any(type(r) is not int or not 0 <= r < 32 for r in (rd, rs1, rs2)):
        raise ValueError('register index must be 0..31')
    return row['match'] | rd << 7 | rs1 << 15 | rs2 << 20


def decode(data, word):
    for row in data['instructions']:
        if word & row['mask'] == row['match']:
            return dict(name=row['name'], rd=(word >> 7) & 31, rs1=(word >> 15) & 31, rs2=(word >> 20) & 31)
    return None


def reference_checks(data):
    """External vectors and alternate expressions are inputs, not generated oracles."""
    results, gaps = [], []
    mask = (1 << data['xlen']) - 1
    for row in data['instructions']:
        vectors = row.get('reference_vectors', [])
        if not vectors:
            gaps.append(row['name'] + ': independent reference vectors missing')
        for v in vectors:
            if any(type(v[k]) is not int or not 0 <= v[k] <= mask for k in ('rs1','rs2','expected')):
                raise ValueError('reference vector values must fit XLEN')
            actual = expression(row['result'], data['xlen'], v['rs1'], v['rs2'])
            results.append(dict(instruction=row['name'], kind='reference', expected=v['expected'], actual=actual,
                                status='consistent' if actual == v['expected'] else 'mismatch'))
        mutants = row.get('mutants', [])
        if not mutants:
            gaps.append(row['name'] + ': independently authored mutants missing')
        for mutant in mutants:
            expression(mutant['result'], data['xlen'])
            killed = any(expression(mutant['result'],data['xlen'],v['rs1'],v['rs2']) != v['expected'] for v in vectors)
            results.append(dict(instruction=row['name'], kind='mutant', id=mutant['id'],
                                status='detected' if killed else 'survived'))
            if not killed:
                gaps.append(row['name'] + ': surviving mutant ' + mutant['id'])
    return results, gaps


def generate(manifest, out, backend_sources=None):
    import hashlib
    data = load(manifest)
    checks, gaps = reference_checks(data)
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    xlen = data['xlen']
    ctype = 'uint32_t' if xlen == 32 else 'uint64_t'
    mode = 'SI' if xlen == 32 else 'DI'
    headers = ['#pragma once', '#include <stdint.h>']
    assembly, rtl, md, vectors, sequences = [], [], [], [], []
    for row in data['instructions']:
        name, match = row['name'], row['match']
        op, f3, f7 = match & 127, (match >> 12) & 7, match >> 25
        directive = f'.insn r {op}, {f3}, {f7}, %0, %1, %2'
        headers += [f'static inline {ctype} rvw_{name}({ctype} a, {ctype} b) {{',
                    f'  {ctype} result; __asm__("{directive}" : "=r"(result) : "r"(a), "r"(b));',
                    '  return result;', '}']
        assembly += [f'.macro {name} rd, rs1, rs2',
                     f'  .insn r {op}, {f3}, {f7}, \\rd, \\rs1, \\rs2', '.endm']
        rtl += [f'module rvw_custom_{name}(input [{xlen-1}:0] a,b, output [{xlen-1}:0] result);',
                f'assign result = {expression(row["result"], xlen)};', 'endmodule']
        md += [f'(define_insn "rvw_{name}"',
               f' [(set (match_operand:{mode} 0 "register_operand" "=r")',
               f'       (unspec:{mode} [(match_operand:{mode} 1 "register_operand" "r")',
               f'                     (match_operand:{mode} 2 "register_operand" "r")] UNSPEC_RVW_{name.upper()}))]',
               f' "" "{directive}" [(set_attr "type" "arith")])']
        boundary = [0, 1, (1 << xlen)-1, 1 << (xlen-1), (1 << (xlen-1))-1]
        cases = [dict(rs1=a,rs2=b,expected=expression(row['result'],xlen,a,b),origin='generated') for a in boundary for b in boundary]
        cases += [dict(v, origin='project-reference') for v in row.get('reference_vectors', [])]
        vectors += [dict(v, instruction=name) for v in cases]
        sequences += [dict(instruction=name, cases=['rd aliases rs1', 'rd aliases rs2', 'rs1 aliases rs2', 'x0 destination'],
                          exceptions='none declared; illegal encodings and disabled extension need separate DUT tests')]
    enum = '(define_c_enum "unspec" [' + ' '.join('UNSPEC_RVW_' + r['name'].upper() for r in data['instructions']) + '])'
    (out / 'custom.h').write_text('\n'.join(headers) + '\n')
    (out / 'custom.S').write_text('\n'.join(assembly) + '\n')
    (out / 'custom.v').write_text('\n'.join(rtl) + '\n')
    (out / 'custom.md').write_text(enum + '\n' + '\n'.join(md) + '\n')
    (out / 'interface.json').write_text(json.dumps(data, indent=2) + '\n')
    decoder = 'import json\nDATA = json.loads(' + repr(json.dumps(data)) + ')\n' + '''def decode(word):
    for row in DATA['instructions']:
        if word & row['mask'] == row['match']:
            return dict(name=row['name'], rd=(word >> 7)&31, rs1=(word >> 15)&31, rs2=(word >> 20)&31)
    return None
'''
    (out / 'custom_disasm.py').write_text(decoder)
    tests = ['.text', '.globl rvw_custom_tests', 'rvw_custom_tests:']
    for v in vectors:
        row = next(r for r in data['instructions'] if r['name'] == v['instruction'])
        tests += [f"li t0, {v['rs1']}", f"li t1, {v['rs2']}",
                  f".insn r {row['match']&127}, {(row['match']>>12)&7}, {row['match']>>25}, t2, t0, t1",
                  f"li t3, {v['expected']}", 'bne t2, t3, .Lrvw_custom_fail']
    for row in data['instructions']:
        op, f3, f7 = row['match'] & 127, (row['match'] >> 12) & 7, row['match'] >> 25
        for rd, rs1, rs2, a, b in [('t0','t0','t1',6,3), ('t1','t0','t1',6,3), ('t2','t0','t0',6,6)]:
            expected = expression(row['result'], xlen, a, b)
            tests += [f'li t0, {a}', f'li t1, {b}', f'.insn r {op}, {f3}, {f7}, {rd}, {rs1}, {rs2}',
                      f'li t3, {expected}', f'bne {rd}, t3, .Lrvw_custom_fail']
        tests += ['li t0, 6', 'li t1, 3', f'.insn r {op}, {f3}, {f7}, zero, t0, t1',
                  'add t2, zero, zero', 'bnez t2, .Lrvw_custom_fail']
    tests += ['li a0, 0', 'ret', '.Lrvw_custom_fail:', 'li a0, 1', 'ret']
    (out / 'tests.S').write_text('\n'.join(tests) + '\n')
    plan = dict(schema='rvw.custom-plan/1', operand_bins=['zero','one','all ones','sign bit','maximum signed'],
                vectors=vectors, sequences=sequences, reference_checks=checks, gaps=gaps,
                limits=['Generated vectors share the declared semantics.', 'Reference/mutant independence needs author review.',
                        'Dependency tests are generated; execution on the DUT is not established.'])
    (out / 'plan.json').write_text(json.dumps(plan, indent=2) + '\n')
    report = dict(schema='rvw.custom-generation/1', status='mismatch' if any(c['status']=='mismatch' for c in checks) else 'generated',
                  manifest_sha256=hashlib.sha256(Path(manifest).read_bytes()).hexdigest(), checks=checks, gaps=gaps,
                  toolchains={'assembler':'GNU binutils .insn r', 'intrinsics':'GNU C inline asm',
                              'compiler_description':'GCC RISC-V machine-description fragment; integration build NOT RUN',
                              'disassembler':'standalone Python decoder; no objdump plugin'},
                  licenses={'GNU GCC':'GPL-3.0-or-later', 'GNU binutils':'GPL-3.0-or-later',
                            'plugins':'no compiler or disassembler plugin is installed'},
                  limits='Pure register R-type custom opcodes only. No extra state, memory or trap effects. No DUT qualification.')
    from .custom_backends import export
    report['backend_exports']=export(data,out,backend_sources)
    (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main(args):
    try:
        result = generate(args.manifest, args.out, getattr(args, 'backend_sources', None))
        print(json.dumps(result) if args.json else result['status'])
        return 1 if result['status'] == 'mismatch' else 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps(dict(status='error', error=str(exc))))
        return 2
