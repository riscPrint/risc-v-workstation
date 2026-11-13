"""Generate a pinned Sail Zicond result slice and its RVFI instruction shell.

This covers RV32 CZERO register results only. It is not a full Sail-machine proof.
"""
import hashlib
import json
from pathlib import Path
import re
import shutil

from rvw.common.proc import run_group
from .sail_subset import MODEL_COMMIT, sha

RULE = 'model/extensions/Zicond/zicond_insts.sail'
HASH = '86ea235572d08792921a264756e195c0e8d4cc728199a26476f87586297193ce'
NAMES = {'czero_eqz': 'CZERO_EQZ', 'czero_nez': 'CZERO_NEZ'}


def named_instances(text):
    """Use declared ports, including typed ports which Yosys can reorder."""
    headers = re.findall(r'(?ms)^module (\w+)\s*\((.*?)\n\);', text)
    for module, header in headers:
        ports = re.findall(r'^\s*(?:input|output|inout)\s+[^\n]*?\b(\w+)\s*(?:/\*.*?\*/)?\s*,?\s*$', header, re.M)
        pattern = re.compile(r'\b' + module + r'\s+\w+\s*\(')
        positions = list(pattern.finditer(text))
        for match in reversed(positions):
            start = match.end()
            depth, end = 1, start
            while end < len(text) and depth:
                depth += (text[end] == '(') - (text[end] == ')')
                end += 1
            if depth:
                raise ValueError('unclosed Sail module instance')
            args = text[start:end-1]
            if args.lstrip().startswith('.'):
                continue
            values, begin, nesting = [], 0, 0
            for i, char in enumerate(args):
                nesting += (char in '([{') - (char in ')]}')
                if char == ',' and nesting == 0:
                    values.append(args[begin:i].strip())
                    begin = i+1
            values.append(args[begin:].strip())
            if len(values) != len(ports):
                raise ValueError('unsupported Sail module port layout: ' + module)
            text = text[:start] + ', '.join('.'+p+'('+v+')' for p,v in zip(ports, values)) + text[end-1:]
    return text


def extract(model):
    path = Path(model) / RULE
    if sha(path) != HASH:
        raise ValueError('Zicond source does not match pinned Sail rule')
    text = path.read_text()
    layout = re.search(r'<-> 0b([01]+) @ encdec_reg\(rs2\) @ encdec_reg\(rs1\) @ encdec_zicondop\(op\) @ encdec_reg\(rd\) @ 0b([01]+)', text)
    if not layout:
        raise ValueError('unsupported Zicond encoding layout')
    result = {}
    for name, op in NAMES.items():
        condition = re.search(r'    ' + op + r' => (.+),', text)
        encoding = re.search(r'  ' + op + r' <-> 0b([01]{3}),', text)
        if not condition or not encoding:
            raise ValueError('missing Zicond rule')
        # Both the condition and selection come from the pinned source.
        selection = re.search(r'  X\(rd\) = (.+);', text)
        expression = selection[1].replace('condition', '(' + condition[1] + ')')
        expression = expression.replace('X(rs1)', 'a').replace('X(rs2)', 'b').replace('zeros()', '0x00000000')
        expression = expression.replace('b != 0x00000000', 'not_bool(b == 0x00000000)')
        result[name] = dict(expression=expression,
                            match=(int(layout[1], 2) << 25) | (int(encoding[1], 2) << 12) | int(layout[2], 2),
                            condition_line=text[:condition.start()].count('\n') + 1,
                            selection_line=text[:selection.start()].count('\n') + 1)
    return result


