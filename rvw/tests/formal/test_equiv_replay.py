import json
import shutil
import pytest
from rvw.cli import main
from rvw.formal.equiv_cex import model_for_trace


@pytest.mark.skipif(not all(shutil.which(t) for t in ('yosys','eqy','sby','yosys-abc','vcd2fst')),reason='needs native formal and waveform tools')
def test_closed_output_counterexample_replays_in_simulation(tmp_path):
    gold,gate=tmp_path/'gold.v',tmp_path/'gate.v'
    text='module Top(input clk,reset,a,output reg q);always @(posedge clk) if(reset)q<=0;else q<=EXPR;endmodule'
    gold.write_text(text.replace('EXPR','a'));gate.write_text(text.replace('EXPR','~a'))
    proof=tmp_path/'proof'
    assert main(['formal','equiv','--gold',str(gold),'--gate',str(gate),'--top','Top','--reset','reset','--out',str(proof)])==1
    original=json.loads((proof/'result.json').read_text());assert original['status']=='not_equivalent',original
    out=tmp_path/'replay'
    assert main(['formal','cex','--result',str(proof),'--out',str(out),'--emit-testbench'])==1
    result=json.loads((out/'result.json').read_text())
    assert result['source_flow']=='equiv'
    assert result['disposition']=='reproduced',result
    assert result['status']=='inconclusive'
    assert result['baseline']['assertions']
    assert (out/'replay_tb.sv').is_file() and (out/'replay_model.v').is_file()
    assert original==json.loads((proof/'result.json').read_text())


def test_replay_refuses_missing_or_nonfailed_partition(tmp_path):
    root=tmp_path/'proof';directory=root/'eqy/part/model';directory.mkdir(parents=True)
    (directory/'design.il').write_text('fixture')
    trace=root/'eqy/part/engine_0/trace.vcd';trace.parent.mkdir();trace.write_text('fixture')
    with pytest.raises(ValueError,match='missing'):model_for_trace(root,trace)
    (directory.parent/'status').write_text('PASS 0 0')
    with pytest.raises(ValueError,match='failed native'):model_for_trace(root,trace)
    (directory.parent/'status').write_text('FAIL 0 0')
    assert model_for_trace(root,trace)==(directory/'design.il').resolve()
    with pytest.raises(ValueError,match='inside'):model_for_trace(root,tmp_path/'foreign.vcd')
