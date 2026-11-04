"""Project APB3 binding. Reference state comes only from stimulus."""
from cocotb.triggers import Timer
from rvw.cosim.devices import Plic, PlicMap


class PlicBus:
    def __init__(self, dut):
        self.dut = dut
        self.model = Plic(PlicMap(0, 0x1000, 0x2000, 128, 0x200000, 4096, 3, 2))
        self.levels = 0
        dut.clk.value = 0
        dut.reset.value = 0
        dut.io_sources.value = 0
        dut.io_bus_PSEL.value = 0
        dut.io_bus_PENABLE.value = 0
        dut.io_bus_PWRITE.value = 0
        dut.io_bus_PADDR.value = 0
        dut.io_bus_PWDATA.value = 0

    async def tick(self, count=1):
        for _ in range(count):
            self.dut.clk.value = 0
            await Timer(5, unit='ns')
            self.dut.clk.value = 1
            await Timer(5, unit='ns')
        self.dut.clk.value = 0
        await Timer(1, unit='ns')

    async def reset(self):
        self.dut.reset.value = 1
        await self.tick(3)
        self.dut.reset.value = 0
        self.model.reset()
        self.levels = 0
        self.dut.io_sources.value = 0
        await self.tick(4)

    async def access(self, address, value=None, levels=None):
        d = self.dut
        d.io_bus_PADDR.value = address
        d.io_bus_PWRITE.value = int(value is not None)
        d.io_bus_PWDATA.value = value or 0
        d.io_bus_PSEL.value = 1
        await self.tick()
        d.io_bus_PENABLE.value = 1
        # Drive a source edge during the APB access, independently of DUT data.
        if levels is not None:
            self.sources(levels)
        for _ in range(16):
            await Timer(1, unit='ns')
            if int(d.io_bus_PREADY.value):
                observed = int(d.io_bus_PRDATA.value) if value is None else None
                await self.tick()
                break
            await self.tick()
        else:
            raise AssertionError('APB response exceeded 16 cycles')
        d.io_bus_PSEL.value = 0
        d.io_bus_PENABLE.value = 0
        if value is None:
            expected = self.model.read(address)
            assert observed == expected, (hex(address), observed, expected)
        else:
            self.model.write(address, value)
        await self.tick(4)  # library arbitration is registered
        self.check_irq()
        return observed

    def sources(self, levels):
        for source in range(1, 4):
            if (levels ^ self.levels) & (1 << (source - 1)):
                self.model.set_level(source, bool(levels & (1 << (source - 1))))
        self.levels = levels
        self.dut.io_sources.value = levels

    def check_irq(self):
        expected = sum(int(self.model.irq(i)) << i for i in range(2))
        assert int(self.dut.io_irq.value) == expected
