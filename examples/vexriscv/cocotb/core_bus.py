"""Bounded simple-bus harness for the VexTop example. No implicit clock task."""
from cocotb.triggers import Timer

BASE = 0x80000000


class CoreBus:
    def __init__(self, dut, words):
        self.d = dut
        self.words = words
        self.pending = None
        self.retired = []
        self.traps = []
        self.stores = []
        self.cycle = 0
        dut.clk.value = 0
        dut.reset.value = 0
        for name in ('timerInterrupt', 'softwareInterrupt', 'externalInterrupt',
                     'externalInterruptS', 'iBus_cmd_ready', 'iBus_rsp_valid',
                     'iBus_rsp_payload_error', 'iBus_rsp_payload_inst',
                     'dBus_cmd_ready', 'dBus_rsp_ready', 'dBus_rsp_error', 'dBus_rsp_data'):
            getattr(dut, name).value = 0

    async def edge(self):
        self.d.clk.value = 0
        await Timer(5, unit='ns')
        self.d.clk.value = 1
        await Timer(5, unit='ns')
        self.d.clk.value = 0
        await Timer(1, unit='ns')
        self.cycle += 1

    async def step(self, fetch=True, data=True):
        d = self.d
        d.iBus_cmd_ready.value = int(fetch and self.pending is None)
        d.iBus_rsp_valid.value = int(self.pending is not None)
        if self.pending is not None:
            d.iBus_rsp_payload_inst.value = self.pending
        d.dBus_cmd_ready.value = int(data)
        await Timer(1, unit='ns')
        accepted = int(d.iBus_cmd_valid.value) and int(d.iBus_cmd_ready.value)
        pc = int(d.iBus_cmd_payload_pc.value) if accepted else None
        if int(d.dBus_cmd_valid.value) and data:
            address = int(d.dBus_cmd_payload_address.value)
            if int(d.dBus_cmd_payload_wr.value):
                self.stores.append((address, int(d.dBus_cmd_payload_data.value)))
            else:
                raise AssertionError('load response is deliberately stalled in this harness')
        self.pending = self.words.get(pc, 0x0000006f) if accepted else None
        await self.edge()
        if int(d.rvfi_valid.value):
            self.retired.append((int(d.rvfi_pc_rdata.value), int(d.rvfi_insn.value),
                                 int(d.rvfi_order.value)))
        if int(d.trap_valid.value):
            self.traps.append(int(d.trap_cause.value))

    async def until(self, predicate, limit=300, **kwargs):
        for _ in range(limit):
            if predicate():
                return
            await self.step(**kwargs)
        raise AssertionError('bounded core observation did not occur')

    async def pulse_reset(self):
        # System reset discards harness-owned bus responses. It is not a local reset.
        self.pending = None
        self.d.iBus_cmd_ready.value = 0
        self.d.iBus_rsp_valid.value = 0
        self.d.dBus_cmd_ready.value = 0
        self.d.dBus_rsp_ready.value = 0
        self.d.reset.value = 1
        for _ in range(4):
            await self.edge()
        self.retired.clear()
        self.traps.clear()
        self.stores.clear()
