"""Native FCSR reset initialization."""
import pytest
from rvw.cosim.platform import Platform


@pytest.mark.slow
def test_native_seed_preserves_mstatus(elf):
    from model_fixtures import Spike
    model = Spike(Platform.load('boom'), elf)
    try:
        before = model.csr_snapshot(['0x300'])
        model.seed_fcsr(0xd9)
        assert model.csr_snapshot(['0x300']) == before
        effect = model.step()
        assert effect['fcsr'] == 0xd9 and effect['fflags'] == 0x19
    finally:
        model.close()
