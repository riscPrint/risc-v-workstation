"""Generate RV32 M arithmetic slices from pinned Sail expressions."""
import re
import json
from pathlib import Path
from rvw.formal.sail_zicond import generate as compile_rules
from rvw.formal.sail_subset import sha

HASHES={'model/extensions/M/mext_insts.sail': 'f439cf260459ac1dd6031bf208c7444400b31bfa73dba5cec867d0edffa152f6', 'model/core/arithmetic.sail': 'e96d68eadd62816e02e5bed6ff428aa2098df37294675f066284370eb21dfcde', 'model/prelude/prelude.sail': 'c5a3825e88088bdad0a14abf9f8645894621148fe2cc23ebdd1e6d3ea549da8f'}
PATHS=('model/extensions/M/mext_insts.sail','model/core/arithmetic.sail','model/prelude/prelude.sail')


def extract(model):
    model=Path(model)
    expected=HASHES
    for path,digest in expected.items():
        if sha(model/path)!=digest: raise ValueError('Sail M source hash mismatch: '+path)
    source=(model/PATHS[0]).read_text()
    prelude=(model/PATHS[2]).read_text()
    helpers=(model/PATHS[1]).read_text()
    convert=prelude[prelude.index('val to_bits_truncate :'):prelude.index('// This version should never be used.')]
    enums='enum Signedness = { Signed, Unsigned }\nenum VectorHalf = { High, Low }\n'
    multiply=helpers[helpers.index('val mult_to_bits_half :'):helpers.index('$[property]')]
    arithmetic='\n'.join(line for line in prelude.splitlines() if line.startswith(('val quot_round_zero =','val rem_round_zero =')))+'\n'
    common='default Order dec\n$include <prelude.sail>\n'+convert+enums+multiply+arithmetic
    rules={}
    for i,(name,sign1,sign2,part) in enumerate((('mul','Signed','Signed','Low'),('mulh','Signed','Signed','High'),('mulhsu','Signed','Unsigned','High'),('mulhu','Unsigned','Unsigned','High'))):
        # The tuple is checked against the pinned instruction's mnemonic map.
        pattern=rf'struct {{ result_part = {part},\s+signed_rs1 = {sign1},\s+signed_rs2 = {sign2}\s+}} <-> "{name}"'
        if not re.search(pattern,source): raise ValueError('missing multiply mnemonic '+name)
        rules[name]=dict(expression=f'mult_to_bits_half(32, {sign1}, {sign2}, a, b, {part})',match=0x02000033|(i<<12),prelude=common)
    for family,base in [('DIV',4),('REM',6)]:
        body=re.search(r'function clause execute '+family+r'\([^\n]+\) = \{(.*?)\n\}',source,re.S)[1]
        body=body.replace('not(', 'not_bool(')
        body=body.replace('X(rs1)','a').replace('X(rs2)','b').replace('xlen','32')
        body=re.sub(r'X\(rd\) = ([^;]+);\s*RETIRE_SUCCESS',r'\1',body)
        for unsigned in (False,True):
            name=family.lower()+('u' if unsigned else '')
            rules[name]=dict(expression='{'+body.replace('is_unsigned','true' if unsigned else 'false')+'\n}',match=0x02000033|((base+unsigned)<<12),prelude=common)
    for rule in rules.values():
        rule.update(sail_sources=expected,scope='RV32 M arithmetic expression; independent instruction shell',excluded=['full machine','extension-disabled traps','CSR MISA','RV64'])
    return rules


def generate(model, compiler, out):
    result = compile_rules(model,compiler,out,rules=extract(model),metadata=dict(schema='rvw.sail-m/1',rule_sources=HASHES,rule=dict(path=PATHS[0],sha256=HASHES[PATHS[0]]),lowerings=['pinned helper extraction','XLEN specialization to 32','not to not_bool'],implementation_options=dict(xlen=32,extension='M',alternative_operations=False,memory=False,privilege=False)))

    for name, entry in result['files'].items():
        path=Path(out)/('insn_'+name+'.v')
        raw=path.read_text()
        entry['before_backend_lowering_sha256']=sha(path)
        path.write_text(lower(raw,name))
        entry['model_sha256']=sha(path)
        entry['backend_lowerings'] += ['packed aggregate to concatenation', 'signedness casts to system functions',
                                       'temporary concatenation slice to sized cast', 'signed 128-bit divide/remainder primitive binding']
    result['primitive_boundary']='Sail quot_round_zero and rem_round_zero use signed SystemVerilog / and % bindings.'
    (Path(out)/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def lower(text, name):
    text=text.replace("unsigned'(", '$unsigned(').replace("signed'(", '$signed(').replace("'{", '{')
    text=re.sub(r'= \{([^;]+)\}\[([0-9]+):0\];',lambda m:'= '+str(int(m[2])+1)+"'("+m[1]+');',text)
    for primitive,op in [('quot_round_zero','/'),('rem_round_zero','%')]:
        if primitive in text:
            text=re.sub(r'\b'+primitive+r'\b','sail_'+name+'_'+primitive,text)
            text+='\nmodule sail_'+name+'_'+primitive+'(input [127:0] a,b, output [127:0] y);\nassign y = $signed(a) '+op+' $signed(b);\nendmodule\n'
    return text
