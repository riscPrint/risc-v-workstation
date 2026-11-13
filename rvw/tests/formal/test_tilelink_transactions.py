import shutil
import pytest
from rvw.common.proc import run_group
from rvw.formal.tilelink_transactions import render
from rvw.formal.typed_bus_checks import render as channels

pytestmark=pytest.mark.slow


def fields(coherent=False):
    payloads=dict(a=dict(opcode=3,param=3,source=2,address=32,size=3,mask=4,data=32,corrupt=1),
                  d=dict(opcode=3,param=2,source=2,size=3,sink=2,data=32,denied=1,corrupt=1))
    if coherent:
        payloads.update(b=dict(opcode=3,param=3,source=2,address=32,size=3),
                        c=dict(opcode=3,param=3,source=2,address=32,size=3,data=32,corrupt=1),e=dict(sink=2))
    result={}
    for ch,payload in payloads.items():
        for key,width in [('valid',1),('ready',1),*[(f'payload.{k}',v) for k,v in payload.items()]]:
            name=ch+'.'+key;result[name]=(name.replace('.','_'),None,None,width,1,False)
    return result


@pytest.mark.parametrize('case',['good','single_source','zero','reorder','arithmetic','logical','hint','put_burst','read_burst','preoffer',
                                 'error_response','reset','orphan_reset','bad_mask','bad_param','orphan','wrong_size','wrong_opcode','source_reuse',
                                 'a_header','d_header','burst_stall'])
def test_uh_tracker(tmp_path,case):check(tmp_path,False,case)


@pytest.mark.parametrize('case',['grant','single_sink','orphan_e','release','release_data','orphan_release','probe','probe_zero','probe_two_addresses',
                                 'probe_data','probe_bad_address','probe_bad_cap','probe_reuse','probe_duplicate','probe_capacity','probe_perm_data','probe_reset','grant_reset','release_reset'])
def test_coherent_tracker(tmp_path,case):check(tmp_path,True,case)


