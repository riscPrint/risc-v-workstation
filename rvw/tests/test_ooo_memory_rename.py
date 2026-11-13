from dataclasses import replace
import pytest
from rvw.ooo.core import Config, Instruction, simulate

pytestmark = pytest.mark.fast


def config(width=8):
    return Config(width, 64, width, 128, width, 64, 32, 32, width,
                  {'alu':1, 'divide':30, 'store':3, 'load':12}, physical_registers=256)


def sequence(address=0x1000):
    return [Instruction('divide', dest=1),
            Instruction('alu', dest=2),
            Instruction('store', (1,2), address=0x1000, size=8, mnemonic='sd'),
            Instruction('load', (0,), 3, address=address, size=8, mnemonic='ld'),
            *[Instruction('alu', (i,), i+1) for i in range(3,15)]]


@pytest.mark.parametrize('width', [8,10])
def test_rename_data_bypass_keeps_verification(width):
    c = config(width)
    ops = sequence()
    base = simulate(ops,c,backend='python')
    r = simulate(ops,replace(c,memory_rename={'mode':'oracle_store_data'}))
    assert r['events']['memory_renamed_loads'] == 1
    assert r['events']['issued'] == base['events']['issued']
    assert r['instret'] == len(ops)
    assert r['cycles'] < base['cycles']
    # Store address dependency still delays normal load verification and commit.
    assert r['cycles'] >= 30+3+12


def test_nonalias_and_partial_store_do_not_rename():
    c = replace(config(),memory_rename={'mode':'oracle_store_data'})
    for ops in [sequence(0x2000), sequence()[:3]+[
        Instruction('store',(0,2),address=0x1004,size=4,mnemonic='sw')]+sequence()[3:]]:
        r = simulate(ops,c)
        assert not r['events'].get('memory_renamed_loads')


def test_value_width_fence_and_zero_data():
    c = replace(config(),memory_rename={'mode':'oracle_store_data'})
    ops = sequence()
    ops[2] = replace(ops[2],sources=(1,0))
    r = simulate(ops,c)
    assert r['events']['memory_renamed_loads'] == 1
    ops[3] = replace(ops[3],mnemonic='lw',size=4)
    assert not simulate(ops,c)['events'].get('memory_renamed_loads')
    with pytest.raises(ValueError,match='replay'):
        replace(c,memory_policy='speculate')
    with pytest.raises(ValueError,match='address'):
        simulate([Instruction('load')],c)
