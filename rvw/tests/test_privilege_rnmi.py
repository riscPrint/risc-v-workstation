import pytest
from rvw.privilege import campaign
from rvw.privilege.rnmi import State,programs,reference

pytestmark=pytest.mark.fast


def test_saved_frame_survives_an_ordinary_exception():
    m=State(mode='S',pc=0x100,mprv=True)
    assert not m.entry(1,0x200)
    m.write_nmie(True);assert m.entry(1,0x200)
    saved=dict(m.frame)
    assert m.mode=='M' and not m.nmie and not m.effective_mprv
    m.normal_exception(0x300);assert m.frame==saved
    m.ret();assert (m.mode,m.pc,m.nmie,m.mprv)==('S',0x100,True,False)
    m.write_nmie(False);assert m.nmie


def test_matrix_and_expected_frames():
    c=campaign.load('examples/privilege/nmi-matrix.json');rows=campaign.scenarios(c)
    assert len(rows)==12 and len({r['id'] for r in rows})==12
    assert all(reference(r)['status']=='pass' for r in rows)
    assert all(r['events'][0]['when_pc']=='rnmi_wait' for r in rows)
    assert all('.rnmi_exception' in r['assembly'] and '0x20000' in r['assembly'] for r in rows)
    pending=[r['assembly'] for r in rows if r['reference_model']['pending']]
    assert len(pending)==6 and all('bnez s4, fail' in s and 'la t1, main_end' in s for s in pending)
    assert all('Spike has no external RNMI' in r['reference_unavailable'] for r in rows)


def test_exception_vector_is_a_project_choice():
    c=campaign.load('examples/privilege/nmi-matrix.json');c['nmi'].pop('exception_vector')
    with pytest.raises(ValueError,match='exception vector'):programs(c)
    c['nmi']['exception_uses_mtvec']=True
    assert len(programs(c))==12
    c['nmi']['pmp_entries']=0
    with pytest.raises(ValueError,match='eight'):programs(c)


def test_return_profiles():
    c=campaign.load('examples/privilege/nmi-return.json');rows=campaign.scenarios(c)
    assert len(rows)==6
    assert all('csrr s5, 0x744' in r['assembly'] for r in rows)
    assert all('.word 0x70200073' in r['assembly'] and 'csrr t0, mstatus' in r['assembly'] for r in rows)
