import shutil
import pytest
from rvw.common.proc import run_group
from rvw.formal.axi_transactions import render
from rvw.formal.typed_bus_checks import render as channels

pytestmark=pytest.mark.slow


def fields(kind='axi4'):
    result={}
    payloads=dict(aw=dict(addr=32),w=dict(data=32,strb=4),b=dict(resp=2),ar=dict(addr=32),r=dict(data=32,resp=2))
    if kind=='axi4':
        for ch in ('aw','ar'):payloads[ch].update(id=2,len=8,size=3,burst=2,lock=1,cache=4)
        payloads['b']['id']=2;payloads['r'].update(id=2,last=1);payloads['w']['last']=1
    for ch,payload in payloads.items():
        for key,width in [('valid',1),('ready',1),*[(f'payload.{k}',v) for k,v in payload.items()]]:
            name=ch+'.'+key
            result[name]=(name.replace('.','_'),None,None,width,1,False)
    return result


@pytest.mark.parametrize('case',['good','w_before_aw','w_before_aw_narrow','w_before_aw_strobe','zero','reorder','interleave','exclusive','error_response','narrow','wrap','unaligned','strobe','wlast','w_missing_last','w_short_prefix','w_prefix_ok','b_premature','rlast','rid','bid','r_exokay','b_exokay','boundary','capacity'])
def test_full_axi_tracker(tmp_path,case):
    check(tmp_path,'axi4',case)


@pytest.mark.parametrize('case',['good','w_before_aw','zero','bid','r_exokay'])
def test_lite_tracker(tmp_path,case):
    check(tmp_path,'axi_lite4',case)


def check(tmp_path,kind,case):
    if not shutil.which('sby') or not shutil.which('yices-smt2'):
        pytest.skip('SBY and Yices required')
    sigs=fields(kind);source,_=channels(kind,sigs,'monitor')
    source=source.replace('\nendmodule\n','\n'+render(kind,sigs,2,max_beats=4)+'\nendmodule\n')
    wires=[]
    lite=kind=='axi_lite4'
    for key,row in sigs.items():
        ch=key.split('.')[0];v='0'
        if key.endswith('ready'):v='1'
        if key.endswith('valid'):
            v={'aw':'phase==1','w':'phase==2' if lite else '(phase==2 || phase==3)',
               'b':'phase==3' if lite else 'phase==4','ar':'phase==1',
               'r':'phase==2' if lite else '(phase==2 || phase==3)'}[ch]
            if case.startswith('w_before_aw'):
                v={'aw':'phase==3','w':'phase==1' if lite else '(phase==1 || phase==2)',
                   'b':'phase==4','ar':'phase==1','r':'phase==2' if lite else '(phase==2 || phase==3)'}[ch]
            if case=='zero':v='phase==1'
            if case=='reorder':v='(phase==1 || phase==2)' if ch in ('aw','ar','w') else '(phase==3 || phase==4)'
            if case=='interleave':v='(phase>=3 && phase<=6)' if ch=='r' else '(phase==1 || phase==2)' if ch=='ar' else v
            if case=='w_missing_last' and ch=='b':v='0'
            if case=='w_short_prefix':v={'aw':'phase==3','w':'(phase==1 || phase==2)','b':'0'}.get(ch,v)
            if case=='w_prefix_ok':v={'aw':'phase==2','w':'(phase==1 || phase==4)','b':'phase==5'}.get(ch,v)
            if case=='b_premature' and ch=='b':v='phase==2'
            if case=='capacity':v='(phase>=1 && phase<=3)' if ch=='ar' else '0'
        if key.endswith('payload.id'):
            v='1' if ch in ('aw','b') else '0'
            if case=='rid' and ch=='r':v='1'
            if case=='bid' and ch=='b':v='0'
            if case=='interleave' and ch in ('ar','r'):v='phase==2' if ch=='ar' else '(phase==4 || phase==6)'
            if case=='reorder':v={'aw':'phase==1','b':'phase==4','ar':'phase==2','r':'phase==3'}[ch]
        if key.endswith('payload.len'):v='0' if case in ('zero','reorder','capacity') else '1'
        if key=='aw.payload.len' and case=='w_short_prefix':v='0'
        if key.endswith('payload.size'):v='2'
        if key=='aw.payload.size' and case in ('narrow','wrap','strobe','w_before_aw_narrow','w_before_aw_strobe'):v='1'
        if key.endswith('payload.burst'):v='1'
        if key.endswith('payload.strb'):v='15'
        if key=='w.payload.strb' and case=='narrow':v='phase==2 ? 3 : 12'
        if key=='w.payload.strb' and case=='w_before_aw_narrow':v='phase==1 ? 3 : 12'
        if key=='w.payload.strb' and case=='wrap':v='phase==2 ? 12 : 3'
        if key=='w.payload.strb' and case=='unaligned':v='phase==2 ? 14 : 15'
        if key=='aw.payload.addr' and case=='unaligned':v='1'
        if key=='aw.payload.addr' and case=='wrap':v='2'
        if key=='aw.payload.burst' and case=='wrap':v='2'
        if key.endswith('payload.last'):
            v='phase==3' if case not in ('zero','reorder','w_before_aw','w_before_aw_narrow','w_before_aw_strobe') else ('1' if case in ('zero','reorder') else 'phase==2' if ch=='w' else 'phase==3')
            if case==ch+'last':v='1'
            if ch=='w' and case in ('w_missing_last','w_short_prefix'):v='0'
            if ch=='w' and case=='w_prefix_ok':v='phase==4'
        if key=='r.payload.last' and case=='interleave':v='phase>=5'
        if key.endswith('payload.resp') and case=='error_response':v='2'
        if key.endswith('payload.lock') and case=='exclusive':v='1'
        if key.endswith('payload.resp') and (case=='exclusive' or case==ch+'_exokay'):v='1'
        if key=='ar.payload.addr' and case=='boundary':v="32'hffc"
        # AXI-Lite has no IDs: use an unsolicited response for its orphan case.
        if lite and case=='bid' and key=='b.valid':v='phase==1'
        wires.append(f'wire [{row[3]-1}:0] {row[0]}={v};')
    source+='module fixture(input clk); reg [4:0] phase=0; always @(posedge clk) if(phase<12) phase<=phase+1; wire reset=phase==0;\n'+'\n'.join(wires)+'\nmonitor dut(.*); endmodule\n'
    (tmp_path/'design.sv').write_text(source)
    engine='abc pdr' if lite else 'smtbmc yices'
    (tmp_path/'proof.sby').write_text(f'''[options]
mode prove
depth 20
[engines]
{engine}
[script]
read -formal design.sv
prep -top fixture
[files]
design.sv
''')
    r=run_group(['nice','-n','10','sby','-f','proof.sby'],cwd=tmp_path,capture=True,timeout=60)
    status=tmp_path/'proof/status'
    assert status.exists(),r.stdout+r.stderr
    good=case in ('good','w_before_aw','zero','reorder','interleave','exclusive','error_response','w_prefix_ok','narrow','wrap','unaligned','w_before_aw_narrow')
    assert status.read_text().split()[0]==('PASS' if good else 'FAIL'),r.stdout+r.stderr
