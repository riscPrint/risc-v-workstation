"""Compiler patches and Spike extensions for pure version-1 custom semantics."""
import difflib
import hashlib
import json
from pathlib import Path
import re

from .custom_isa import OPS

GCC_MD='gcc/config/riscv/riscv.md'
GCC_BUILTINS='gcc/config/riscv/riscv-builtins.cc'
GCC_TYPES='gcc/config/riscv/riscv-ftypes.def'
LLVM_INSNS='llvm/lib/Target/RISCV/RISCVInstrInfo.td'
LLVM_INTRINSICS='llvm/include/llvm/IR/IntrinsicsRISCV.td'


def cpp(tree,xlen):
    if isinstance(tree,str):
        if tree not in ('rs1','rs2'):raise ValueError('unsupported pure operand')
        return 'a' if tree=='rs1' else 'b'
    if type(tree) is int:return f'word_t(0x{tree:x}ULL)'
    op=tree[0];lhs,rhs=(cpp(value,xlen) for value in tree[1:])
    if op in ('sll','srl'):rhs=f'({rhs} & {xlen-1})'
    return f'word_t(({lhs}) {OPS[op]} ({rhs}))'


def spike(data,name):
    xlen=data['xlen'];lines=['#include <riscv/extension.h>','#include <cstdint>',
        'using word_t = uint'+str(xlen)+'_t;']
    rows=data['instructions']
    for row in rows:
        ident=row['name']
        lines += [f'static word_t eval_{ident}(word_t a,word_t b) {{ return {cpp(row["result"],xlen)}; }}',
                  f'static reg_t exec_{ident}(processor_t* p,insn_t insn,reg_t pc) {{',
                  f'  word_t value=eval_{ident}(word_t(p->get_state()->XPR[insn.rs1()]),word_t(p->get_state()->XPR[insn.rs2()]));',
                  '  reg_t canonical='+('reg_t(int64_t(int32_t(value)))' if xlen==32 else 'reg_t(value)')+';',
                  '  if(insn.rd()) { p->get_state()->XPR.write(insn.rd(),canonical); p->get_state()->log_reg_write[insn.rd()<<4]={canonical,0}; }',
                  '  return '+('reg_t(int64_t(int32_t(uint32_t(pc+4))))' if xlen==32 else 'pc+4')+';', '}']
    lines += ['extern "C" uint64_t rvw_custom_eval(unsigned index,uint64_t a,uint64_t b) {','  switch(index) {']
    lines += [f'  case {i}: return eval_{row["name"]}(word_t(a),word_t(b));' for i,row in enumerate(rows)]
    lines += ['  default: return 0; }','}',
              'class rvw_reg_arg final : public arg_t { unsigned shift; public:',
              ' explicit rvw_reg_arg(unsigned value):shift(value) {}',
              ' std::string to_string(insn_t insn) const override { return "x"+std::to_string((insn.bits()>>shift)&31); } };',
              'static rvw_reg_arg rd_arg(7),rs1_arg(15),rs2_arg(20);',
              f'class {name}_t final : public extension_t {{ public:',
              f' const char* name() const override {{ return "{name}"; }}',
              ' std::vector<insn_desc_t> get_instructions(const processor_t&) override { return {']
    for row in rows:
        handler='exec_'+row['name'];bad='::illegal_instruction'
        rv32,rv64=(handler,bad) if xlen==32 else (bad,handler)
        lines += [f'  {{0x{row["match"]:x},0x{row["mask"]:x},{rv32},{rv64},{bad},{bad},{rv32},{rv64},{bad},{bad}}},']
    lines += [' }; }',' std::vector<disasm_insn_t*> get_disasms(const processor_t*) override { return {']
    lines += [f'  new disasm_insn_t("{row["name"]}",0x{row["match"]:x},0x{row["mask"]:x},{{&rd_arg,&rs1_arg,&rs2_arg}}),' for row in rows]
    lines += [' }; }','};',f'REGISTER_EXTENSION({name}, []() {{ return new {name}_t; }})']
    return '\n'.join(lines)+'\n'


