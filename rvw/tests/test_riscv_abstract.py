import json
from pathlib import Path
import pytest
from rvw.formal.riscv_abstract import restrict, run
pytestmark=pytest.mark.fast
PLAN=dict(module='Core',clock='clk',reset='reset',in_flight=['decode_valid','execute_valid'])


def test_restriction_preserves_source_assumptions():
    source='module Core(input clk,reset); always @* assume(reset == $initstate); endmodule'
    result,assumption=restrict(source,PLAN)
    assert 'assume(reset == $initstate)' in result
    assert "{31'b0, decode_valid} + {31'b0, execute_valid}" in assumption
    assert 'if(!reset)' in assumption and '<= 1' in assumption


def test_restriction_requires_exact_module_and_plain_signals():
    with pytest.raises(ValueError,match='once'): restrict('module Other; endmodule',PLAN)
    with pytest.raises(ValueError,match='identifiers'): restrict('module Core; endmodule',dict(PLAN,in_flight=['a; assume(0)']))


def test_wrong_schema_does_not_capture(tmp_path):
    with pytest.raises(ValueError,match='schema|expected'): run({}, {},tmp_path/'out')
    assert not (tmp_path/'out').exists()


def test_unbounded_mcp_keeps_inconclusive_results(tmp_path):
    from rvw.formal.commands.riscv_proof import mcp_run
    (tmp_path/'result.json').write_text(json.dumps(dict(schema='rvw.riscv-proof/1',status='inconclusive')))
    class Job:
        def run(self,argv): return 3
    assert mcp_run(Job(),out=str(tmp_path))['status']=='inconclusive'


def test_abstract_cli_and_mcp_discovery():
    from rvw.cli import build_parser
    from rvw.formal.commands.riscv_abstract import mcp_tools
    args=build_parser().parse_args(['formal','riscv-abstract','--manifest','x','--out','y'])
    assert args.budget==240
    assert mcp_tools()[0].name=='formal_riscv_abstract'


def test_retaining_a_word_preserves_its_actual_state():
    from rvw.formal.riscv_abstract import restore_words
    design={'modules':{'Top':{'ports':{},'netnames':{
        'mem[0]':{'bits':[1,2],'attributes':{'init':'01'}},
        'mem[1]':{'bits':[3,4],'attributes':{'init':'00'}}},
        'cells':{'word0':{'type':'$dff','connections':{'Q':[1,2]}},
                 'word1':{'type':'$dff','connections':{'Q':[3,4]}}}}}}
    collected={'modules':{'Top':{'cells':{'mem':{'parameters':{'SIZE':'10','OFFSET':'0','MEMID':'mem'}}}}}}
    result=restore_words(design,collected,{'top':'Top','memory':'mem'},[0])['modules']['Top']
    assert 'word0' in result['cells'] and 'word1' not in result['cells']
    assert result['netnames']['mem[0]']['attributes']['init']=='01'
    assert 'rvw_ram_word_1' in result['ports']
    assert not any(c['type']=='$assume' for c in result['cells'].values())


def test_isa_exposes_abstraction_without_qualifying_the_full_core():
    from rvw.cli import build_parser
    args=build_parser().parse_args(['formal','isa','--out','x','--abstraction','map.json'])
    assert args.abstraction=='map.json'


def test_conflicting_engine_answers_cannot_qualify_a_proof():
    from rvw.formal.riscv_abstract import native_closed
    assert native_closed({'status':'inconclusive','rows':[{'status':'pass'}]})
    assert not native_closed({'status':'inconclusive','rows':[{'status':'pass'},{'status':'fail'}]})
    assert not native_closed({'status':'fail','rows':[{'status':'pass'}]})
