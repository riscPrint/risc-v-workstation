import pytest
from rvw.privilege import campaign,env_cbom

pytestmark=pytest.mark.fast


def test_cbom_matrix_and_exception_priority():
    for profile,count in [('envcfg-cbom',51),('envcfg-cbom-h',215)]:
        rows=campaign.scenarios(campaign.load('examples/privilege/'+profile+'.json'))
        assert len(rows)==count and len({r['id'] for r in rows})==count
        assert all('csrr t1, 0x30a' in r['assembly'] and 'csrr t1, 0x10a' in r['assembly'] for r in rows)
        assert all('cache side-effect' in r['scope'] for r in rows)
    assert env_cbom.decision('clean','M',0,0,0)==dict(denied=False,cause=11,expected_operation='clean')
    assert env_cbom.decision('flush','VU',0,1,1)['cause']==2
    assert env_cbom.decision('clean','VU',1,1,0)['cause']==22
    assert env_cbom.decision('inval','U',3,None,0)['cause']==2
    assert env_cbom.decision('inval','VS',3,1,3)['expected_operation']=='flush'
    assert env_cbom.decision('inval','VU',3,3,3)['expected_operation']=='inval'
    assert env_cbom.decision('inval','VU',1,3,3)['expected_operation']=='flush'


def test_declared_legal_subset_and_mode_selection():
    c=campaign.load('examples/privilege/envcfg-cbom.json');c['modes']=['S','U'];c['envcfg']['operations']=['inval']
    c['envcfg']['cbie']['machine']=[3];c['envcfg']['cbie']['supervisor']=[1]
    rows=campaign.scenarios(c)
    assert len(rows)==2
    assert rows[0]['expected_outcome']['expected_operation']=='inval'
    assert rows[1]['expected_outcome']['expected_operation']=='flush'
    assert '.word 0x5200f' in rows[0]['assembly']


@pytest.mark.parametrize('field,value',[('cbie',[2]),('cbie',[1,1]),('cbcfe',[3]),('cbcfe',[])])
def test_unsupported_or_duplicate_control_values(field,value):
    c=campaign.load('examples/privilege/envcfg-cbom.json');c['envcfg'][field]['machine']=value
    with pytest.raises(ValueError):campaign.scenarios(c)


def test_rv32_guest_entry_and_completion_transport():
    from rvw.privilege.extensions import access
    for name,count in [('envcfg-cbom-rv32',51),('envcfg-cbom-rv32-h',215)]:
        rows=campaign.scenarios(campaign.load('examples/privilege/'+name+'.json'))
        assert len(rows)==count and all(' sd ' not in r['assembly'] for r in rows)
        assert all(' sw t1, 0(t0)\n sw zero, 4(t0)' in r['assembly'] for r in rows)
        assert all('slli t0, t0, 39' not in r['assembly'] for r in rows)
        if name.endswith('-h'):
            guest=next(r for r in rows if r['id']=='envcfg-cbom-inval-vs-333')
            assert 'csrs 0x310' in guest['assembly']
    with pytest.raises(ValueError):access('M','','nop',xlen=16)