def fragments(data):
    xlen=data['xlen'];mode='SI' if xlen==32 else 'DI';itype='i'+str(xlen)
    llvm=[];intrinsics=['let TargetPrefix = "riscv" in {'];gcc=[]
    for row in data['instructions']:
        name=row['name'];match=row['match'];opcode=match&127;f3=(match>>12)&7;f7=match>>25
        custom={0x0b:0,0x2b:1,0x5b:2,0x7b:3}[opcode]
        llvm += [f'let Predicates = [IsRV{xlen}], hasSideEffects = 0, mayLoad = 0, mayStore = 0 in {{',
                 f'def RVW_{name.upper()} : RVInstR<0b{f7:07b},0b{f3:03b},OPC_CUSTOM_{custom},',
                 f'  (outs GPR:$rd),(ins GPR:$rs1,GPR:$rs2),"{name}","$rd, $rs1, $rs2">;',
                 f'def : Pat<(int_riscv_rvw_{name} GPR:$rs1,GPR:$rs2),(RVW_{name.upper()} GPR:$rs1,GPR:$rs2)>;', '}']
        intrinsics += [f'def int_riscv_rvw_{name} : Intrinsic<[llvm_{itype}_ty],[llvm_{itype}_ty,llvm_{itype}_ty],[IntrNoMem]>;']
        gcc += [f'(define_insn "rvw_{name}"',
                f' [(set (match_operand:{mode} 0 "register_operand" "=r")',
                f'   (unspec:{mode} [(match_operand:{mode} 1 "register_operand" "r")',
                f'               (match_operand:{mode} 2 "register_operand" "r")] UNSPEC_RVW_{name.upper()}))]',
                f' "'+('!TARGET_64BIT' if xlen==32 else 'TARGET_64BIT')+'"',
                f' ".insn r {opcode}, {f3}, {f7}, %0, %1, %2" [(set_attr "type" "arith")])']
    intrinsics += ['}']
    return {'gcc/config/riscv/rvw-custom.md':'\n'.join(gcc)+'\n',
            'llvm/lib/Target/RISCV/RISCVInstrInfoRVWCustom.td':'\n'.join(llvm)+'\n',
            'llvm/include/llvm/IR/IntrinsicsRVWCustom.td':'\n'.join(intrinsics)+'\n'}


def base_sources(root):
    root=Path(root);manifest=json.loads((root/'sources.json').read_text())
    if manifest.get('schema')!='rvw.custom-backend-bases/1':raise ValueError('expected hash-pinned compiler bases')
    files={row['path']:row for row in manifest['files']}
    if len(files)!=len(manifest['files']):raise ValueError('duplicate compiler source path')
    if any(not re.fullmatch(r'[0-9a-f]{40}',row.get('revision','')) for row in files.values()):raise ValueError('compiler sources need full revision IDs')
    required={GCC_MD,GCC_BUILTINS,GCC_TYPES,LLVM_INSNS,LLVM_INTRINSICS}
    if not required<=files.keys():raise ValueError('compiler bases need GCC MD/builtins/types and LLVM instructions/intrinsics')
    texts={}
    for name in required:
        raw=(root/name).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=files[name]['sha256']:raise ValueError('compiler base hash differs: '+name)
        texts[name]=raw.decode()
    return texts,manifest


