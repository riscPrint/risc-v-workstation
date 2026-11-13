import json
import pytest
from rvw.formal.machine_checks import monitor, generate, RULES
pytestmark = pytest.mark.fast


def test_rule_inventory():
    from rvw.formal.isa import MACHINE_CHECKS
    assert set(RULES) == set(MACHINE_CHECKS)
    assert 'assume' not in monitor('x0')
    assert 'assert(!retired_killed)' in monitor('flush_retirement')
    assert 'redirect ? redirect_pc : previous_pc' in monitor('trap_pc_chain')


def test_catalog_read_only_cannot_be_written():
    with pytest.raises(ValueError, match='read-only'):
        monitor('csr_consistency', dict(csr='mvendorid', write_mask=1))
    assert 'assert(trap == denied)' in monitor('csr_consistency', dict(csr='mvendorid', write_mask=0))


def test_capture_does_not_modify_source(tmp_path):
    source = 'module core(input clk, rst, r, k); endmodule\n'
    (tmp_path/'core.v').write_text(source)
    plan = dict(schema='rvw.machine-checks/1', xlen=32, sources=['core.v'], top='core',clock='clk',reset='rst',
                checks={'flush_retirement':{'signals':dict(retire='r',retired_killed='k')}})
    result = generate(plan,tmp_path,tmp_path/'out')
    assert (tmp_path/'core.v').read_text() == source
    assert 'rvw_machine_check rvw_check' in (tmp_path/'out/flush_retirement/input0.sv').read_text()
    assert result['status'] == 'generated'


def test_missing_observation_is_not_zero(tmp_path):
    (tmp_path/'core.v').write_text('module core; endmodule')
    plan = dict(schema='rvw.machine-checks/1',xlen=32,sources=['core.v'],checks={'x0':{'signals':{}}})
    with pytest.raises(ValueError, match='every input'):
        generate(plan,tmp_path,tmp_path/'out')


def test_no_binding_is_unsupported(tmp_path):
    result = generate(dict(schema='rvw.machine-checks/1',xlen=32,sources=[],checks={
        'exception_entry':{'unsupported':'No aligned state observations'}}),tmp_path,tmp_path/'out')
    assert result['rows'][0]['status'] == 'unsupported'
