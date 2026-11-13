"""Independent custom-state and trap expectations, not DUT qualification."""
import copy
import json
from pathlib import Path
import shutil
import pytest
from rvw.formal.custom_effects import load,transition,generate,rtl,predicate

EXAMPLE=Path(__file__).resolve().parents[2]/'examples/custom-isa/effects.json'


def test_explicit_vectors_and_effect_mutants(tmp_path):
    result=generate(EXAMPLE,tmp_path/'out')
    assert result['status']=='generated' and not result['gaps']
    assert [row['status'] for row in result['checks']]==['consistent']*5+['detected']*3
    assert result['generator_sha256']


def test_x0_keeps_non_register_effects_and_atomic_prestate():
    data=load(EXAMPLE);row=data['instructions'][0]
    vector=row['reference_vectors'][3]
    result=transition(data,row,vector['inputs'])
    assert not result['rd_write'] and result['state']['acc']==10 and result['memory']['commit']
    changed=dict(row,state_updates={'acc':'state.last_cause','last_cause':'state.acc'})
    inputs=dict(vector['inputs'],state={'acc':7,'last_cause':11})
    assert transition(data,changed,inputs)['state']=={'acc':11,'last_cause':7}


def test_load_masks_memory_data_and_faults_suppress_normal_updates(tmp_path):
    data=load(EXAMPLE);row=data['instructions'][0]
    row.update(result=['and','mem_rdata',65535],state_updates={'acc':['and','mem_rdata',65535]},
               memory={'kind':'load','address':'rs1','size':2})
    row['trap'].update(when=['ne',['and','rs1',1],0],cause=4,memory_fault_cause=5)
    row.pop('mutants');row.pop('reference_vectors')
    path=tmp_path/'load.json';path.write_text(json.dumps(data));data=load(path);row=data['instructions'][0]
    inputs=dict(rs1=8192,rs2=0,pc=4096,rd=3,mem_rdata=0xabcdffee,mem_fault=False,state={'acc':7,'last_cause':0})
    assert transition(data,row,inputs)['result']==65518
    result=transition(data,row,dict(inputs,mem_fault=True))
    assert result['trap'] and result['cause']==5 and result['state']=={'acc':7,'last_cause':5}
    assert not result['memory']['commit'] and not result['rd_write']


@pytest.mark.parametrize('change',[
 lambda d:d['instructions'][0].pop('memory'),
 lambda d:d['instructions'][0].update(trap=None),
 lambda d:d['instructions'][0]['trap'].pop('memory_fault_cause'),
 lambda d:d['instructions'][0]['state_updates'].update(unknown=1),
 lambda d:d['instructions'][0]['memory'].update(size=8),
 lambda d:d['instructions'][0].update(pc_after='unknown'),
])
def test_incomplete_effects_refused(tmp_path,change):
    data=json.loads(EXAMPLE.read_text());change(data)
    path=tmp_path/'bad.json';path.write_text(json.dumps(data))
    with pytest.raises((ValueError,KeyError)):load(path)


def test_fault_without_request_refused():
    data=load(EXAMPLE);row=data['instructions'][0]
    vector=copy.deepcopy(row['reference_vectors'][2]['inputs']);vector['mem_fault']=True
    with pytest.raises(ValueError,match='without an attempted'):transition(data,row,vector)


