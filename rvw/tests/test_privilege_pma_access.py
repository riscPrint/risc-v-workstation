import pytest
from rvw.privilege import campaign
from rvw.privilege.pma import observe,programs as regions
from rvw.privilege.pma_access import programs
from rvw.privilege.pmp import program

pytestmark=pytest.mark.fast


def test_crossing_transfer_sequence_includes_other_addresses():
    e=dict(address=4,width=8,write=False,transfers=[dict(address=4,width=4,write=False),dict(address=8,width=4,write=False)],state={'reads':2})
    c=dict(complete=True,transfers=list(e['transfers']),device_state={'reads':2})
    assert observe(e,c)['status']=='pass'
    c['transfers'].append(dict(address=12,width=4,write=False))
    assert observe(e,c)['status']=='fail'
    c['transfers']=list(reversed(e['transfers']))
    assert observe(e,c)['status']=='fail'
    e['transfers']=[];c['transfers']=[]
    assert observe(e,c)['status']=='pass'


def test_scalar_and_atomic_project_profiles():
    c=campaign.load('examples/privilege/pma-spike-access.json');rows=campaign.scenarios(c)
    assert len(rows)==14 and all('reference_unavailable' not in r for r in rows)
    assert all('pma_probe_end:' in r['assembly'] for r in rows)
    assert any('amoadd.w a2' in r['assembly'] and 'bne a3, t0, fail' in r['assembly'] for r in rows)
    other=campaign.scenarios(campaign.load('examples/privilege/pma-crossing.json'))
    assert len(other)==2 and all('reference_unavailable' in r for r in other)
    c['pma']['probes'][1]['test_writes']=False
    with pytest.raises(ValueError,match='test_writes'):programs(c)


def test_four_byte_mmio_region():
    rows=regions({'pma':{'regions':[dict(name='msip',base=0x2000000,size=4,widths=[4],read=True,write=False)]}})
    assert len(rows)==6 and all(r['pma_expectation']['width']<=4 for r in rows)


def test_fallback_tor_lower_bound_is_initialized():
    for addressing in ('tor','na4','napot'):
        code=program(addressing,'S',False,7,'read')
        low=code.index('csrw pmpaddr6, zero');high=code.index('csrw pmpaddr7, t0')
        assert low<high<code.index('csrw pmpcfg0, t0',high)


def test_pmp_granularity_selects_supported_address_modes():
    from rvw.privilege.pmp import programs as pmp
    rows=pmp({'pmp':{'entries':8,'granularity_bytes':64}})
    assert len(rows)==264 and not any('-na4-' in r['id'] for r in rows)
    tor=next(r['assembly'] for r in rows if r['id']=='pmp-tor-s-0-7-read')
    assert 'addi t0, t0, 16' in tor and '.balign 64' in tor
    napot=next(r['assembly'] for r in rows if r['id']=='pmp-napot-s-0-7-read')
    assert 'ori t0, t0, 7' in napot
    with pytest.raises(ValueError):pmp({'pmp':{'granularity_bytes':64,'address_modes':['na4']}})
    with pytest.raises(ValueError):pmp({'pmp':{'entries':4}})