def patches(data,new_files,source_root):
    old={};new=dict(new_files);identity=None;gaps=[]
    if source_root:
        old,identity=base_sources(source_root)
        new.update(old)
        names=''.join('  UNSPEC_RVW_'+row['name'].upper()+'\n' for row in data['instructions'])
        md,count=re.subn(r'(\(define_c_enum "unspec"\s*\[)(.*?)(\]\))',lambda m:m[1]+m[2]+names+m[3],old[GCC_MD],count=1,flags=re.S)
        if count!=1:raise ValueError('unsupported GCC unspec enum layout')
        new[GCC_MD]=md.rstrip()+'\n\n(include "rvw-custom.md")\n'
        marker='static const struct riscv_builtin_description riscv_builtins[] = {'
        if old[GCC_BUILTINS].count(marker)!=1:raise ValueError('unsupported GCC builtin table')
        xlen=data['xlen'];mode='USI' if xlen==32 else 'UDI'
        if f'DEF_RISCV_FTYPE (2, ({mode}, {mode}, {mode}))' not in old[GCC_TYPES]:raise ValueError('GCC binary unsigned builtin type missing')
        entries='\n'.join(f'  RISCV_BUILTIN_NO_PREFIX (rvw_{row["name"]}, "rvw_{row["name"]}", RISCV_BUILTIN_DIRECT, RISCV_{mode}_FTYPE_{mode}_{mode}, rvw_custom),' for row in data['instructions'])
        availability='AVAIL (rvw_custom, '+('!TARGET_64BIT' if xlen==32 else 'TARGET_64BIT')+')\n\n'
        new[GCC_BUILTINS]=old[GCC_BUILTINS].replace(marker,availability+marker+'\n'+entries)
        new[LLVM_INSNS]=old[LLVM_INSNS].rstrip()+'\n\ninclude "RISCVInstrInfoRVWCustom.td"\n'
        new[LLVM_INTRINSICS]=old[LLVM_INTRINSICS].rstrip()+'\n\ninclude "llvm/IR/IntrinsicsRVWCustom.td"\n'
    else:gaps.append('pinned compiler bases absent; patches add fragments only, without parent includes or builtin registration')
    result={}
    for prefix in ('gcc','llvm'):
        chunks=[]
        for name,text in sorted(new.items()):
            if not name.startswith(prefix+'/') or old.get(name)==text:continue
            chunks += difflib.unified_diff(old.get(name,'').splitlines(True),text.splitlines(True),
                                           fromfile='a/'+name if name in old else '/dev/null',tofile='b/'+name)
        result[prefix+'.patch']=''.join(chunks)
    return result,identity,gaps


def export(data,out,source_root=None):
    out=Path(out);directory=out/'backends';directory.mkdir()
    factory='rvw_custom_'+hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()[:12]
    (directory/'spike.cc').write_text(spike(data,factory))
    (directory/'platform.fragment.json').write_text(json.dumps(dict(reference_extensions=[dict(name=factory,library='libcustom.so')]),indent=2)+'\n')
    build='''#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
spike_root="${SPIKE_PREFIX:-/opt/homebrew}"
case "$(uname -s)" in Darwin) shared=(-dynamiclib);; *) shared=(-shared -fPIC);; esac
"${CXX:-c++}" -std=c++17 -O2 "${shared[@]}" -I"$spike_root/include" "$here/spike.cc" -L"$spike_root/lib" -lriscv -ldisasm -Wl,-rpath,"$spike_root/lib" -o "$here/libcustom.so"
'''
    (directory/'build-spike.sh').write_text(build);(directory/'build-spike.sh').chmod(0o755)
    files=fragments(data)
    for name,text in files.items():
        target=directory/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text)
    diffs,identity,gaps=patches(data,files,source_root)
    for name,text in diffs.items():(directory/name).write_text(text)
    if identity:(directory/'compiler-bases.json').write_text(json.dumps(identity,indent=2)+'\n')
    result=dict(schema='rvw.custom-backends/1',status='generated',extension_name=factory,xlen=data['xlen'],
                files={str(path.relative_to(directory)):hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(directory.rglob('*')) if path.is_file()},
                compiler_bases=identity,gaps=gaps,
                upstream_toolchain_licenses={'gcc':'GPL-3.0-or-later','llvm':'Apache-2.0 WITH LLVM-exception','installed_spike':'not verified'},
                generated_artifact_license='not specified',
                limits=['Pure RV32I/RV64I R-type instructions. RV32E/RV64E handlers are refused.',
                        'Compiler patches target a project toolchain with this extension enabled; no runtime feature discovery.',
                        'Compiler patch application is not a compiler build or calling-convention qualification.',
                        'Build Spike with the same prefix as the co-simulation shim. No DUT execution is implied.'])
    (directory/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
