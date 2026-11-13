import importlib.util
from pathlib import Path
import pytest

pytestmark=pytest.mark.fast
ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('div_smoke',ROOT/'examples/vexriscv/formal/div-smoke.py')
example=importlib.util.module_from_spec(spec);spec.loader.exec_module(example)


def test_closed_cone_retains_sequential_inputs():
    m={'ports':{'out':{'direction':'output','bits':[10]}},'netnames':{},'cells':{
        'reg':{'type':'$dff','port_directions':{'Q':'output','D':'input','CLK':'input'},'connections':{'Q':[10],'D':[11],'CLK':[2]}},
        'logic':{'type':'$not','port_directions':{'Y':'output','A':'input'},'connections':{'Y':[11],'A':[3]}},
        'unrelated':{'type':'$not','port_directions':{'Y':'output','A':'input'},'connections':{'Y':[20],'A':['0']}}}}
    example.closed_cone(m)
    assert set(m['cells'])=={'reg','logic'}
    assert m['cells']['reg']['connections']['CLK']==[2]


@pytest.mark.parametrize('op,funct3,signed',[('div',4,1),('divu',5,0),('rem',6,1),('remu',7,0)])
def test_opcode_and_boundary_contract(op,funct3,signed):
    wrapper=example.adapter(op,'zero')
    assert f".memory_INSTRUCTION(32'h{funct3<<12:08x})" in wrapper
    assert f".execute_IS_RS1_SIGNED(1'b{signed})" in wrapper
    assert ".execute_RS2(32'h0)" in wrapper
    assert '.memory_arbitration_isStuck(active && !raw_done)' in wrapper
