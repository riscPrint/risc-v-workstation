"""Bounded IFT instrumentation and native seeded RTL checks."""
import json
import os
from pathlib import Path
import shutil
import sys
import pytest
from rvw.formal.security.ift import instrument
from rvw.common.proc import run_group

ROOT = Path(__file__).resolve().parents[2]


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


@pytest.mark.parametrize('backend', ['json', 'yosys'])
def test_native_ift_mask_control_and_sequential_reset(tmp_path,native_env,ift_plugin,backend):
    source=tmp_path/'source.v'
    source.write_text('''module dut(input clk,reset,secret,mask,select,output reg q,output y);
    assign y=secret & mask;
    always @(posedge clk) if(reset) q<=0; else q<=select ? secret : 0;
    endmodule''')
    net=tmp_path/'net.json'
    native(['yosys','-Q','-T','-p', f'read_verilog {source}; hierarchy -top dut; proc; flatten; techmap; simplemap; write_json {net}'],env=native_env)
    design=json.loads(net.read_text())
    output=tmp_path/'ift.v'
    if backend=='json': output.write_text(instrument(design,'dut'))
    else:
        native(['yosys','-Q','-T','-m',ift_plugin,'-p',f'read_json {net}; rvw_ift; rename dut dut__ift; write_verilog -noattr {output}'],env=native_env)
    tb=tmp_path/'tb.v'
    tb.write_text('''module tb;
    reg clk=0,reset=1,secret=1,mask=0,select=0,st=0;
    wire q,qt,y,yt;
    dut__ift d(.clk(clk),.reset(reset),.reset__t(1'b0),.secret(secret),.secret__t(1'b1),.mask(mask),.mask__t(1'b0),.select(select),.select__t(st),.q(q),.q__t(qt),.y(y),.y__t(yt));
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


@pytest.mark.parametrize('backend', ['json', 'yosys'])
@pytest.mark.parametrize('kind', ['NOT', 'AND', 'OR', 'XOR', 'MUX'])
def test_native_ift_exhaustive_gate_truth_tables(kind,tmp_path,native_env,ift_plugin,backend):
    from itertools import product
    names=['a'] if kind=='NOT' else ['a','b','s'] if kind=='MUX' else ['a','b']
    ports={p:{'direction':'input','bits':[i+2]} for i,p in enumerate(names)}
    ports['y']={'direction':'output','bits':[8]}
    con={p.upper():ports[p]['bits'] for p in names};con['Y']=[8]
    mod={'ports':ports,'cells':{'g':{'type':f'$_{kind}_','connections':con}},
         'netnames':{p:{'bits':d['bits']} for p,d in ports.items()}}
    rtl=tmp_path/'ift.v'
    if backend=='json': rtl.write_text(instrument({'modules':{'gate':mod}},'gate'))
    else:
        design={'creator':'rvw test', 'modules':{'gate':mod}}
        # Yosys read_json requires netname defaults and cell metadata.
        for d in mod['netnames'].values(): d.update(hide_name=0,attributes={})
        mod['attributes']={'top':'1'}
        mod['cells']['g'].update(hide_name=0,parameters={},attributes={},port_directions={p:'output' if p=='Y' else 'input' for p in con})
        net=tmp_path/'gate.json';net.write_text(json.dumps(design))
        native(['yosys','-Q','-T','-m',ift_plugin,'-p',f'read_json {net}; rvw_ift; rename gate gate__ift; write_verilog -noattr {rtl}'],env=native_env)
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
    args=','.join(f'.{p}({p}),.{p}__t({p}t)' for p in names)+',.y(y),.y__t(yt)'
    tb.write_text('module tb; reg '+','.join(x for p in names for x in (p,p+'t'))+'; wire y,yt;\n'
        +f'gate__ift d({args}); initial begin\n'+'\n'.join(checks)+'\n$finish; end endmodule')
    native(['iverilog','-s','tb','-o',tmp_path/'sim',rtl,tb],env=native_env)
    native(['vvp',tmp_path/'sim'],env=native_env)


@pytest.fixture(scope='session')
def ift_plugin(tmp_path_factory):
    compiler=shutil.which('clang++')
    include=Path(os.environ.get('YOSYS_INCLUDE',Path.home()/'opt/oss-cad-suite/share/yosys/include'))
    if not compiler or not (include/'kernel/yosys.h').exists():
        pytest.skip('Yosys plugin headers or clang++ missing')
    out=tmp_path_factory.mktemp('ift-plugin')/'rvw_ift.so'
    flags=['-undefined','dynamic_lookup'] if sys.platform=='darwin' else []
    native([compiler,'-std=c++17','-O1','-fPIC','-D_YOSYS_','-DYOSYS_ENABLE_PLUGINS',
            '-I',include,*flags,'-shared',ROOT/'SpinalChecks/security/rvw_ift.cc','-o',out])
    return out


@pytest.mark.parametrize('source', [
    'module dut(input clk,reset,d,output reg q); always @(posedge clk or posedge reset) if(reset) q<=0; else q<=d; endmodule',
    'module dut(input a,b,d,output reg q,r); always @(posedge a) q<=d; always @(posedge b) r<=d; endmodule',
    'module dut(input clk,d,output reg q); initial q=0; always @(posedge clk) q<=d; endmodule',
    'module dut(output y); wire x; assign y=x; endmodule',
    'module dut(inout x, output y); assign y=x; endmodule',
])
def test_native_ift_refuses_unmodeled_state_and_channels(source,tmp_path,native_env,ift_plugin):
    rtl=tmp_path/'source.v';rtl.write_text(source)
    net=tmp_path/'design.json'
    native(['yosys','-Q','-T','-p',f'read_verilog {rtl}; hierarchy -top dut; proc; flatten; techmap; simplemap; write_json {net}'],env=native_env)
    with pytest.raises(ValueError): instrument(json.loads(net.read_text()),'dut')
    result=run_group(['yosys','-Q','-T','-m',str(ift_plugin),'-p',f'read_json {net}; rvw_ift'],env=native_env,capture=True,timeout=30)
    assert result.returncode!=0 and not result.timed_out


@pytest.mark.parametrize('port', ['n3', 't3'])
def test_json_ift_keeps_ports_distinct_from_internal_bits(tmp_path, native_env, port):
    source = tmp_path / 'source.v'
    source.write_text(f'module dut(input {port}, output y); assign y = ~{port}; endmodule')
    net = tmp_path / 'net.json'
    native(['yosys', '-Q', '-T', '-p',
            f'read_verilog {source}; hierarchy -top dut; proc; flatten; techmap; simplemap; write_json {net}'],
           env=native_env)
    output = tmp_path / 'ift.v'
    output.write_text(instrument(json.loads(net.read_text()), 'dut'))
    tb = tmp_path / 'tb.v'
    tb.write_text(f'''module tb;
reg value=0, taint=0; wire y, yt;
dut__ift d(.{port}(value), .{port}__t(taint), .y(y), .y__t(yt));
initial begin
 #1; if (y !== 1 || yt !== 0) $fatal(1, "public value changed");
 value=1; taint=1;
 #1; if (y !== 0 || yt !== 1) $fatal(1, "secret value or taint changed");
 $finish;
end
endmodule
''')
    executable = tmp_path / 'sim'
    native(['iverilog', '-g2012', '-s', 'tb', '-o', executable, output, tb], env=native_env)
    native(['vvp', executable], env=native_env)


def test_native_ift_unknown_constant_is_tainted(tmp_path, native_env, ift_plugin):
    rtl = tmp_path / 'source.v'
    rtl.write_text("module dut(input d,output y); assign y=d & 1'bx; endmodule")
    net = tmp_path / 'design.json'
    native(['yosys', '-Q', '-T', '-p',
            f'read_verilog {rtl}; hierarchy -top dut; proc; flatten; techmap; simplemap; write_json {net}'],
           env=native_env)
    output = tmp_path / 'ift.v'
    output.write_text(instrument(json.loads(net.read_text()), 'dut'))
    # The native plugin still refuses X/Z. The JSON backend models their taint.
    result = run_group(['yosys', '-Q', '-T', '-m', str(ift_plugin), '-p',
                        f'read_json {net}; rvw_ift'],
                       env=native_env, capture=True, timeout=30)
    assert result.returncode != 0 and not result.timed_out
    assert 'X/Z cell input is unmodeled' in result.stderr
    tb = tmp_path / 'tb.v'
    tb.write_text('''module tb;
reg d=0; wire y, yt;
dut__ift unit0(.d(d), .d__t(1'b0), .y(y), .y__t(yt));
initial begin
 #1; if (y !== 0 || yt !== 0) $fatal(1, "public zero must mask unknown");
 d=1;
 #1; if (yt !== 1) $fatal(1, "unknown must taint output");
 $finish;
end
endmodule
''')
    executable = tmp_path / 'sim'
    native(['iverilog', '-g2012', '-s', 'tb', '-o', executable, output, tb], env=native_env)
    native(['vvp', executable], env=native_env)
