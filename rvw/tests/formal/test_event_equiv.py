import json
import shutil
import pytest
from rvw.cli import main
from rvw.formal.common import async_state_problems


@pytest.mark.skipif(not all(shutil.which(t) for t in ('yosys','eqy','sby','yosys-abc')),reason='needs native formal tools')
@pytest.mark.parametrize('sampled,mutant',[(True,False),(True,True),(False,False)])
def test_clock_gating_insertion_sampled_contract(tmp_path,sampled,mutant):
    gold,gate=tmp_path/'gold.v',tmp_path/'gate.v'
    gold.write_text('module Top(input clk,reset,en,a,output reg q);always @(posedge clk) if(reset)q<=0;else if(en)q<=a;endmodule')
    gate.write_text('module Top(input clk,reset,en,a,output reg q);reg active;always @* if(!clk)active<=reset|'+('!en' if mutant else 'en')+';wire gclk=clk&active;always @(posedge gclk)if(reset)q<=0;else q<=a;endmodule')
    out=tmp_path/'out'
    options=['--sampled-events','--stable-at-edge','en','--stable-at-edge','a'] if sampled else []
    main(['formal','equiv','--gold',str(gold),'--gate',str(gate),'--top','Top','--reset','reset',
          '--unmatched-state','prove',*options,'--timeout','90','--out',str(out)])
    result=json.loads((out/'result.json').read_text())
    if sampled:
        assert result['status']=='conditional',result
        assert result['contract_verdict']==('not_equivalent' if mutant else 'equivalent'),result
        assert result['event_model']['stable_at_edge']==['en','a']
        if mutant and shutil.which('vcd2fst'):
            replay=tmp_path/'replay'
            main(['formal','cex','--result',str(out),'--out',str(replay)])
            observed=json.loads((replay/'result.json').read_text())
            assert observed['disposition']=='reproduced',observed
    else:assert result['status']=='inconclusive',result


def test_latch_opt_in_keeps_other_state_checks():
    module={'cells':{'latch':{'type':'$dlatch','connections':{'D':[1],'Q':[2],'EN':[3]}}}}
    assert async_state_problems({'Top':module})
    assert not async_state_problems({'Top':module},allow_latches=True)
    module['cells']['latch']['type']='$adlatch'
    assert async_state_problems({'Top':module},allow_latches=True)


def test_event_mcp_flags_and_input_constraints():
    from rvw.formal.mcp_tools import _argv,mcp_tools
    argv=_argv('equiv',{'sampled_events':True,'stable_at_edge':['en','a'],'unmatched_state':'prove'})
    assert '--sampled-events' in argv and 'True' not in argv
    assert argv.count('--stable-at-edge')==2
    tool=next(t for t in mcp_tools() if t.name=='formal_equiv')
    assert tool
