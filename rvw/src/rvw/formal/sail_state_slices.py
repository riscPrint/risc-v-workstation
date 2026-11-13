"""Source-derived FP results, CSR intents and privileged entry decisions.

These kernels expose declared state. They do not replace the Sail machine.
"""
import json
from pathlib import Path
import re

from .sail_subset import sha
from .sail_zicond import generate as compile_rules

PREFIX = 'default Order dec\n$include <prelude.sail>\n'
HASHES = {
    'model/prelude/prelude.sail': 'c5a3825e88088bdad0a14abf9f8645894621148fe2cc23ebdd1e6d3ea549da8f',
    'model/extensions/FD/zfh_insts.sail': 'cf7b46524e20c32f206c48813fe06150fea243f45442fb158a07e1299eb25126',
    'model/extensions/FD/fext_insts.sail': '05800b11a134971369ec4a9d06ba9b471b8a1cf46d74f0f68ad5e9a635b2c4a1',
    'model/extensions/FD/dext_insts.sail': '4e8252ecb019d1af118e5d72637714b76b6f0659d96489955bf00059d4f6d104',
    'model/extensions/Zicsr/zicsr_insts.sail': '137441624950ab9b17258fae874a6484d81b39fc5e641267f5c68a325f212e6e',
    'model/extensions/I/base_insts.sail': '07ce0b099023b6e9ce9aeedb0be15a800f2cec8dd7382a076853391537b5add3',
}
EXCLUDED = ['full-machine transition', 'CSR address legality and WARL writes',
            'floating-point register boxing and extension-enable traps',
            'privileged return state updates and target validation',
            'WFI timeout, wakeup and progress', 'floating-point arithmetic and rounding']


def block(text, pattern):
    match = re.search(pattern, text, re.S)
    if not match:
        raise ValueError('unsupported pinned Sail rule layout')
    return match


