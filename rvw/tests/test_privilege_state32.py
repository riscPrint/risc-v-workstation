import pytest
from rvw.privilege import campaign,state32

pytestmark=pytest.mark.fast


def test_split_banks_and_privilege_matrix():
    for name,count in [('stateen-rv32',48),('stateen-rv32-h',160)]:
        config=campaign.load('examples/privilege/'+name+'.json');rows=campaign.scenarios(config)
        assert len(rows)==count and len({r['id'] for r in rows})==count
        assert all(' sd ' not in r['assembly'] and 'slli t0, t0, 39' not in r['assembly'] for r in rows)
        denied=next(r for r in rows if r['id']=='stateen32-stateen-3-s-000')
        assert 'csrw 0x31f' in denied['assembly'] and 'li t1, 2' in denied['assembly']
        if name.endswith('-h'):
            guest=next(r for r in rows if r['id']=='stateen32-envcfg-0-vs-100')
            assert 'csrw 0x61c' in guest['assembly'] and 'csrs 0x310' in guest['assembly'] and 'li t1, 22' in guest['assembly']
            machine_denied=next(r for r in rows if r['id']=='stateen32-envcfg-0-vs-010')
            assert 'li t1, 2' in machine_denied['assembly']


def test_split_encoding_retains_both_halves():
    text=state32.write_bank(0x30c,2,0xfedcba9876543210)
    assert 'li t0, 1985229328\n csrw 0x30e' in text
    assert 'li t0, 4275878552\n csrw 0x31e' in text


@pytest.mark.parametrize('field,value', [('writable_bits',[63]),('probes',[]),('probes',['stateen','stateen'])])
def test_invalid_gate_contract(field,value):
    c=campaign.load('examples/privilege/stateen-rv32.json');c['stateen'][field]=value
    with pytest.raises(ValueError):campaign.scenarios(c)
