#!/usr/bin/env python3
"""Check the real split multiplier's unrestricted RTL-operator composition.

Bind all four $mul cells to exact operand slices. Prove product ranges and
expansion with Z3 integers. Prove the actual adder network for symbolic
partial products with Yosys SAT. This trusts RTL $mul semantics, as other RTL
word-level proofs do. It does not qualify technology-mapped multiplier gates.
"""
import argparse
import hashlib
import json
from pathlib import Path
from rvw.common.proc import run_group


def products(module):
    a,b=(module['ports'][n]['bits'] for n in ('a','b'))
    if len(a)!=33 or len(b)!=33 or len(module['ports']['y']['bits'])!=64:
        raise ValueError('expected 33-bit signed operands and a 64-bit result')
    expected={
        'll':(a[:17],b[:17],False,34),
        'lh':(a[:17]+['0']*17,b[17:]+[b[-1]]*18,True,34),
        'hl':(a[17:]+[a[-1]]*18,b[:17]+['0']*17,True,34),
        'hh':(a[17:]+[a[-1]]*16,b[17:]+[b[-1]]*16,True,32)}
    found={}
    for name,cell in module['cells'].items():
        if cell['type']!='$mul':continue
        con=cell['connections'];p={k:int(v,2) for k,v in cell['parameters'].items()}
        matches=[role for role,(aa,bb,signed,w) in expected.items()
                 if con['A']==aa and con['B']==bb and p['A_SIGNED']==int(signed)
                 and p['B_SIGNED']==int(signed) and len(con['Y'])==w]
        if len(matches)!=1 or matches[0] in found:raise ValueError('unexpected or duplicate partial-product binding')
        found[matches[0]]=(name,con['Y'])
    if set(found)!=set(expected):raise ValueError('four exact partial products required')
    return found


LEMMA = '''(set-logic QF_NIA)
(declare-const a0 Int)(declare-const b0 Int)(declare-const a1 Int)(declare-const b1 Int)
; Unsigned 17 by unsigned 17 has exactly 34 result bits.
(push)(assert (and (<= 0 a0) (< a0 131072) (<= 0 b0) (< b0 131072)))
(assert (not (and (<= 0 (* a0 b0)) (< (* a0 b0) 17179869184))))
(check-sat)(pop)
; Unsigned 17 by signed 16 fits signed 33 bits. The 34-bit RTL
; product therefore has a duplicated sign bit. The transposed case is identical.
(push)(assert (and (<= 0 a0) (< a0 131072) (<= (- 32768) b1) (< b1 32768)))
(assert (not (and (<= (- 4294967296) (* a0 b1)) (< (* a0 b1) 4294967296))))
(check-sat)(pop)
; Signed 16 by signed 16 fits signed 32 bits.
(push)(assert (and (<= (- 32768) a1) (< a1 32768) (<= (- 32768) b1) (< b1 32768)))
(assert (not (and (<= (- 2147483648) (* a1 b1)) (< (* a1 b1) 2147483648))))
(check-sat)(pop)
; Polynomial identity for the signed 33-bit operand decomposition.
(assert (not (= (* (+ a0 (* 131072 a1)) (+ b0 (* 131072 b1)))
 (+ (* a0 b0) (* 131072 a0 b1) (* 131072 a1 b0) (* 17179869184 a1 b1)))))
(check-sat-using (then (using-params simplify :som true) smt))
'''


def main():
    p=argparse.ArgumentParser(__doc__);p.add_argument('--rtl',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--timeout',type=float,default=60)
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    root=Path(__file__).resolve().parents[3]
    raw=a.rtl.read_bytes();(out/'dut.v').write_bytes(raw)
    result=dict(schema='rvw.vexii-mul-composition/1',status='inconclusive',rtl_sha256=hashlib.sha256(raw).hexdigest(),
                scope='unrestricted signed 33x33 product modulo 2^64; actual helper adder network; RTL operator semantics',
                trusted_primitive='Yosys signed/unsigned $mul word semantics; not a technology-mapped gate proof')
    def execute(command,log):
        r=run_group([str(root/'scripts/with-lock.sh'),'vex-equiv','nice','-n','10',*command],cwd=out,timeout=min(a.timeout,120),capture=True)
        (out/log).write_text((r.stdout or '')+(r.stderr or ''));return r
    def yosys(script,name):
        (out/(name+'.ys')).write_text(script)
        return execute(['yosys','-Q','-s',name+'.ys'],name+'.log')
    r=yosys('read_verilog dut.v\nhierarchy -check -top VexiiMul\nproc\nflatten\nopt_clean\nwrite_json raw.json\n','map')
    if r.returncode: return 3
    design=json.loads((out/'raw.json').read_text());mod=design['modules']['VexiiMul'];found=products(mod)
    result['partial_products']={k:dict(width=len(bits),binding='exact source operand slices and signedness') for k,(_,bits) in found.items()}
    (out/'lemmas.smt2').write_text(LEMMA)
    r=execute(['z3','-smt2','lemmas.smt2'],'lemmas.log')
    result['closed_lemmas']=r.returncode==0 and (r.stdout or '').split()==['unsat']*4
    if result['closed_lemmas']:
        for role,(name,bits) in found.items():
            del mod['cells'][name];mod['ports']['pp_'+role]=dict(direction='input',bits=bits)
        (out/'composition.json').write_text(json.dumps(design))
        (out/'composition.sv').write_text('''module composition(input [32:0] a,b,input [33:0] pp_ll,pp_lh,pp_hl,input [31:0] pp_hh);
wire [63:0] y;
VexiiMul dut(.*);
wire [63:0] lh={{30{pp_lh[33]}},pp_lh};
wire [63:0] hl={{30{pp_hl[33]}},pp_hl};
wire [63:0] hh={{32{pp_hh[31]}},pp_hh};
always @* begin
assume(pp_lh[33]==pp_lh[32]); assume(pp_hl[33]==pp_hl[32]);
assert(y == ({30'd0,pp_ll} + (lh<<17) + (hl<<17) + (hh<<34)));
end endmodule
''')
        r=yosys('read_json composition.json\nread_verilog -formal -sv composition.sv\nprep -top composition -flatten\ncheck -assert\nchformal -lower\nsat -verify -prove-asserts -set-assumes -set-def-inputs\n','composition')
        if r.returncode==0:result['status']='composition_proved'
        elif 'SAT proof finished - model found: FAIL!' in (r.stdout or ''): result['status']='counterexample'
        else:result['reason']='composition did not close; inspect composition.log'
    else:result['reason']='range or expansion lemma did not close'
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
    return 0 if result['status']=='composition_proved' else 3


if __name__=='__main__':raise SystemExit(main())
