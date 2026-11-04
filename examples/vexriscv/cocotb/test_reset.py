"""Real synchronous reset pulses on the same native VexRiscv instance."""
import cocotb
from rvw.cosim.reset import ResetContract, ResetSample, check_reset
from core_bus import BASE, CoreBus

# Hand-encoded RV32I stimulus: initialize mtvec, issue a load, then ECALL.
# A reset during the stalled load must discard the old pipeline transaction.
WORDS = {
    BASE: 0x800000b7,       # lui x1, 0x80000
    BASE + 4: 0x04008093,   # addi x1, x1, 64
    BASE + 8: 0x30509073,   # csrw mtvec, x1
    BASE + 12: 0x0000a103,  # lw x2, 0(x1)
    BASE + 16: 0x00000073,  # ecall
    BASE + 64: 0x0000006f,  # j .
}
CONTRACT = ResetContract({'privilege': (3, 3), 'status': (0x1800, 0x1888)},
                         ('retirement', 'trap'))


def sample(b, asserted):
    d = b.d
    return ResetSample(b.cycle, asserted,
        {'privilege': int(d.observed_privilege.value), 'status': int(d.observed_status.value)},
        {'retirement': bool(int(d.rvfi_valid.value)), 'trap': bool(int(d.trap_valid.value))})


async def reset_and_check(b):
    await b.pulse_reset()
    asserted = sample(b, True)
    b.d.reset.value = 0
    # No functional transfer is accepted before the release sample.
    await b.edge()
    released = sample(b, False)
    result = check_reset(CONTRACT, [asserted, released])
    assert result['status'] == 'consistent', result
    await b.until(lambda: bool(int(b.d.iBus_cmd_valid.value)), fetch=False)
    assert int(b.d.iBus_cmd_payload_pc.value) == BASE
    assert not b.retired


@cocotb.test()
async def cold_warm_repeated_bus_and_trap_reset(dut):
    b = CoreBus(dut, WORDS.copy())
    await reset_and_check(b)  # actual cold reset, not initial register values
    for _ in range(3):
        # A fetch request is held across reset.
        await b.until(lambda: bool(int(dut.iBus_cmd_valid.value)), fetch=False)
        await reset_and_check(b)
        # A data request is held across warm system reset.
        await b.until(lambda: bool(int(dut.dBus_cmd_valid.value)), data=False)
        assert int(dut.dBus_cmd_payload_address.value) == BASE + 64
        await reset_and_check(b)
        # Replace the load with NOP so ECALL enters the real CSR trap path.
        b.words[BASE + 12] = 0x00000013
        await b.until(lambda: bool(b.traps))
        assert b.traps[-1] == 11
        await reset_and_check(b)
        b.words[BASE + 12] = WORDS[BASE + 12]
