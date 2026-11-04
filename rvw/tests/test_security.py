"""Bounded security checks and native seeded RTL experiments."""
import copy
import json
import os
from pathlib import Path
import shutil
import sys
import pytest
from rvw.formal.security.contracts import assess, detection_rate
from rvw.formal.security.ift import instrument
from rvw.common.proc import run_group

ROOT = Path(__file__).resolve().parents[2]


def row(value=0, cycles=None):
    effects = [dict(pc=0, insn=0x2081b3, rd=3, rd_wdata=value)]
    return {'public_key': [7], 'reference': {'contract': [[0,None]], 'effects': effects},
            'rtl': {'complete': True, 'effects': copy.deepcopy(effects),
                    'cycles': cycles or [1], 'observations': {'cache': 0}}}


def test_contracts_ignore_secret_data_and_find_timing():
    a,b = row(3),row(4,[2])
    result = assess([a,b], ['cache'])
    assert result['verdict']=='violation'
    assert result['violations'][0]['kind']=='zkt-add'
    assert assess([a,row(4)], ['cache'])['verdict']=='no_violation'


def test_distinct_contracts_and_public_contexts_are_not_compared():
    a,b = row(),row()
    b['reference']['contract']=[[4,None]]
    assert assess([a,b], ['cache'])['verdict']=='inconclusive'
    b=row(); b['public_key']=[8]
    assert assess([a,b], ['cache'])['compared_pairs']==0


@pytest.mark.parametrize('fault', ['complete','effects','cycles','observations'])
def test_incomplete_evidence_is_inconclusive(fault):
    a,b=row(),row()
    b['rtl'][fault] = {'complete':False,'effects':[],'cycles':[], 'observations':{}}[fault]
    assert assess([a,b], ['cache'])['verdict']=='inconclusive'


def test_detection_denominators_include_inconclusive_and_missed():
    report=detection_rate([{'seeded':True,'verdict':v} for v in ['violation','inconclusive','no_violation']])
    assert report['detection_rate']==1/3
    assert report['seeded_total']==3 and report['missed']==1 and report['inconclusive']==1


def native(argv, **kwargs):
    r=run_group(list(map(str,argv)),capture=True,timeout=60,**kwargs)
    assert not r.timed_out and r.returncode==0, (r.stdout,r.stderr)
    return r.stdout


@pytest.fixture
def native_env():
    env=dict(os.environ)
    env['PATH']=str(Path.home()/'opt/oss-cad-suite/bin')+os.pathsep+env['PATH']
    env['PYTHONPATH']=str(ROOT/'rvw/src')
    for name in ('yosys','iverilog','vvp'):
        if not shutil.which(name,path=env['PATH']): pytest.skip(f'{name} not installed')
    return env


def test_native_ift_mask_control_and_sequential_reset(tmp_path,native_env):
    source=tmp_path/'source.v'
    source.write_text('''module dut(input clk,reset,secret,mask,select,output reg q,output y);
    assign y=secret & mask;
    always @(posedge clk) if(reset) q<=0; else q<=select ? secret : 0;
    endmodule''')
    net=tmp_path/'net.json'
    native(['yosys','-Q','-T','-p', f'read_verilog {source}; hierarchy -top dut; proc; flatten; techmap; simplemap; write_json {net}'],env=native_env)
    design=json.loads(net.read_text())
    output=tmp_path/'ift.v'; output.write_text(instrument(design,'dut'))
    tb=tmp_path/'tb.v'
    tb.write_text('''module tb;
    reg clk=0,reset=1,secret=1,mask=0,select=0,st=0;
    wire q,qt,y,yt;
    dut__ift d(clk,reset,1'b0,secret,1'b1,mask,1'b0,select,st,q,qt,y,yt);
    always #5 clk=~clk;
    initial begin
      #6; if(qt!==0 || yt!==0) $fatal;
      reset=0; mask=1; #1; if(yt!==1) $fatal;
      #9; if(qt!==0) $fatal;
      st=1; #10; if(qt!==1) $fatal;
      reset=1; #10; if(qt!==0) $fatal;
      $display("IFT_OK"); $finish;
    end endmodule''')
    native(['iverilog','-g2012','-s','tb','-o',tmp_path/'sim',output,tb],env=native_env)
    assert 'IFT_OK' in native(['vvp',tmp_path/'sim'],env=native_env)
    design['modules']['dut']['cells']['bad']={'type':'blackbox'}
    with pytest.raises(ValueError,match='unmodeled'): instrument(design,'dut')