def extract(model):
    texts, sources, rules = {}, {}, {}
    for name, digest in HASHES.items():
        path = Path(model) / name
        if sha(path) != digest:
            raise ValueError('source differs from pinned Sail rule: ' + name)
        texts[name] = path.read_text()
        sources[name] = dict(path=name, sha256=digest)
    support = texts['model/prelude/prelude.sail']
    prefix = PREFIX + support[support.index('function not_bit('):support.index('val sub_vec =')]

    def add(name, path, execute, expression, **kwargs):
        kwargs.setdefault('input_width', 32)
        kwargs.setdefault('output_width', 32)
        kwargs.setdefault('shell_origin', 'generated result checker; project selects the decoded operation')
        rules[name] = dict(expression=expression, execute=execute,
                           source=sources[path], line=texts[path][:texts[path].index(execute)].count('\n') + 1,
                           excluded=EXCLUDED, **kwargs)

    for suffix, width, filename in [('H', 16, 'zfh'), ('S', 32, 'fext'), ('D', 64, 'dext')]:
        path = f'model/extensions/FD/{filename}_insts.sail'
        text = texts[path]
        split = block(text, r'function fsplit_' + suffix + r'\(.*?\n  [^\n]+')[0]
        make = block(text, r'function fmake_' + suffix + r'\(.*?\n  [^\n]+')[0]
        for operation in ('FSGNJ', 'FSGNJN', 'FSGNJX'):
            name = (operation + '_' + suffix).lower()
            execute = block(text, r'function clause execute [^\n]+, ' + operation + '_' + suffix + r'\) = \{.*?\n\}')[0]
            body = execute.split('= {', 1)[1].rsplit('}', 1)[0]
            body = re.sub(r'F_or_X_' + suffix + r'\(rs1\)', 'a', body)
            body = re.sub(r'F_or_X_' + suffix + r'\(rs2\)', 'b', body)
            body = re.sub(r'F_or_X_' + suffix + r'\(rd\) = (\w+);\s*RETIRE_SUCCESS', r'\1', body)
            encoding = block(text, r'mapping clause encdec = [^\n]+, ' + operation + '_' + suffix + r'\)\s*<-> ([^\n]+)')[1]
            bits = re.sub(r'encdec_freg\((?:rs1|rs2|rd)\)', '0b00000', encoding)
            bits = ''.join(token.strip()[2:].replace('_', '') for token in bits.split('@'))
            if len(bits) != 32 or set(bits) - {'0', '1'}:
                raise ValueError('unsupported FP instruction encoding')
            add(name, path, execute, '{' + body + '}', input_width=width, output_width=width,
                prelude=prefix + split + '\n' + make + '\n', match=int(bits, 2), mask=0xfe00707f,
                kind='fp_result', lowerings=['replace architectural operand accessors with decoded operands',
                                             'replace destination write with returned bitvector'],
                shell_origin='generated FP encoding and result checker; no integer x0 suppression')

    path = 'model/extensions/Zicsr/zicsr_insts.sail'
    text = texts[path]
    access = block(text, r'function csr_access_type\(.*?\n  \}')[0]
    helper = access.replace('function csr_access_type(', 'function access(')
    helper = helper.replace('-> CSRAccessType', '-> bits(2)')
    for label, bits in [('CSRReadWrite', '0b11'), ('CSRWrite', '0b01'), ('CSRRead', '0b10')]:
        helper = helper.replace('=> ' + label, '=> ' + bits)
    write = block(text, r'let write_val : xlenbits = match op \{(.*?)\n          \};')[1]
    for operation in ('CSRRW', 'CSRRS', 'CSRRC'):
        expression = block(write, operation + r' => ([^,\n]+)')[1]
        expression = expression.replace('read_val', 'a').replace('rs1_val', 'b')
        add(operation.lower() + '_write', path, 'let write_val : xlenbits = match op {' + write + '\n          };',
            expression, prelude=prefix, kind='csr_write_value')
        add(operation.lower() + '_access', path, access,
            f'access({operation}, a[4..0] == 0b00000, b[4..0] == 0b00000)',
            prelude=prefix + 'enum csrop = {CSRRW, CSRRS, CSRRC}\n' + helper + '\n',
            output_width=2, kind='csr_access',
            lowerings=['read/write access enum to two bits: read=bit1, write=bit0'])

    path = 'model/extensions/I/base_insts.sail'
    text = texts[path]
    context = '''enum Privilege = {User, Supervisor, Machine, VirtualUser, VirtualSupervisor}
enum Extension = {Ext_S}
'''
    operands = '''let cur_privilege : Privilege = match a[2..0] {
  0b000 => User, 0b001 => Supervisor, 0b011 => Machine,
  0b100 => VirtualUser, _ => VirtualSupervisor };
'''
    replacements = {'cur_privilege != Machine': 'not_bool(a[2..0] == 0b011)',
                    'not(ext_check_xret_priv(Machine))': 'b[0..0] == 0b0',
                    'not(ext_check_xret_priv(Supervisor))': 'b[0..0] == 0b0',
                    'not(currentlyEnabled(Ext_S))': 'b[1..1] == 0b0',
                    'mstatus[TSR]': 'a[3..3]', 'hstatus[VTSR]': 'a[4..4]', 'mstatus[TW]': 'a[5..5]',
                    'plat_wfi_available_to_usermode': 'a[6..6] == 0b1',
                    'Illegal_Instruction()': '0b01', 'Virtual_Instruction()': '0b10',
                    'Ext_XRET_Priv_Failure()': '0b11', 'Enter_Wait(WAIT_WFI)': '0b00'}
    for operation in ('MRET', 'SRET', 'WFI'):
        execute = block(text, r'function clause execute ' + operation + r'\(\) =\s*(.*?)\n\s*mapping clause assembly')[0]
        execute = re.split(r'\n\s*mapping clause assembly', execute)[0]
        body = re.split(r'=\s*', execute, maxsplit=1)[1]
        if operation != 'WFI':
            body = body[1:body.index('else {')] + 'else 0b00'
        for old, new in replacements.items():
            body = body.replace(old, new)
        add(operation.lower() + '_entry', path, execute, '{' + operands + body + '\n}',
            prelude=prefix + context, output_width=2, kind='privileged_entry',
            lowerings=['declared privilege and control bits replace architectural accessors',
                       'terminal result enum to two-bit decision', 'return-state branch excluded'])
    return rules, sources


def shell(name, rule, result_port):
    width, output = rule.get('input_width', 32), rule.get('output_width', 32)
    decode = f"((insn & 32'h{rule['mask']:08x}) == 32'h{rule['match']:08x})" if 'match' in rule else "1'b1"
    context = ' && (a[2:0] == 0 || a[2:0] == 1 || a[2:0] == 3 || a[2:0] == 4 || a[2:0] == 5)' if rule['kind'] == 'privileged_entry' else ''
    return f'''module sail_check_{name}(input clk,valid,input [31:0] insn,
input [{width-1}:0] a,b,input [{output-1}:0] observed,output check_valid,output [{output-1}:0] expected);
assign check_valid = valid && {decode}{context};
sail_{name} semantics(.a_0(a),.b_0(b),.{result_port}(expected));
always @(posedge clk) if(check_valid) assert(observed == expected);
endmodule
'''


def generate(model, compiler, out):
    rules, sources = extract(model)
    manifest = compile_rules(model, compiler, out, rules=rules, shell_builder=shell, metadata=dict(
        schema='rvw.sail-state-slices/1', rule=sources,
        implementation_options=dict(operand_widths=[16, 32, 64], csr_xlen=32, full_machine=False),
        lowerings=['typed operand and control slices; see each property trace']))
    manifest['status'] = 'generated'
    manifest['limits'] = EXCLUDED
    (Path(out) / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


def main(args):
    try:
        result = generate(args.model, args.compiler, args.out)
        print(json.dumps(result) if args.json else str(Path(args.out) / 'manifest.json'))
        return 0
    except (ValueError, OSError) as exc:
        print(json.dumps(dict(status='error', error=str(exc))))
        return 2