def instruction_shell(name, match, result_port):
    # The shell implements the pinned R-type layout. No upstream instruction
    # template is needed, so extensions missing in riscv-formal can be checked.
    return f'''
module rvfi_insn_{name}(
 input rvfi_valid,
 input [`RISCV_FORMAL_ILEN-1:0] rvfi_insn,
 input [`RISCV_FORMAL_XLEN-1:0] rvfi_pc_rdata, rvfi_rs1_rdata, rvfi_rs2_rdata, rvfi_mem_rdata,
 output spec_valid, spec_trap,
 output [4:0] spec_rs1_addr, spec_rs2_addr, spec_rd_addr,
 output [`RISCV_FORMAL_XLEN-1:0] spec_rd_wdata, spec_pc_wdata, spec_mem_addr, spec_mem_wdata,
 output [`RISCV_FORMAL_XLEN/8-1:0] spec_mem_rmask, spec_mem_wmask
);
 generate if (`RISCV_FORMAL_XLEN != 32 || `RISCV_FORMAL_ILEN != 32) begin : unsupported_width
 RVW_UNSUPPORTED_ZICOND_WIDTH unsupported();
 end endgenerate
 wire [31:0] result;
 sail_{name} semantics(.a_0(rvfi_rs1_rdata), .b_0(rvfi_rs2_rdata), .{result_port}(result));
 assign spec_valid = rvfi_valid && ((rvfi_insn & 32'hfe00707f) == 32'h{match:08x}) && !(rvfi_insn >> 16 >> 16);
 assign spec_rs1_addr = rvfi_insn[19:15];
 assign spec_rs2_addr = rvfi_insn[24:20];
 assign spec_rd_addr = rvfi_insn[11:7];
 assign spec_rd_wdata = spec_rd_addr ? result : 0;
 assign spec_pc_wdata = rvfi_pc_rdata + 4;
 assign spec_trap = 0;
 assign spec_mem_addr = 0;
 assign spec_mem_rmask = 0;
 assign spec_mem_wmask = 0;
 assign spec_mem_wdata = 0;
endmodule
'''


