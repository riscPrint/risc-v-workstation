from rvw.privilege.pma import programs, observe


def test_boundary_probes():
    rows = programs({'pma':{'regions':[dict(name='dev',base=0x10000000,size=16,widths=[4],read=True,write=True,test_writes=True)]}})
    assert len(rows) == 16
    assert len({r['id'] for r in rows}) == 16
    assert all('pma_expectation' in r for r in rows)


def test_independent_capture():
    e=dict(address=8,width=4,write=True,count=1,state={'irq':1})
    c=dict(complete=True,transfers=[dict(address=8,width=4,write=True)],device_state={'irq':1})
    assert observe(e,c)['status']=='pass'
    c['device_state']['irq']=0
    assert observe(e,c)['status']=='fail'
    c['complete']=False
    assert observe(e,c)['status']=='inconclusive'
    assert observe(e,None)['status']=='inconclusive'
