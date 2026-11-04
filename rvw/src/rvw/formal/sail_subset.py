"""Lower three pinned Sail arithmetic expressions to RV32 instruction models.

This is an expression slice, not a compilation of the full Sail machine.
The upstream riscv-formal model supplies decode, x0, PC and RVFI wiring.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

from rvw.common.proc import run_group

MODEL_COMMIT = '549e723031b34b5ffea5bbb56367be15c7a38a9e'
RULE_HASH = '07ce0b099023b6e9ce9aeedb0be15a800f2cec8dd7382a076853391537b5add3'
COMPILER_VERSION = '0.20.1'
INSTRUCTIONS = ('add', 'sub', 'addi')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def slice_source(model, instruction):
    rule = Path(model) / 'model/extensions/I/base_insts.sail'
    if sha(rule) != RULE_HASH:
        raise ValueError('Sail rule hash does not match the pinned model')
    text = rule.read_text()
    match = re.search(r'^    '+instruction.upper()+r'  => ([^,]+),$', text, re.M)
    if not match:
        raise ValueError('missing Sail arithmetic rule')
    expression = match[1].replace('X(rs1)', 'a').replace('X(rs2)', 'b')
    # immext is defined by execute ITYPE. Keep sign extension in Sail.
    return ('default Order dec\n$include <prelude.sail>\n'
            "val sign_extend : forall 'n 'm, 'm >= 'n. (implicit('m), bits('n)) -> bits('m)\n"
            'function sign_extend(m, v) = sail_sign_extend(v, m)\n'
            "val sub_vec = pure \"sub_bits\" : forall 'n. (bits('n), bits('n)) -> bits('n)\n"
            'overload operator - = {sub_vec}\n'
            'val main : (bits(32), bits(32), bits(12)) -> bits(32)\n'
            'function main(a, b, imm) = {\n' +
            ('  let immext : bits(32) = sign_extend(imm);\n' if instruction == 'addi' else '') +
            f'  {expression}\n}}\n')


def generate(model, compiler, upstream, out):
    # Validate all source rules before creating output or invoking the compiler.
    sources = {insn: slice_source(model, insn) for insn in INSTRUCTIONS}
    compiler = shutil.which(str(compiler))
    if not compiler:
        raise ValueError('native Sail compiler not found')
    out = Path(out).absolute()
    out.mkdir(parents=True, exist_ok=False)
    with (out/'compiler.log').open('w') as log:
        result = run_group([compiler, '--version'], cwd=out, stdout=log, stderr=log, timeout=30)
    version = (out/'compiler.log').read_text().strip()
    if result.returncode or not re.search(r'\b0\.20\.1\b', version):
        raise ValueError('requires Sail compiler 0.20.1')
    manifest = dict(schema='rvw.sail-subset/1', compiler=version, compiler_sha256=sha(compiler),
                    model_commit=MODEL_COMMIT, rule_sha256=RULE_HASH, xlen=32, nret=1,
                    subset=list(INSTRUCTIONS), boundary='arithmetic expressions only; upstream decode, x0 and PC',
                    files={})
    library = Path(compiler).resolve().parents[1] / 'share/sail/lib'
    manifest['compiler_library'] = {str(p.relative_to(library)): sha(p) for p in sorted(library.rglob('*.sail'))}
    if not manifest['compiler_library']:
        raise ValueError('cannot identify the native compiler library')
    for insn in INSTRUCTIONS:
        source=out/f'{insn}.sail'
        source.write_text(sources[insn])
        args=[compiler, '--no-memo-z3', '--sv', '--sv-comb', '--sv-no-strings', '--sv-specialize', '2', str(source), '-o', str(out/insn)]
        with (out/f'{insn}.log').open('w') as log:
            result=run_group(args, cwd=out, stdout=log, stderr=log, timeout=120)
        if result.returncode or result.timed_out:
            raise ValueError(f'Sail backend failed for {insn}; see {out}/{insn}.log')
        sv=out/f'{insn}.sv'
        generated=sv.read_text()
        # Keep the compiler's pure entry and its specialized helper modules.
        # Exclude the simulator top and unused runtime types. Do not rewrite logic.
        modules = re.findall(r'(?ms)^module (\w+).*?^endmodule', generated)
        generated = '\n'.join(m.group(0) for m in re.finditer(r'(?ms)^module (\w+).*?^endmodule', generated)
                              if m[1] not in {'initialize_registers', 'sail_toplevel'})
        for module in modules:
            if module not in {'initialize_registers', 'sail_toplevel'}:
                generated = re.sub(r'\b'+module+r'\b', 'sail_'+insn+('_'+module if module != 'main' else ''), generated)
        template=(Path(upstream)/'insns'/f'insn_{insn}.v').read_text()
        pattern=r'wire \[`RISCV_FORMAL_XLEN-1:0\] result = [^;]+;'
        replacement=(f'wire [31:0] result;\n  sail_{insn} sail_model('
                     '.a_0(rvfi_rs1_rdata), .b_0(rvfi_rs2_rdata), '
                     '.imm_0(rvfi_insn[31:20]), .sail_return_1(result));')
        template,count=re.subn(pattern,lambda _:replacement,template)
        if count!=1:
            raise ValueError('unsupported upstream instruction template')
        (out/f'insn_{insn}.v').write_text(generated+'\n'+template)
        manifest['files'][insn]=dict(source_sha256=sha(source), sv_sha256=sha(sv),
                                    template_sha256=sha(Path(upstream)/'insns'/f'insn_{insn}.v'),
                                    model_sha256=sha(out/f'insn_{insn}.v'), options=args[1:])
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model',required=True,type=Path)
    parser.add_argument('--compiler',default='sail')
    parser.add_argument('--riscv-formal',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args()
    try:
        generate(args.model,args.compiler,args.riscv_formal,args.out)
    except (ValueError, OSError) as exc:
        parser.exit(2, f'sail-subset: {exc}\n')


if __name__=='__main__':
    main()
