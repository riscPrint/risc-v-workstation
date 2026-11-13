#!/usr/bin/env python3
"""Check the actual DivRadix4 active-step invariant at a selected word width.

The default checks local transitions. --complete composes the unsigned 32-bit
transaction certificate. Register Q inputs are explicit lemma variables. Every
next-state D expression comes from the supplied RTL.
"""
import argparse
import hashlib
import json
from pathlib import Path
from rvw.common.proc import run_group

NAMES = ('counter','busy','done','shifter','numerator','result','div1','div3')


def cut_state(design, width):
    mod = design['modules']['DivRadix4']
    expected = dict(counter=max(1,(width//2-1).bit_length()),busy=1,done=1,
                    shifter=width,numerator=width,result=width,div1=width+2,div3=width+2)
    selected = {}
    for name in NAMES:
        bits = mod['netnames'][name]['bits']
        if len(bits) != expected[name]: raise ValueError('state width changed: '+name)
        matches = [(n,c) for n,c in mod['cells'].items() if c['type']=='$dff' and c['connections']['Q']==bits]
        if len(matches)!=1: raise ValueError('one plain synchronous state cell required: '+name)
        cellname, cell = matches[0]
        if cell['connections'].get('CLK') != mod['ports'].get('clk',{}).get('bits') or int(cell['parameters'].get('CLK_POLARITY','0'),2)!=1:
            raise ValueError('all state must use the public rising-edge clk')
        mod['ports']['state_'+name] = dict(direction='input',bits=bits)
        mod['ports']['next_'+name] = dict(direction='output',bits=cell['connections']['D'])
        selected[name] = cellname
    if len(set(selected.values()))!=len(NAMES): raise ValueError('state aliases are unsupported')
    if {n for n,c in mod['cells'].items() if c['type'].startswith(('$dff','$sdff','$adff'))} != set(selected.values()):
        raise ValueError('unaccounted state remains')
    for name in selected.values(): del mod['cells'][name]
    for net in mod['netnames'].values(): net.get('attributes',{}).pop('init',None)
    return expected


def response_binding(module, width):
    inputs={'clk':1,'reset':1,'io_flush':1,'io_cmd_valid':1,'io_rsp_ready':1,
            'io_cmd_payload_a':width,'io_cmd_payload_b':width}
    if any(module['ports'].get(n,{}).get('direction')!='input' or len(module['ports'][n]['bits'])!=w for n,w in inputs.items()):
        raise ValueError('complete certificate needs the original full-width input interface')
    pairs = {'io_rsp_valid':module['netnames']['done']['bits'],
             'io_rsp_payload_result':module['netnames']['result']['bits']+['0']*3,
             'io_rsp_payload_remain':module['netnames']['shifter']['bits']+['0']}
    if any(module['ports'][port].get('direction')!='output' or module['ports'][port]['bits']!=bits for port,bits in pairs.items()):
        raise ValueError('response no longer exposes the proved quotient, remainder and done state')
    return {name:len(bits) for name,bits in pairs.items()}


def prefix_lemmas(width):
    lines=['(set-logic QF_BV)',f'(declare-const a (_ BitVec {width}))']
    val=lambda n:f'(_ bv{n} {width})'
    for count in range(width//2):
        processed=2*count
        prefix=f'(bvlshr a {val(width-processed)})'
        numerator=f'(bvshl a {val(processed)})'
        incoming=f'(bvlshr {numerator} {val(width-2)})'
        after=f'(bvlshr a {val(width-processed-2)})'
        append=f'(bvadd (bvshl {prefix} {val(2)}) {incoming})'
        claims=[f'(= {after} {append})',
                f'(= (bvshl {numerator} {val(2)}) (bvshl a {val(processed+2)}))',
                f'(=> (= a (bvlshr {numerator} {val(processed)})) (= {prefix} {val(0)}))']
        for claim in claims:
            lines+=['(push)',f'(assert (not {claim}))','(check-sat)','(pop)']
    return '\n'.join(lines)+'\n'


def wrapper(mod, widths, width):
    declarations=[];connections=[]
    for name, port in mod['ports'].items():
        n=len(port['bits']);declarations.append(f"{'input' if port['direction']=='input' else 'output'} [{n-1}:0] {name}")
        connections.append(f'.{name}({name})')
    body=['module step_lemma('+','.join(declarations)+');','DivRadix4 dut('+','.join(connections)+');']
    # All extension widths are explicit. The candidate remainder is W bits,
    # while the trial dividend and three-times divisor need W+2 bits.
    w=width
    body += [f'wire [{w+1}:0] trial = {{state_shifter,state_numerator[{w-1}:{w-2}]}};',
             f'wire [{w+1}:0] digit_product = next_result[1:0]==0 ? 0 : next_result[1:0]==1 ? state_div1 : next_result[1:0]==2 ? (state_div1 << 1) : state_div3;',
             'always @* begin',
             f'if (!reset && !io_flush && state_busy && !state_done && state_div1!=0 && state_div1 < {w+3}\'d{1<<w} && state_shifter < state_div1 && state_div3 == (state_div1 + (state_div1 << 1))) begin',
             'assert ({2\'b0,next_shifter} + digit_product == trial);',
             'assert (next_shifter < state_div1);',
             'assert (next_numerator == (state_numerator << 2));',
             f'assert (next_result[{w-1}:2] == state_result[{w-3}:0]);',
             'assert (next_div1 == state_div1);', 'assert (next_div3 == state_div3);',
             'end end endmodule\n']
    # Base, reset and progress obligations use the same extracted next-state logic.
    body[-1] = 'end'
    body += ['assert(io_cmd_ready==!state_busy);']
    body += ['if (reset) begin assert(!next_busy); assert(!next_done); end',
             'if (!reset && !io_flush && !state_busy && !state_done) begin',
             'assert(next_busy==io_cmd_valid);', 'assert(next_shifter==0);',
             'assert(next_div1==io_cmd_payload_b);',
             'assert(next_div3==({2\'b0,io_cmd_payload_b}+({2\'b0,io_cmd_payload_b}<<1)));',
             f"assert(next_result==(io_cmd_payload_b==0 ? {w}'h{(1<<w)-1:x} : {w}'d0));"]
    for count in range(width//2):
        body.append(f'if(next_counter=={count}) begin assert(io_cmd_payload_a==(next_numerator >> {2*count})); assert(next_numerator==(io_cmd_payload_a << {2*count})); end')
    body += ['end', 'if (!reset && !io_flush && state_busy && !state_done) begin',
             'assert(next_busy);', 'assert(next_numerator==(state_numerator<<2));',
             f'assert(next_result[{w-1}:2]==state_result[{w-3}:0]);',
             'assert(next_div1==state_div1); assert(next_div3==state_div3);',
             'assert(next_counter == ((state_counter+1) & '+str(width//2-1)+'));',
             'assert(next_done == (state_counter=='+str(width//2-1)+'));',
             'if(state_div1==0 && state_div3==0) begin',
             'assert(next_result[1:0]==3);',
             f"if(state_result=={w}'h{(1<<w)-1:x}) assert(next_result=={w}'h{(1<<w)-1:x});", f'assert(next_shifter==trial[{w-1}:0]);',
             'end end end endmodule\n']
    return '\n'.join(body)


def main():
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--rtl',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--width',type=int,choices=[8,16,32],default=32)
    p.add_argument('--complete',action='store_true',help='compose the 32-bit unsigned transaction certificate')
    p.add_argument('--timeout',type=float,default=60)
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    root=Path(__file__).resolve().parents[3]
    def execute(script,name):
        (out/(name+'.ys')).write_text(script)
        r=run_group([str(root/'scripts/with-lock.sh'),'vex-equiv','nice','-n','10','yosys','-Q','-s',name+'.ys'],
                    cwd=out,timeout=min(a.timeout,120),capture=True)
        (out/(name+'.log')).write_text((r.stdout or '')+(r.stderr or ''))
        return r
    raw=a.rtl.read_bytes();(out/'dut.v').write_bytes(raw)
    result=dict(schema='rvw.nax-div-step/1',width=a.width,rtl_sha256=hashlib.sha256(raw).hexdigest(),
                status='inconclusive',scope='local active transition lemma only; not a complete arithmetic proof',
                preconditions=['busy and not done','no reset or flush','nonzero W-bit divisor','remainder below divisor','stored triple equals three times divisor'])
    r=execute('read_verilog dut.v\nhierarchy -check -top DivRadix4\nproc\nwrite_json raw.json\n','map')
    if not r.returncode:
        design=json.loads((out/'raw.json').read_text())
        if a.complete:
            if a.width!=32: raise ValueError('complete certificate currently requires width 32')
            result['response_binding']=response_binding(design['modules']['DivRadix4'],a.width)
        widths=cut_state(design,a.width)
        (out/'step.json').write_text(json.dumps(design))
        (out/'lemma.sv').write_text(wrapper(design['modules']['DivRadix4'],widths,a.width))
        r=execute('read_json step.json\nread_verilog -formal -sv lemma.sv\nprep -top step_lemma -flatten\ncheck -assert\nchformal -lower\nsat -verify -prove-asserts -set-def-inputs -show-inputs -show-outputs\n','prove')
        if not r.returncode: result['status']='step_proved'
        elif 'SAT proof finished - model found: FAIL!' in (r.stdout or ''): result['status']='counterexample'
        elif r.timed_out: result['reason']='native step proof timed out'
        else: result['reason']='step assertion or mapping failed; inspect prove.log'
    if a.complete and result['status']=='step_proved':
        # The machine-checkable bridges connect the extracted bit transitions
        # to the integer induction theorem. No complete C divide is assumed.
        math=(root/'SpinalChecks/c2rtl/division-invariant.smt2').read_text()
        (out/'division-math.smt2').write_text(math)
        (out/'prefix.smt2').write_text(prefix_lemmas(a.width))
        result['step_status']='step_proved'
        result['status']='inconclusive'
        result['certificate']={'kind':'unsigned one-request DIVU and REMU',
            'contract':['one public synchronous reset clock','one request with stable operands',
                        'no reset or flush before first completion','first response only'],
            'proof_chain':['reset to idle','request base and skipped-zero prefix','active radix-4 step',
                           'prefix recurrence and width bounds','counter progress to completion',
                           'response-state binding','Euclidean uniqueness or zero-divisor convention'],
            'obligations':{}}
        for filename,expected in [('division-math.smt2',6),('prefix.smt2',48)]:
            r=run_group([str(root/'scripts/with-lock.sh'),'vex-equiv','nice','-n','10','z3','-smt2',filename],
                        cwd=out,timeout=min(a.timeout,120),capture=True)
            (out/(filename+'.log')).write_text((r.stdout or '')+(r.stderr or ''))
            result['certificate']['obligations'][filename]={
                'closed':r.returncode==0 and (r.stdout or '').split()==['unsat']*expected,
                'expected_unsat':expected,'sha256':hashlib.sha256((out/filename).read_bytes()).hexdigest()}
        if all(o['closed'] for o in result['certificate']['obligations'].values()):
            result['status']='transaction_proved'
            result['scope']='unrestricted unsigned 32-bit quotient and remainder at first response; compositional induction on actual RTL transitions'
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
    return 0 if result['status']=='transaction_proved' or (not a.complete and result['status']=='step_proved') else 3


if __name__=='__main__': raise SystemExit(main())
