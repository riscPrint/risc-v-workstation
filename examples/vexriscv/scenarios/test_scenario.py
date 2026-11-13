"""CPU-backed pyuvm checks on the real composed VexRiscv SoC."""
import json
from pathlib import Path

import cocotb
from cocotb.queue import Queue
from cocotb.triggers import RisingEdge, with_timeout
import pyuvm

from rvw.sim.bench import start
from scenario_sequence import ScenarioSequence


class CpuPort:
    def __init__(self, directory):
        self.directory = directory
        self.dut = cocotb.top
        self.queue = Queue()
        self.cycle = 0
        self.bases = json.loads((directory / 'probe-bases.json').read_text())
        self.starts = {}

    async def monitor(self):
        while True:
            await RisingEdge(self.dut.clk)
            self.cycle += 1
            if int(self.dut.reset.value):
                self.starts.clear()
                continue
            for name, base in self.bases.items():
                packed = int(getattr(self.dut, name + '_probe').value)
                fields = {}
                for field, width in [('error', 1), ('ready', 1), ('rdata', 32), ('wdata', 32),
                                     ('write', 1), ('enable', 1), ('select', 1)]:
                    fields[field] = packed & ((1 << width) - 1)
                    packed >>= width
                if fields['select'] and not fields['enable']:
                    self.starts[name] = self.cycle
                if fields['select'] and fields['enable'] and fields['ready']:
                    assert not fields['error'], 'APB response error'
                    self.queue.put_nowait(dict(address=base + packed, write=fields['write'],
                        value=fields['wdata'] if fields['write'] else fields['rdata'],
                        start=self.starts.pop(name, self.cycle), end=self.cycle + 1))

    async def start(self):
        self.dut.uart_serial_rxd.value = 1
        self.dut.plic_sources.value = 0
        cocotb.start_soon(self.monitor())
        await start(self.dut)

    async def observe(self, action):
        actual = await with_timeout(self.queue.get(), 100000, 'ns')
        assert actual['address'] == action['address'], action['id'] + ': address mismatch'
        assert actual['write'] == int(action['operation'] == 'write32'), action['id'] + ': direction mismatch'
        return actual

    async def finish(self):
        for _ in range(1000):
            await RisingEdge(self.dut.clk)
            if int(self.dut.finisher_done.value):
                assert int(self.dut.finisher_code.value) == 1, 'bare-metal self-check failed'
                return
        raise AssertionError('finisher timeout')


@pyuvm.test()
class ScenarioTest(pyuvm.uvm_test):
    async def run_phase(self):
        self.raise_objection()
        try:
            directory = Path(__file__).resolve().parent
            sequence = ScenarioSequence('cpu_scenario')
            sequence.port = CpuPort(directory)
            await sequence.start()
            assert sequence.records, 'no checked MMIO observations'
        finally:
            self.drop_objection()
