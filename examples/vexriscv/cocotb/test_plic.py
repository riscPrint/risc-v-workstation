"""Native upstream PLIC checks. These do not qualify a CPU/PLIC integration."""
import cocotb
from plic_bus import PlicBus


@cocotb.test()
async def arbitration_and_context_interleavings(dut):
    b = PlicBus(dut)
    await b.reset()
    for source in range(1, 4):
        await b.access(source * 4, 3)
    for context in range(2):
        await b.access(0x2000 + context * 128, 14)
    # Two sources rise together while a context enable write is in flight.
    await b.access(0x2080, 14, levels=3)
    assert await b.access(0x200004) == 1
    assert await b.access(0x201004) == 2
    assert await b.access(0x200004) == 0
    # A level gateway cannot re-pend until completion.
    await b.access(0x200004, 1, levels=2)
    assert await b.access(0x201004) == 0
    await b.access(0x201004, 2)
    assert await b.access(0x200004) == 2
    await b.access(0x200004, 2, levels=4)
    await b.access(12, 7)
    await b.access(0x201000, 6)
    assert await b.access(0x201004) == 3
    await b.access(0x201004, 3, levels=0)
    assert await b.access(0x200004) == 0


@cocotb.test()
async def claim_must_ignore_threshold(dut):
    # Known upstream divergence: PlicTarget gates claim with iep.
    # Keep the independent reference rule. Do not copy the RTL's claim value.
    b = PlicBus(dut)
    await b.reset()
    await b.access(4, 3)
    await b.access(0x2000, 2)
    await b.access(0x200000, 3, levels=1)
    assert int(dut.io_irq.value) == 0
    await b.access(0x200004)  # reference requires 1, library returns 0