def generate(model, compiler, out, *, rules=None, metadata=None, shell_builder=None):
    rules = extract(model) if rules is None else rules
    compiler = shutil.which(str(compiler))
    if not compiler:
        raise ValueError('native Sail compiler required')
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    with (out / 'compiler.log').open('w') as log:
        process = run_group([compiler, '--version'], cwd=out, stdout=log, stderr=log, timeout=10)
    if process.returncode or not re.search(r'\b0\.20\.1\b', (out / 'compiler.log').read_text()):
        raise ValueError('Sail compiler 0.20.1 required')
    library = Path(compiler).resolve().parents[1] / 'share/sail/lib'
    library_hashes = {str(p.relative_to(library)): sha(p) for p in sorted(library.rglob('*.sail'))}
    if not library_hashes:
        raise ValueError('Sail compiler library unavailable')
    manifest = dict(schema='rvw.sail-zicond/1', model_commit=MODEL_COMMIT,
                    rule=dict(path=RULE, sha256=HASH), compiler_sha256=sha(compiler),
                    compiler_version=(out / 'compiler.log').read_text().strip(), compiler_library=library_hashes,
                    lowerings=['32-bit zeros() to 0x00000000', 'bitvector inequality to negated equality'],
                    implementation_options=dict(xlen=32, extension='Zicond', enabled=True,
                                                memory=False, privilege=False), files={})
    if metadata:
        manifest.update(metadata)
    for name, rule in rules.items():
        input_width = rule.get('input_width', 32)
        output_width = rule.get('output_width', 32)
        source = out / f'{name}.sail'
        source.write_text(rule.get('prelude', 'default Order dec\n$include <prelude.sail>\n') +
                          f'val main : (bits({input_width}), bits({input_width})) -> bits({output_width})\n'
                          f'function main(a, b) = {rule["expression"]}\n')
        args = [compiler, '--no-memo-z3', '--sv', '--sv-comb', '--sv-no-strings', '--sv-specialize', '2', str(source), '-o', str(out / name)]
        with (out / f'{name}.log').open('w') as log:
            process = run_group(args, cwd=out, stdout=log, stderr=log, timeout=110)
        if process.timed_out or process.returncode:
            raise ValueError('Sail backend failed: ' + name)
        raw = out / f'{name}.sv'
        available = {m[1]: m for m in re.finditer(r'(?ms)^module (\w+).*?^endmodule', raw.read_text())}
        pending, reachable = ['main'], set()
        while pending:
            current = pending.pop()
            if current in reachable:
                continue
            if current not in available:
                raise ValueError('missing Sail entry module')
            reachable.add(current)
            for candidate in available:
                if candidate != current and re.search(r'\b' + candidate + r'\s+\w+\s*\(', available[current][0]):
                    pending.append(candidate)
        modules = [module for key, module in available.items() if key in reachable]
        lowered = '\n'.join(m[0] for m in modules)
        # The combinational backend can expose undriven exception ports even
        # for these pure functions. Refuse live exception logic. Drop only
        # output declarations whose signals are never referenced elsewhere.
        for signal in ('sail_have_exception', 'sail_current_exception'):
            lines = [line for line in lowered.splitlines() if re.search(r'\b' + signal + r'\b', line)]
            if any(not line.strip().startswith('output ') for line in lines):
                raise ValueError('Sail exception logic is outside the pure slice')
            lowered = re.sub(r'^\s*output[^\n]*\b' + signal + r'\b[^\n]*\n?', '', lowered, flags=re.M)
        lowered = re.sub(r',\s*\);', '\n);', lowered)
        for module in modules:
            lowered = re.sub(r'\b' + module[1] + r'\b', 'sail_' + name + ('_' + module[1] if module[1] != 'main' else ''), lowered)
        lowered = named_instances(lowered)
        # Keep the packed types used by reachable modules. Sail emits these
        # outside the modules. Namespace enum members as well as type names.
        typedefs = {m[2]: m[0] for m in re.finditer(
            r'(?ms)^typedef\s+(?:(struct|union|enum)\s*(?:packed\s*)?\{.*?^\}|[^;\n]+?)\s+(\w+)\s*;', raw.read_text())}
        enum_members = {}
        for t, declaration in typedefs.items():
            if declaration.startswith('typedef enum'):
                body = declaration.split('{', 1)[1].split('}', 1)[0]
                enum_members[t] = set(re.findall(r'^\s*(\w+)\s*(?:,|=|$)', body, re.M))
        selected = set()
        while True:
            needed = lowered + '\n' + '\n'.join(typedefs[t] for t in selected)
            extra = {t for t in typedefs if any(re.search(r'\b' + symbol + r'\b', needed)
                     for symbol in {t} | enum_members.get(t, set()))} - selected
            if not extra:
                break
            selected.update(extra)
        if selected:
            declarations = '\n'.join(typedefs[t] for t in typedefs if t in selected)
            identifiers = set(selected)
            for t in selected:
                identifiers.update(enum_members.get(t, set()))
            lowered = declarations + '\n' + lowered
            for ident in sorted(identifiers, key=len, reverse=True):
                lowered = re.sub(r'\b' + ident + r'\b', 'sail_' + name + '_type_' + ident, lowered)
        entry = re.search(r'(?ms)^module sail_' + name + r'\s*\(.*?^endmodule', lowered)
        result_ports = re.findall(r'output logic \[' + str(output_width - 1) + r':0\] (sail_return_[0-9]+)', entry[0] if entry else '')
        if len(result_ports) != 1:
            raise ValueError('unsupported Sail result interface')
        # Yosys accepts a sized cast where Sail emits a slice of a temporary
        # concatenation. Both forms retain the low N bits of the expression.
        lowered = re.sub(r'= \{([^\n]+)\}\[([0-9]+):0\];',
                         lambda m: '= ' + str(int(m[2])+1) + "'(" + m[1] + ');', lowered)
        target = out / f'insn_{name}.v'
        shell = (shell_builder(name, rule, result_ports[0]) if shell_builder
                 else instruction_shell(name, rule['match'], result_ports[0]))
        target.write_text(lowered + '\n' + shell)
        manifest['files'][name] = dict(source_sha256=sha(source), raw_sv_sha256=sha(raw),
                                      model_sha256=sha(target), options=args[1:],
                                      property_trace=rule, generated_result=result_ports[0],
                                      shell_origin=rule.get('shell_origin', 'generated R-type shell; pinned Sail encoding layout'),
                                      backend_lowerings=['reachable module selection', 'packed type and enum namespace',
                                                         'named instance ports', 'unreferenced exception output removal',
                                                         'temporary low-bit slice to sized cast'],
                                      excluded=rule.get('excluded', ['full-machine state', 'extension-disabled illegal-instruction traps',
                                                'CSR MISA', 'privilege', 'RV64'])
                                      )
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


def main(args):
    try:
        result = generate(args.model, args.compiler, args.out)
        print(json.dumps(result) if args.json else str(Path(args.out) / 'manifest.json'))
        return 0
    except (ValueError, OSError) as exc:
        print(json.dumps(dict(status='error', error=str(exc))))
        return 2