def check(tmp_path,coherent,case):
    if not shutil.which('sby') or not shutil.which('yices-smt2'):pytest.skip('SBY and Yices required')
    sigs=fields(coherent)
    options=dict(size_max=4)
    if case=='single_source':
        sigs={k:v for k,v in sigs.items() if not k.endswith('payload.source')};options['source_width']=0
    if case=='single_sink':
        sigs={k:v for k,v in sigs.items() if not k.endswith('payload.sink')};options['sink_width']=0
    source,_=channels('tilelink',sigs,'monitor')
    body=render(sigs,depth=2,options=options)
    source=source.replace('\nendmodule\n','\n'+body+'\nendmodule\n')
    probe=case.startswith('probe');release='release' in case;grant=coherent and not probe and not release
    burst_a=case in ('put_burst','a_header');burst_d=case in ('read_burst','d_header','burst_stall') or (grant and case!='grant_reset')
    wires=[]
    for key,row in sigs.items():
        ch=key.split('.')[0];v='0'
        if key.endswith('ready'):v='1'
        if key.endswith('valid'):
            v={'a':'phase==1','d':'phase==2','b':'0','c':'0','e':'0'}[ch]
            if case=='zero' and ch in ('a','d'):v='phase==1'
            if case=='reorder' and ch in ('a','d'):v='(phase==1 || phase==2)' if ch=='a' else '(phase==3 || phase==4)'
            if case=='preoffer' and ch in ('a','d'):v='(phase>=1 && phase<=3)' if ch=='a' else 'phase==4'
            if case=='source_reuse' and ch=='a':v='(phase==1 || phase==2)'
            if burst_a:v={'a':'(phase==1 || phase==2)','d':'phase==3'}.get(ch,v)
            if burst_d and ch=='d':v='(phase==2 || phase==3)' if case!='burst_stall' else '(phase>=2 && phase<=4)'
            if case=='orphan' and ch=='a':v='0'
            if grant and ch=='e':v='phase==4'
            if probe:
                v={'a':'0','d':'0','e':'0','b':'phase==1','c':'phase==2'}[ch]
                if case=='probe_zero' and ch=='c':v='phase==1'
                if case=='probe_two_addresses' and ch in ('b','c'):v='(phase==1 || phase==2)' if ch=='b' else '(phase==3 || phase==4)'
                if case in ('probe_duplicate','probe_reuse') and ch=='b':v='(phase==1 || phase==2)'
                if case=='probe_duplicate' and ch=='c':v='phase==3'
                if case=='probe_reuse' and ch=='c':v='(phase==2 || phase==3)'
                if case=='probe_capacity':v='(phase>=1 && phase<=3)' if ch=='b' else '0'
                if case in ('probe_data','probe_perm_data') and ch=='c':v='(phase==2 || phase==3)'
            if release:v={'a':'0','b':'0','c':'phase==1' if case!='release_data' else '(phase==1 || phase==2)',
                          'd':'phase==2' if case!='release_data' else 'phase==3','e':'0'}[ch]
            if case=='orphan_release' and ch=='c':v='0'
        if key.endswith('valid') and case in ('reset','orphan_reset'):
            v={'a':'phase==1' if case=='orphan_reset' else '(phase==1 || phase==4)',
               'd':'phase==3' if case=='orphan_reset' else 'phase==5'}[ch]
        if key.endswith('valid') and case=='probe_reset':
            v={'a':'0','d':'0','e':'0','b':'(phase==1 || phase==4)','c':'phase==5'}[ch]
        if key.endswith('valid') and case=='release_reset':
            v={'a':'0','d':'phase==5','e':'0','b':'0','c':'(phase==1 || phase==4)'}[ch]
        if key.endswith('valid') and case=='grant_reset':
            v={'a':'(phase==1 || phase==5)','d':'(phase==2 || phase==6)','e':'phase==7','b':'0','c':'0'}[ch]
        if key=='a.ready' and case=='preoffer':v='phase>=3'
        if key=='d.ready' and case=='burst_stall':v='phase!=3'
        if key.endswith('payload.opcode'):
            v={'a':'6' if grant else '4','d':'5' if grant else '1','b':'6','c':'4'}[ch]
            if ch=='a':
                if burst_a:v='0'
                if case=='arithmetic':v='2'
                if case=='logical':v='3'
                if case=='hint':v='5'
                if case=='preoffer':v='phase==2 ? 0 : 4'
            if ch=='d':
                if burst_a or case=='wrong_opcode':v='0'
                if case=='hint':v='2'
                if release:v='6'
            if ch=='c':
                if release:v='7' if case=='release_data' else '6'
                if case in ('probe_data','probe_perm_data'):v='5'
            if ch=='b' and case=='probe_perm_data':v='7'
        if key.endswith('payload.size'):
            v='3' if burst_a or burst_d or case in ('probe_data','probe_perm_data','release_data') else '2'
            if key=='d.payload.size' and case=='wrong_size':v='3'
        if key.endswith('payload.address'):
            v="32'h100"
            if case=='probe_two_addresses':v="phase==2 ? 32'h200 : 32'h100" if ch=='b' else "phase==3 ? 32'h200 : 32'h100"
            if case=='probe_capacity':v='phase*256'
            if case=='probe_bad_address' and ch=='c':v="32'h300"
        if key.endswith('payload.source'):
            if case=='reorder':v='phase==1' if ch=='a' else 'phase==4'
            if case=='a_header' and ch=='a':v='phase==2'
            if case=='d_header' and ch=='d':v='phase==3'
        if key.endswith('payload.param'):
            if ch=='a':v='1' if grant or case=='bad_param' else '4' if case=='arithmetic' else '3' if case=='logical' else '0'
            if ch=='b':v='2'
            if ch=='c' and probe:v='0' if case=='probe_bad_cap' else '1'
        if key=='a.payload.mask':v='0' if case=='bad_mask' else '15'
        if key.endswith('payload.data'):v='phase' if case=='burst_stall' else '0'
        if case=='error_response' and key in ('d.payload.denied','d.payload.corrupt'):v='1'
        if case=='orphan_e' and key=='e.payload.sink':v='1'
        wires.append(f'wire [{row[3]-1}:0] {row[0]}={v};')
    reset='phase==0 || phase==3' if case=='grant_reset' else 'phase==0 || phase==2' if case.endswith('reset') else 'phase==0'
    source+=f'module fixture(input clk);reg [4:0] phase=0;always @(posedge clk)if(phase<16)phase<=phase+1;wire reset={reset};\n'+'\n'.join(wires)+'\nmonitor dut(.*);endmodule\n'
    (tmp_path/'design.sv').write_text(source)
    (tmp_path/'proof.sby').write_text('''[options]
mode prove
depth 24
[engines]
smtbmc yices
[script]
read -formal design.sv
prep -top fixture
[files]
design.sv
''')
    r=run_group(['nice','-n','10','sby','-f','proof.sby'],cwd=tmp_path,capture=True,timeout=45)
    status=tmp_path/'proof/status'
    assert status.exists(),r.stdout+r.stderr
    good=case in ('good','single_source','single_sink','zero','reorder','arithmetic','logical','hint','put_burst','read_burst','preoffer','error_response',
                  'grant','release','release_data','probe','probe_zero','probe_two_addresses','probe_data','probe_reuse','reset','probe_reset','release_reset','grant_reset')
    assert status.read_text().split()[0]==('PASS' if good else 'FAIL'),r.stdout+r.stderr
