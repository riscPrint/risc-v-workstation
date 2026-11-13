import pytest
from rvw.privilege import campaign
from rvw.privilege.controllers import NestedPriority
from rvw.privilege.fast_preemption import reference as preemption_reference
from rvw.privilege.fast_vector import resolve,reference as vector_reference

pytestmark=pytest.mark.fast


def test_zero_group_bits_disables_nested_preemption():
    m=NestedPriority(8,0);assert m.eligible(255)
    m.trap(72);assert not any(m.eligible(p) for p in range(256))
    m.ret();assert m.eligible(255)


def test_preemption_same_group_and_software_restore():
    rows=campaign.scenarios(campaign.load('examples/privilege/fast-preemption.json'))
    assert len(rows)==12 and all(preemption_reference(r)['status']=='pass' for r in rows)
    eligible={r['id']:r['reference_model']['preempts'] for r in rows}
    assert not eligible['fast-preemption-4-64'] and eligible['fast-preemption-8-64']
    assert eligible['fast-preemption-4-32'] and not eligible['fast-preemption-0-32']
    assert all('csrw 0x346, s4' in r['assembly'] and 'csrw mepc, s6' in r['assembly'] for r in rows)


def test_jump_table_signed_offsets_fallback_and_alignment():
    assert resolve(0x1000,1,7,None,0x2003,0x3000,32)==(0xfc8,0x2000)
    assert resolve(0x1000,2,11,3,0x2003,0x3000,16)==(0x1030,0x2002)
    assert resolve(0x1000,1,11,1,0x2000,0x3000,32)==(0x1008,0x3000)
    for name in ('fast-vector','fast-vector-c'):
        rows=campaign.scenarios(campaign.load('examples/privilege/'+name+'.json'))
        assert len(rows)==18 and all(vector_reference(r)['status']=='pass' for r in rows)
    c=campaign.load('examples/privilege/fast-vector.json');c['spec_version']='old-clic-draft'
    with pytest.raises(ValueError,match='specification'):campaign.scenarios(c)


def test_signed_irq_and_new_csr_coverage_domains(tmp_path,monkeypatch):
    import json
    from types import SimpleNamespace
    from pathlib import Path
    def compile(command,**kw):
        Path(command[command.index('-o')+1]).write_bytes(b'elf fixture')
        return SimpleNamespace(returncode=0,stderr='')
    monkeypatch.setattr(campaign,'run_group',compile)
    out=tmp_path/'out'
    campaign.build('examples/privilege/fast-vector.json',out,gcc='fixture')
    groups=json.loads((out/'functional-groups.json').read_text())['groups']
    csr=next(g for g in groups if g['name']=='privilege_csr_mode')
    assert {'0x307','0x348','0x352','0x353'}.issubset(csr['domains'][0])
    irq=next(g for g in groups if g['name']=='privilege_irq')
    assert {1,2,(1<<63)-3,(1<<63)-7}.issubset(irq['domains'][0])
