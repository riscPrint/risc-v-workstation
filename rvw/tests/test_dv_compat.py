"""Pinned upstream memory-stream corrections preserve emitted alignment."""
from types import SimpleNamespace
import pytest
from rvw.regress.dv_compat import corrected_load_store_source, constrain_offsets

pytestmark = pytest.mark.fast
SOURCE = '''def gen_load_store_instr(self):
    allowed_instr = []
    for i in range(len(self.addr)):
        allowed_instr.append('byte')
        if not cfg.enable_unaligned_load_store:
            if self.addr[i] % 4 == 0:
                allowed_instr.append('word')
            if (rcs.XLEN >= 64) and self.addr[i] % 8 == 0:
                allowed_instr.append('double')
            else:  # unalligned load/store
                allowed_instr.append('unaligned')
        instr = riscv_instr.get_load_store_instr(allowed_instr)
        self.instructions.append(instr)
'''


@pytest.mark.parametrize('xlen', [32, 64])
def test_alignment_and_allowed_opcodes_reset_per_access(xlen):
    namespace = dict(cfg=SimpleNamespace(enable_unaligned_load_store=False),
        rcs=SimpleNamespace(XLEN=xlen),
        riscv_instr=SimpleNamespace(get_load_store_instr=lambda allowed: list(allowed)))
    exec(corrected_load_store_source(SOURCE), namespace)
    stream=SimpleNamespace(addr=[0,1], instructions=[])
    namespace['gen_load_store_instr'](stream)
    assert stream.instructions == [['byte','word']+(['double'] if xlen==64 else []), ['byte']]
    namespace['cfg'].enable_unaligned_load_store=True
    stream.instructions=[]
    namespace['gen_load_store_instr'](stream)
    assert stream.instructions == [['byte','unaligned'], ['byte','unaligned']]


def test_alignment_uses_emitted_address_and_page_bounds():
    stream=SimpleNamespace(base=3, max_load_store_offset=32, offset=[-16,0,31], addr=[0,0,0])
    constrain_offsets(stream)
    assert stream.offset == [-3,0,21]
    assert stream.addr == [0,3,24]
    assert all(0 <= addr <= 24 for addr in stream.addr)


def test_upstream_change_requires_review():
    with pytest.raises(ValueError, match='review compatibility patch'):
        corrected_load_store_source(SOURCE.replace('allowed_instr = []', 'allowed_instr = list()'))
