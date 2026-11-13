"""Counter overflow must retain all flow information needed by the decoder."""
import pytest
from rvw.debug import ntrace
from rvw.debug.hart import Asm

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('taken', [False, True])
@pytest.mark.parametrize('mode', ['htm', 'btm'])
def test_branch_on_instruction_counter_overflow_round_trips(mode, taken):
    p = ntrace.normalize({'icnt_bits': 2, 'mode': mode})
    branch = Asm.bne(1, 0, 8)
    rows = [dict(pc=0x1000, pc_next=0x1004, insn=Asm.NOP, mode=3),
            dict(pc=0x1004, pc_next=0x100c if taken else 0x1008, insn=branch, mode=3),
            dict(pc=0x100c if taken else 0x1008, pc_next=0x1010 if taken else 0x100c,
                 insn=Asm.NOP, mode=3)]
    messages = ntrace.encode(rows, p)
    messages, rest = ntrace.unpack(ntrace.pack(messages, p), p)
    assert rest == 0
    code = ntrace.Code([(0x1000, Asm.words(Asm.NOP, branch, Asm.NOP, Asm.NOP))])
    segments = ntrace.decode(messages, code, p)
    assert segments == [([r['pc'] for r in rows], True, 'trace stop')]