@pytest.mark.parametrize('mutant',[False,True])
def test_native_effects_against_independent_formula(tmp_path,mutant):
    if any(not shutil.which(t) for t in ('yosys','sby','yices-smt2')):
        pytest.skip('native Yosys, SBY and Yices required')
    from rvw.formal.apps import flow
    data=load(EXAMPLE);row=data['instructions'][0]
    if mutant:row['state_updates']['acc']=['xor','state.acc','rs2']
    model=tmp_path/'model.sv';model.write_text(rtl(data,row))
    oracle=tmp_path/'oracle.sv'
    oracle.write_text('''module oracle(input clk,reset,input [31:0] a,b,pc,acc,oldcause,input fault,input [4:0] rd);
wire selected,trap,wr,mvalid,mwrite,mcommit;
wire [31:0] result,nextpc,cause,addr,mdata,nextacc,nextcause; wire [3:0] mask;
wire [31:0] insn=32'h0000000b | ({27'b0,rd} << 7);
rvw_custom_xstacc_effects dut(.execute(!reset),.mem_fault(fault),.a(a),.b(b),.pc(pc),.mem_rdata(32'b0),.insn(insn),
.state_acc(acc),.state_last_cause(oldcause),.selected(selected),.trap(trap),.rd_write(wr),
.mem_valid(mvalid),.mem_write(mwrite),.mem_commit(mcommit),.result(result),.pc_after(nextpc),.cause(cause),
.mem_addr(addr),.mem_data(mdata),.mem_mask(mask),.next_acc(nextacc),.next_last_cause(nextcause));
wire bad_alignment=|a[1:0]; wire trapped=bad_alignment || fault;
wire [31:0] sum=acc+b;
always @(posedge clk) if(!reset) begin
 assume(!fault || !bad_alignment);
 assert(selected && trap==trapped);
 assert(nextacc==(trapped ? acc : sum));
 assert(nextcause==(trapped ? (fault ? 32'd7 : 32'd6) : oldcause));
 assert(nextpc==(trapped ? 32'd256 : pc+32'd4));
 assert(wr==(!trapped && rd!=0));
 assert(result==(!trapped && rd!=0 ? sum : 0));
 assert(mvalid==!bad_alignment && mwrite==!bad_alignment && mcommit==!trapped);
 assert(addr==(!bad_alignment ? a : 0) && mdata==(!bad_alignment ? b : 0));
 assert(mask==(!bad_alignment ? 4'b1111 : 4'b0000));
end
endmodule
''')
    result=flow([model,oracle],'oracle','clk','reset',tmp_path/'proof',4,'smtbmc:yices',30)
    assert result['status']==('fail' if mutant else 'pass'),result


def test_cli_mcp_and_generated_plan(tmp_path):
    from rvw.cli import main
    from rvw.formal.mcp_tools import _custom_effects
    assert main(['formal','custom-effects',str(EXAMPLE),'--out',str(tmp_path/'cli')])==0
    plan=json.loads((tmp_path/'cli/plan.json').read_text())
    cases=plan['instructions']['xstacc']
    assert any(case.get('scenario')=='memory fault' for case in cases)
    assert {case['origin'] for case in cases}=={'generated','project-reference'}
    class Job:
        def run(self,argv):return main(argv[3:])
    assert _custom_effects(Job(),manifest=str(EXAMPLE),out=str(tmp_path/'mcp'))['status']=='generated'


def test_native_unrequested_fault_is_rejected(tmp_path):
    if any(not shutil.which(t) for t in ('yosys','sby','yices-smt2')):
        pytest.skip('native Yosys, SBY and Yices required')
    from rvw.formal.apps import flow
    data=load(EXAMPLE)
    model=tmp_path/'model.sv';model.write_text(rtl(data,data['instructions'][0]))
    oracle=tmp_path/'invalid.sv'
    oracle.write_text('''module invalid(input clk,reset);
rvw_custom_xstacc_effects dut(.execute(!reset),.mem_fault(1'b1),.a(32'd8193),.b(32'd3),
.pc(32'd4096),.mem_rdata(32'b0),.insn(32'h18b),.state_acc(32'd7),.state_last_cause(32'b0));
endmodule
''')
    result=flow([model,oracle],'invalid','clk','reset',tmp_path/'proof',4,'smtbmc:yices',20)
    assert result['status']=='fail'


def test_wrong_independent_reference_is_a_mismatch(tmp_path):
    from rvw.cli import main
    data=json.loads(EXAMPLE.read_text())
    data['instructions'][0]['reference_vectors'][0]['expected']['result']=11
    source=tmp_path/'wrong.json';source.write_text(json.dumps(data))
    assert main(['formal','custom-effects',str(source),'--out',str(tmp_path/'out')])==1
    result=json.loads((tmp_path/'out/result.json').read_text())
    assert result['status']=='mismatch' and result['checks'][0]['status']=='mismatch'
