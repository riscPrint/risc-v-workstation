"""CSR inventories and cut contracts must not grant whole-core signoff."""
import json
from pathlib import Path
import pytest
from rvw.formal.csr_slices import inventory, prepare, execute
from rvw.formal.machine_checks import generate

pytestmark = pytest.mark.fast


def test_inventory_uses_catalog_addresses():
    assert inventory([0x340, 0x341, 0x340]) == [
        {'csr':'mscratch','address':0x340}, {'csr':'mepc','address':0x341}]
    with pytest.raises(ValueError, match='unique catalog'):
        inventory([0xfff])


def plan(tmp_path):
    (tmp_path/'core.v').write_text('module core(input clock,reset); endmodule')
    signals = {n:n for n in ('event','address','op','operand','before','after','read_data','trap','mode')}
    return dict(schema='rvw.csr-slices/1',addresses=[0x340,0x341],
                machine=dict(schema='rvw.machine-checks/1',xlen=32,top='core',clock='clock',reset='reset',sources=['core.v'],depth=25),
                bindings={'mscratch':dict(write_mask=0xffffffff, signals=signals, cone_cuts=['operand'])})


def test_unbound_inventory_rows_remain_gaps(tmp_path):
    result=prepare(plan(tmp_path),tmp_path,tmp_path/'out')
    assert result['rows'][1]['csr']=='mepc'
    assert result['rows'][1]['status']=='unsupported'
    path=Path(result['rows'][0]['manifest'])
    generate(json.loads(path.read_text()),path.parent,tmp_path/'job')
    script=(tmp_path/'job/csr_consistency/check.sby').read_text()
    assert 'depth 25' in script
    assert 'select -assert-count 1 core/w:operand\ncutpoint core/w:operand' in script


def test_cut_names_cannot_inject_yosys_commands(tmp_path):
    obj=plan(tmp_path)
    obj['bindings']['mscratch']['cone_cuts']=['a; delete *']
    with pytest.raises(ValueError,match='local RTL'):
        prepare(obj,tmp_path,tmp_path/'out')


def test_local_result_retains_scope_and_does_not_claim_bank_pass(tmp_path, monkeypatch):
    import rvw.formal.csr_slices as slices
    def native(*args):
        return {'rows':[dict(status='inconclusive',local_status='bounded',
                             reason='Needs composition',native={'check':'PASS','cover':'PASS'})]}
    monkeypatch.setattr(slices,'run',native)
    report=execute(plan(tmp_path),tmp_path,tmp_path/'out')
    assert report['status']=='inconclusive'
    assert report['rows'][0]['local_status']=='bounded'
    assert report['rows'][0]['scope']=='local cone contract'
    assert report['rows'][1]['status']=='unsupported'


def test_isa_table_keeps_each_csr_gap(tmp_path, monkeypatch):
    import rvw.formal.csr_slices as slices
    from rvw.formal.isa import run, table
    monkeypatch.setattr(slices, 'execute', lambda *args: dict(status='inconclusive',rows=[
        dict(csr='mscratch',status='inconclusive',local_status='bounded'),
        dict(csr='mepc',status='unsupported',reason='Needs WARL model')]))
    path=tmp_path/'slices.json';path.write_text(json.dumps({'schema':'rvw.csr-slices/1'}))
    report=run(None,tmp_path/'out',10,'test',machine=path)
    text=table(report)
    assert 'csr_consistency:mscratch | inconclusive' in text
    assert 'csr_consistency:mepc | unsupported' in text
    assert report['status']=='inconclusive'
