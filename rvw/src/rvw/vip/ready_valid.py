"""Project-bound ready/valid stability monitor. No transaction model is inferred."""
class Monitor:
    def __init__(self):
        self.stalled = False
        self.previous = None
        self.transfers = 0

    def sample(self, valid, ready, payload, reset=False):
        if reset:
            self.stalled = False
            self.previous = None
            return
        if self.stalled and (not valid or payload != self.previous):
            raise AssertionError('ready_valid: source changed a stalled request')
        self.stalled = bool(valid and not ready)
        self.previous = payload
        self.transfers += bool(valid and ready)


class CocotbAgent:
    def __init__(self, dut, declaration, bus):
        self.dut, self.declaration, self.bus = dut, declaration, bus
        self.monitor = Monitor()

    def sample(self):
        value = lambda name: int(getattr(self.dut, name).value)
        pins = self.bus['ports']
        self.monitor.sample(value(pins['valid']), value(pins['ready']),
                            tuple(value(p) for p in pins['payload']),
                            value(self.declaration['reset']['signal']) == self.declaration['reset']['active'])

    async def run_monitor(self):
        from cocotb.triggers import RisingEdge, ReadOnly
        while True:
            await RisingEdge(getattr(self.dut, self.declaration['clock']))
            await ReadOnly()
            self.sample()
