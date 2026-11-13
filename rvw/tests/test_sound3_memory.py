import pytest
from rvw.memory.axiomatic import search

pytestmark = pytest.mark.fast


def events(value=7):
    return [dict(id='w',hart=0,order=0,kind='W',address=0,size=4,write=7,addr=[],data=[],ctrl=[]),
            dict(id='r',hart=1,order=0,kind='R',address=0,size=4,read=value,read_from='w',addr=[],data=[],ctrl=[])]


def test_declared_read_from_value_is_checked_before_sc_fast_path():
    with pytest.raises(ValueError, match='value differs'):
        search(events(0), {(0,4):0})
    assert search(events(), {(0,4):0})['status']=='allowed'


def test_declared_read_from_cannot_reverse_program_order():
    rows=events(); rows[1].update(hart=0,order=0);rows[0]['order']=1
    with pytest.raises(ValueError, match='program order'):
        search(rows,{(0,4):0})


def test_missing_register_dependency_is_error():
    from rvw.memory.dependency_consistency import validate_register_dependencies
    rows=[dict(hart=0,order=0,insn=0x00002083,rd=1,memory_model={'id':'load','kind':'R','addr':[]}),
          dict(hart=0,order=1,insn=0x0000a103,rd=2,memory_model={'id':'use','kind':'R','addr':[]})]
    with pytest.raises(ValueError, match='omit observed'):
        validate_register_dependencies(rows,64)
    rows[1]['memory_model']['addr']=['load']
    validate_register_dependencies(rows,64)


def test_observed_value_cannot_change_between_write_and_use():
    from rvw.memory.dependency_consistency import validate_register_dependencies
    rows=[dict(hart=0,order=0,insn=0x00100093,rd=1,rd_wdata=1),
          dict(hart=0,order=1,insn=0x0000a103,rs1_rdata=2,rd=2,memory_model={'id':'use','kind':'R','addr':[]})]
    with pytest.raises(ValueError,match='register value'):
        validate_register_dependencies(rows,64)


def test_load_result_is_checked_against_observed_bytes():
    from rvw.memory.dependency_consistency import validate_register_dependencies
    rows=[dict(hart=0,order=0,insn=0x00002083,rd=1,rd_wdata=9,mem_rdata=7,
               memory_model={'id':'load','kind':'R','size':4,'addr':[]})]
    with pytest.raises(ValueError,match='load result'):
        validate_register_dependencies(rows,64)


def test_load_to_branch_control_dependency_cannot_be_omitted():
    from rvw.memory.dependency_consistency import validate_register_dependencies
    rows=[dict(hart=0,order=0,insn=0x00002083,rd=1,memory_model={'id':'load','kind':'R','addr':[]}),
          dict(hart=0,order=1,insn=0x00008063,rd=0),
          dict(hart=0,order=2,insn=0x00002023,rd=0,memory_model={'id':'store','kind':'W','addr':[],'data':[],'ctrl':[]})]
    with pytest.raises(ValueError,match='control dependencies omit'):
        validate_register_dependencies(rows,64)


def test_equal_values_do_not_erase_declared_store_identity():
    rows=events();rows[1].update(hart=0,order=2)
    rows.insert(1,dict(rows[0],id='newer',order=1))
    assert search(rows,{(0,4):0})['status']=='forbidden'


def test_mutable_csr_dataflow_is_unavailable_evidence():
    from rvw.memory.dependency_consistency import validate_register_dependencies
    row=dict(hart=0,order=0,insn=0x300020f3,rd=1,rd_wdata=0)
    assert 'mutable CSR' in validate_register_dependencies([row],64)


def test_cli_reports_contradictory_declaration_as_error(capsys):
    import json
    from rvw.memory.cli import emit
    code=emit(lambda:search(events(0),{(0,4):0}))
    assert code==2
    assert json.loads(capsys.readouterr().out)['status']=='error'
