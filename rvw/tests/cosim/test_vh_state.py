import copy
import pytest
from rvw.cosim.extensions import header_fields, state_fields, compare_extensions, H_CSRS


def header():
    return dict(schema='rvw.rvfi/2', xlen=64, isa='rv64imafdcvh_zicsr',
                vector=dict(vlen=128, elen=64), hypervisor=True)


def state():
    return dict(mode=3, vector=dict(vstart='0x0', vl='0x4', vtype='0x10',
                vcsr='0x0', vs='0x3', regs=['0x0']*32),
                hypervisor=dict(virtual=False, mode_after=3, virtual_after=False,
                csrs={hex(a): '0x0' for a in H_CSRS}, translations=[]))


@pytest.mark.parametrize('field', ['vl', 'vtype', 'vstart', 'vcsr', 'vs', 'regs'])
def test_vector_mutations(field):
    h, a = header(), state()
    state_fields(a, h)
    e = copy.deepcopy(a)
    if field == 'regs':
        a['vector'][field][0] = 1  # mask mutation
    else:
        a['vector'][field] ^= 1
    assert 'vector.'+field in compare_extensions(a, e, h)


@pytest.mark.parametrize('field', ['virtual', 'mode_after', 'virtual_after', 'csrs'])
def test_h_mutations(field):
    h, a = header(), state()
    state_fields(a, h)
    e = copy.deepcopy(a)
    if field == 'csrs':
        a['hypervisor'][field]['0x643'] = 1
    else:
        a['hypervisor'][field] = 1
    assert 'hypervisor.'+field in compare_extensions(a, e, h)


@pytest.mark.parametrize('field', ['vector', 'hypervisor'])
def test_partial_state(field):
    a = state()
    del a[field]
    with pytest.raises(ValueError):
        state_fields(a, header())
    h = header()
    del h[field]
    with pytest.raises(ValueError):
        header_fields(h)


@pytest.mark.parametrize('vlen,elen', [(127,64), (128,128), (64,64), (128,0), (True,64)])
def test_bad_dimensions(vlen, elen):
    h = header()
    h['vector'] = dict(vlen=vlen, elen=elen)
    with pytest.raises(ValueError):
        header_fields(h)


def test_reference_missing_state():
    with pytest.raises(ValueError, match='reference cannot check'):
        compare_extensions(state(), {}, header())
