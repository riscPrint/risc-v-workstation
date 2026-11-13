import json
import shutil

import pytest
from rvw.cli import main
from rvw.formal.state_encoding import load

TOOLS = all(shutil.which(t) for t in ('eqy', 'sby', 'yosys', 'yosys-abc', 'yices-smt2'))


@pytest.mark.skipif(not TOOLS, reason='needs native formal tools')
@pytest.mark.parametrize('kind', ['equal', 'wrong_mapping', 'missing_value', 'mutant', 'no_hint'])
def test_binary_to_onehot_relation(tmp_path, kind):
    gold=tmp_path/'gold.v'; gate=tmp_path/'gate.v'; contract=tmp_path/'encoding.json'
    gold.write_text('''module top(input clk,reset,enable,output y);
reg [1:0] state;
always @(posedge clk) if(reset) state<=0; else if(enable) state<=state==2 ? 0 : state+1;
assign y=state==2; endmodule''')
    gate.write_text('''module top(input clk,reset,enable,output y);
reg [2:0] phase;
always @(posedge clk) if(reset) phase<=1; else if(enable) phase<={phase[1:0],phase[2]};
assign y=phase=='''+('2' if kind=='mutant' else '4')+'; endmodule')
    values=[[0,1],[1,2],[2,4]]
    if kind=='wrong_mapping': values=[[0,1],[1,4],[2,2]]
    if kind=='missing_value': values=values[:2]
    contract.write_text(json.dumps({'schema':'rvw.equiv-encoding/1','mappings':[{'gold':'state','gate':'phase','values':values}]}))
    out=tmp_path/'out'
    extra=[] if kind=='no_hint' else ['--state-encoding',str(contract)]
    main(['formal','equiv','--gold',str(gold),'--gate',str(gate),'--top','top','--reset','reset',*extra,'--out',str(out)])
    result=json.loads((out/'result.json').read_text())
    assert result['status']==('equivalent' if kind=='equal' else 'inconclusive'), result
    if kind=='equal':
        assert result['encoding_verdict']=='proved'
        assert result['unmatched']=={'gold':[],'gate':[]}
        assert result['state_mapping'][0]['method']=='encoding'
        assert result['state_mapping'][0]['gold_width']==2
        assert result['state_mapping'][0]['gate_width']==3
    elif kind!='no_hint':
        assert result['encoding_verdict']=='not_proved' and result['traces'],result
    config=(out/'equiv.eqy').read_text()
    assert 'assume' not in config
    assert all(p['crossbits']=={} for p in result['partitions'])


@pytest.mark.fast
@pytest.mark.parametrize('values', [[[0,1],[1,1]], [[0,1],[0,2]], [[-1,0]], [[True,0]], []])
def test_encoding_table_refuses_ambiguous_values(tmp_path, values):
    source=tmp_path/'source.json';out=tmp_path/'out';out.mkdir()
    source.write_text(json.dumps({'schema':'rvw.equiv-encoding/1','mappings':[{'gold':'state','gate':'phase','values':values}]}))
    with pytest.raises(ValueError):load(source,out)