def test_native_spike_rtl_seeded_campaign(tmp_path,native_env):
    gcc=shutil.which('riscv64-unknown-elf-gcc') or '/opt/homebrew/opt/riscv-gnu-toolchain/bin/riscv64-unknown-elf-gcc'
    if not Path(gcc).exists(): pytest.skip('RISC-V GCC missing')
    shim=Path(os.environ.get('RVW_SPIKE_SHIM', str(ROOT/'Cosim/build/librvw_spike.so')))
    if not shim.exists(): pytest.skip('Spike shim missing; set RVW_SPIKE_SHIM')
    elf=tmp_path/'program.elf'
    native([gcc,'-march=rv32i','-mabi=ilp32','-nostdlib','-Wl,-Ttext=0x80000000','-Wl,--no-relax',ROOT/'examples/security/program.S','-o',elf],env=native_env)
    platform=tmp_path/'platform.json'
    platform.write_text(json.dumps(dict(name='security-slice',xlen=32,isa='rv32i',reset_pc=0x80000000,ram=[[0x80000000,0x10000]],mmio=[])))
    results=[]
    for seed in range(5):
        manifest=tmp_path/f'manifest-{seed}.json'
        manifest.write_text(json.dumps(dict(elf=str(elf),platform=str(platform),shim=str(shim),
            adapter_tree=str(ROOT/'examples/security'), adapter_command=[sys.executable,'{tree}/adapter.py','{case}','{out}'],
            secret_registers=[1],unmodeled_channels=['analog power','predictor','bus contention'],
            stop_pc=0x8000000c,max_steps=4,observations=['cache','protected_trace','test_output'],
            cases=[dict(public_key=[7,seed],registers={'1':s,'2':7,'4':seed}) for s in (0,1,2,3)])))
        run=run_group([sys.executable,'-m','rvw.cli','formal','security','contract',str(manifest),'--out',str(tmp_path/f'run-{seed}')],env=native_env,capture=True,timeout=120)
        assert (tmp_path/f'run-{seed}/result.json').exists(), (run.stdout, run.stderr)
        report=json.loads((tmp_path/f'run-{seed}/result.json').read_text())
        assert run.returncode==(0 if seed==0 else 1), report
        assert report['compared_pairs']==6, report
        assert report['zkt_add_comparisons']==6
        results.append({'seeded':seed!=0,'verdict':report['verdict']})
    metric=detection_rate(results)
    assert metric==dict(seeded_total=4,detected=4,missed=0,inconclusive=0,detection_rate=1.0,controls=1,false_positives=0)
    print(json.dumps(metric,sort_keys=True))


@pytest.mark.parametrize('kind', ['NOT', 'AND', 'OR', 'XOR', 'MUX'])
def test_native_ift_exhaustive_gate_truth_tables(kind,tmp_path,native_env):
    from itertools import product
    names=['a'] if kind=='NOT' else ['a','b','s'] if kind=='MUX' else ['a','b']
    ports={p:{'direction':'input','bits':[i+2]} for i,p in enumerate(names)}
    ports['y']={'direction':'output','bits':[8]}
    con={p.upper():ports[p]['bits'] for p in names};con['Y']=[8]
    mod={'ports':ports,'cells':{'g':{'type':f'$_{kind}_','connections':con}},
         'netnames':{p:{'bits':d['bits']} for p,d in ports.items()}}
    rtl=tmp_path/'ift.v';rtl.write_text(instrument({'modules':{'gate':mod}},'gate'))
    def gate(values):
        a=values[0];b=values[1] if len(values)>1 else 0
        return {'NOT':1-a,'AND':a&b,'OR':a|b,'XOR':a^b,'MUX':b if len(values)>2 and values[2] else a}[kind]
    checks=[]
    for values in product((0,1),repeat=len(names)):
        for taints in product((0,1),repeat=len(names)):
            possible={gate(xs) for xs in product(*[(0,1) if t else (v,) for v,t in zip(values,taints)])}
            assigns=' '.join(f'{p}={v}; {p}t={t};' for p,v,t in zip(names,values,taints))
            checks.append(assigns+f' #1; if(y!==1\'b{gate(values)} || yt!==1\'b{int(len(possible)>1)}) $fatal;')
    tb=tmp_path/'tb.v'
    args=','.join(x for p in names for x in (p,p+'t'))+',y,yt'
    tb.write_text('module tb; reg '+','.join(x for p in names for x in (p,p+'t'))+'; wire y,yt;\n'
        +f'gate__ift d({args}); initial begin\n'+'\n'.join(checks)+'\n$finish; end endmodule')
    native(['iverilog','-s','tb','-o',tmp_path/'sim',rtl,tb],env=native_env)
    native(['vvp',tmp_path/'sim'],env=native_env)
