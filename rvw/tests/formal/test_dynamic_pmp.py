import json
import shutil
import pytest
from rvw.cli import main
from rvw.formal.apps import generate


def plan(latency):
    widths={'clk':1,'reset':1,'request':1,'address':8,'size':2,'privilege':2,'operation':2,
            'mml':1,'mmwp':1,'locked':1,'rwx':3,'mode':2,'pmpaddr':6,'config':8,'grant':1}
    ports={n:{'direction':'output' if n in ('config','grant') else 'input','width':w} for n,w in widths.items()}
    prop={'id':'pmp_access','kind':'pmp',**{n:n for n in ('address','request','grant','size','privilege','operation','mml','mmwp')},
          'entries':[{'config':'config','address':'pmpaddr'}],'latency':latency}
    return {'schema':'rvw.formal-apps/1','top':'Pmp','clock':'clk','reset':'reset','verilog':['dut.v'],'ports':ports,'properties':[prop]}


def rtl(latency,mutant):
    lines=['module Pmp(input clk,reset,request,input [7:0] address,input [1:0] size,privilege,operation,mode,',
           'input mml,mmwp,locked,input [2:0] rwx,input [5:0] pmpaddr,output [7:0] config,output '+('reg ' if latency else 'wire ')+'grant);',
           "wire [2:0] legal_rwx=(!mml && rwx[1:0]==2) ? 0 : rwx;assign config={locked,2'b0,mode,legal_rwx};",
           'reg [2:0] rights;reg [8:0] lo,hi,mask;wire [8:0] last={1\'b0,address}+((9\'d1<<size)-1);reg allow;',
           'always @* begin rights=0;lo=0;hi=0;mask=0;',
           'if(!mml) rights=(privilege==3 && !locked)?7:legal_rwx;else if(privilege==3) begin case({locked,legal_rwx})']
    m=[0,0,3,0,0,0,3,0,0,1,4,3,4,5,5,1]
    su=[0,1,1,3,4,5,3,7,0,0,4,0,0,0,4,1]
    lines += [f'{i}:rights={r};' for i,r in enumerate(m)]
    lines += ['endcase end else begin case({locked,legal_rwx})']+[f'{i}:rights={r};' for i,r in enumerate(su)]
    lines += ['endcase end',
              'case(mode) 1:begin lo=0;hi={1\'b0,pmpaddr,2\'b0};end 2:begin lo={1\'b0,pmpaddr,2\'b0};hi=lo+4;end',
              '3:begin if(!pmpaddr[0])mask=7;else if(!pmpaddr[1])mask=15;else if(!pmpaddr[2])mask=31;else if(!pmpaddr[3])mask=63;else if(!pmpaddr[4])mask=127;else mask=255;',
              'lo={1\'b0,pmpaddr,2\'b0} & ~mask;hi=lo+mask+1;end endcase',
              'allow=(privilege==3 && !mmwp && !(mml && operation==2));',
              'if(mode!=0 && hi>lo && address<hi && last>=lo) allow=(address>=lo && last<hi && (operation==0 ? rights[0] : (operation==1 ? rights[1] : (operation==2 ? rights[2] : 0))));',
              'if(last>=256 || privilege==2 || operation==3)allow=0;end']
    expression='1' if mutant=='grant' else 'allow'
    if latency and mutant!='current':lines += ['always @(posedge clk) if(reset)grant<=0;else grant<=request && '+expression+';']
    elif latency:lines += ['always @* grant=request && allow;']
    else:lines += ['assign grant=request && '+expression+';']
    return '\n'.join(lines+['endmodule'])


@pytest.mark.skipif(not all(shutil.which(t) for t in ('yosys','sby','yosys-abc')),reason='needs native formal tools')
@pytest.mark.parametrize('latency,mutant',[(0,'none'),(1,'none'),(0,'grant'),(1,'current')])
def test_dynamic_all_modes_mml_table_and_request_policy(tmp_path,latency,mutant):
    p=plan(latency);(tmp_path/'dut.v').write_text(rtl(latency,mutant))
    manifest=tmp_path/'plan.json';manifest.write_text(json.dumps(p));out=tmp_path/'out'
    main(['formal','apps',str(manifest),'--out',str(out),'--mode','prove','--engine','abc:pdr','--timeout','90'])
    result=json.loads((out/'result.json').read_text())
    assert result['status']==('pass' if mutant=='none' else 'fail'),result


def test_pmp_binding_refuses_wrong_address_width():
    p=plan(0);p['ports']['pmpaddr']['width']=7
    with pytest.raises(ValueError,match='config/address widths'):generate(p,p['properties'][0])


@pytest.mark.skipif(not all(shutil.which(t) for t in ('yosys','sby','yosys-abc')),reason='needs native formal tools')
@pytest.mark.parametrize('mutant',[False,True])
def test_first_touched_region_blocks_crossing_access(tmp_path,mutant):
    p=plan(0)
    for n in ('locked','rwx','mode'):p['ports'].pop(n)
    for n,w in [('pmpaddr',6),('config',8),('mml',1),('mmwp',1),('nextaddr',6),('nextcfg',8)]:
        p['ports'][n]={'direction':'output','width':w}
    p['properties'][0]['entries'].append({'config':'nextcfg','address':'nextaddr'})
    guard='1' if mutant else '!(address<=7 && last>=4)'
    (tmp_path/'dut.v').write_text('module Pmp(input clk,reset,request,input [7:0] address,input [1:0] size,privilege,operation,output mml,mmwp,output [5:0] pmpaddr,nextaddr,output [7:0] config,nextcfg,output grant);'
                                 'assign mml=0;assign mmwp=0;assign pmpaddr=1;assign nextaddr=3;assign config=8\'h90;assign nextcfg=8\'h9f;'
                                 'wire [8:0] last={1\'b0,address}+((9\'d1<<size)-1);'
                                 'assign grant=request && privilege==0 && operation==0 && last<32 && '+guard+';endmodule')
    manifest=tmp_path/'plan.json';manifest.write_text(json.dumps(p));out=tmp_path/'out'
    main(['formal','apps',str(manifest),'--out',str(out),'--mode','prove','--engine','abc:pdr','--timeout','60'])
    result=json.loads((out/'result.json').read_text())
    assert result['status']==('fail' if mutant else 'pass'),result
