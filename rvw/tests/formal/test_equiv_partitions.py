import json
import shutil
import pytest
from rvw.formal.equiv_partitions import projection


@pytest.mark.fast
def test_projection_keeps_state_and_initialization():
    original={'modules':{'top':{'ports':{'clk':{'direction':'input','bits':[1]},'y':{'direction':'output','bits':[2]}},
        'netnames':{'state':{'bits':[3],'attributes':{'init':'0'}}},
        'cells':{'reg':{'type':'$dff','connections':{'Q':[3]}}}}}}
    projected=projection(original,'top',[3])['modules']['top']
    assert set(projected['ports'])=={'clk','partition_observation'}
    assert projected['ports']['partition_observation']['bits']==[3]
    assert projected['netnames']['state']['attributes']['init']=='0'
    assert projected['cells']==original['modules']['top']['cells']
    assert 'y' in original['modules']['top']['ports']


@pytest.mark.fast
def test_observation_name_collision_fails():
    d={'modules':{'top':{'ports':{'partition_observation':{}},'netnames':{}}}}
    with pytest.raises(ValueError,match='collision'):projection(d,'top',[1])


@pytest.mark.slow
@pytest.mark.skipif(not all(shutil.which(t) for t in ('yosys','sby','eqy','yosys-abc')),reason='native equivalence tools')
def test_automatic_internal_closed_proof(tmp_path):
    from rvw.cli import main
    for side in ('a','b'):
        (tmp_path/(side+'.v')).write_text('module top(input clk,reset,a,output q);reg state;always @(posedge clk) if(reset)state<=0;else state<=a;assign q=state;endmodule')
    out=tmp_path/'proof'
    assert main(['formal','equiv-partitions','--gold',str(tmp_path/'a.v'),'--gate',str(tmp_path/'b.v'),
                 '--top','top','--reset','reset','--out',str(out),'--timeout','60'])==0
    r=json.loads((out/'result.json').read_text())
    assert r['status']=='equivalent' and r['output_equivalence']=='equivalent'
    assert r['matched_count']==1 and r['partitions'][0]['status']=='equivalent'


@pytest.mark.slow
@pytest.mark.skipif(not all(shutil.which(t) for t in ('yosys','sby','eqy','yosys-abc')),reason='native equivalence tools')
def test_internal_mismatch_does_not_relabel_output_equivalence(tmp_path):
    from rvw.cli import main
    for side,value in [('a','a'),('b','!a')]:
        (tmp_path/(side+'.v')).write_text(f'module top(input clk,reset,a,output q);reg hidden;always @(posedge clk) if(reset)hidden<=0;else hidden<={value};assign q=a;endmodule')
    out=tmp_path/'proof'
    assert main(['formal','equiv-partitions','--gold',str(tmp_path/'a.v'),'--gate',str(tmp_path/'b.v'),
                 '--top','top','--reset','reset','--out',str(out),'--timeout','90'])==1
    r=json.loads((out/'result.json').read_text())
    assert r['output_equivalence']=='equivalent' and r['status']=='inconclusive'
    assert r['partitions'][0]['status']=='not_equivalent'
