import pytest
from rvw.cosim.translation import walk, observations


def test_nested_nonidentity():
    # VS root GPA 0x10000 maps through G to HPA 0x40010000.
    # VS VA 0 maps to GPA 0x80000000; G maps that to HPA 0xc0000000.
    hgatp = (8 << 60) | 4
    vsatp = (8 << 60) | 0x10
    mem = {0x4000: (0x40000 << 10)|0xdf,
           0x4010: (0xc0000 << 10)|0xdf,
           0x40010000: (0x80000 << 10)|0xcf}
    effect = dict(pc=0x120, trap=False, mem_rmask=0, mem_wmask=0)
    assert observations(effect, (True, vsatp, hgatp), mem.__getitem__) == [
        dict(access='fetch', va=0x120, gpa=0x80000120, pa=0xc0000120)]


@pytest.mark.parametrize('root,addr,pte', [(9<<60, 0, 0), (8<<60|1, 0, 0),
    (8<<60, 1<<41, 0), (8<<60,0,0), (8<<60,0,5), (8<<60,0,(1<<63)|0xf),
    (8<<60,0,(1<<10)|0xf)])
def test_unsupported_walk_refused(root, addr, pte):
    with pytest.raises(ValueError):
        walk(addr, root, lambda _: pte, guest=True)


def test_fault_observation_refused():
    with pytest.raises(ValueError, match='faulting'):
        observations(dict(trap=True), (True, 0, 0), lambda _: 0)
