import random
import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def napot_region(dut):
    # cutoff=2. PMP address stores physical address >> 2.
    # N trailing one bits select a region of 2**(N+3) bytes.
    # Check independent aligned region base and compare mask formulas.
    width_mask = (1 << 30) - 1
    for n in range(29):
        for _ in range(8):
            aligned = random.getrandbits(30) & ~((1 << (n + 1)) - 1)
            encoded = aligned | ((1 << n) - 1)
            dut.io_addr.value = encoded
            await Timer(2, unit='ns')
            assert int(dut.io_base.value) == aligned
            assert int(dut.io_mask.value) == (width_mask & ~((1 << (n + 1)) - 1))
