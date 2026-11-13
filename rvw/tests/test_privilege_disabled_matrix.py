import pytest
from rvw.privilege.disabled_matrix import programs


@pytest.mark.parametrize('feature,isa,priv,count',[
    ('fs-off','rv64imf_zicsr','msu',192),('vs-off','rv64imafdv_zicsr','msu',192),
    ('no-float','rv64im_zicsr','msu',192),('no-vector','rv64im_zicsr','msu',192),
    ('no-supervisor','rv64im_zicsr','mu',384)])
def test_complete_masks(feature,isa,priv,count):
    rows=programs(dict(isa=isa,priv=priv,disabled={'feature':feature}))
    assert len(rows)==count and len({r['id'] for r in rows})==count
    assert len({r['requested_controls'] for r in rows})==64
    assert all(len(r['bins'])==7 for r in rows)
    assert all('bne t0, s3, fail' in r['assembly'] for r in rows)


def test_no_floating_contradiction():
    with pytest.raises(ValueError):programs(dict(isa='rv64imf',disabled={'feature':'no-float'}))


def test_g_abbreviation_and_absent_mode():
    assert len(programs(dict(isa='rv64g',disabled={'feature':'fs-off'})))==192
    with pytest.raises(ValueError):programs(dict(priv='mu',modes=['S'],disabled={'feature':'no-supervisor'}))
