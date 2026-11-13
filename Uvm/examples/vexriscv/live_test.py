"""Project-owned VexRiscv simple-bus binding for the shared CPU environment."""
import json
import os
from pathlib import Path

import cocotb
from cocotb.triggers import Timer
import pyuvm
from cpu_env import LiveCpuEnvironment
from rvw.common.capture import Capture
from rvw.cosim.elf import Elf
from rvw.cosim.platform import Platform
from rvw.cosim.spike import Spike, capture_shim

HERE = Path(__file__).resolve().parent


class VexEnvironment(LiveCpuEnvironment):
    async def run_phase(self):
        d = self.config['dut']
        bindings = self.config['bindings']
        for pin in bindings['zero_inputs']:
            getattr(d, pin).value = 0
        d.clk.value = 0
        d.reset.value = 1
        async def edge():
            d.clk.value = 0
            await Timer(5, unit='ns')
            d.clk.value = 1
            await Timer(5, unit='ns')
            d.clk.value = 0
            await Timer(1, unit='ns')
        for _ in range(5):
            await edge()
        d.reset.value = 0
        fetch, load = None, None
        for cycle in range(self.config['max_cycles']):
            # Each port allows one pending response. Both ports share CpuMemory.
            d.iBus_cmd_ready.value = int(fetch is None)
            d.iBus_rsp_valid.value = int(fetch is not None and fetch[0] <= cycle)
            if fetch is not None:
                d.iBus_rsp_payload_inst.value = fetch[1].data
                d.iBus_rsp_payload_error.value = int(fetch[1].error)
            d.dBus_cmd_ready.value = int(load is None)
            d.dBus_rsp_ready.value = int(load is not None and load[0] <= cycle)
            if load is not None:
                d.dBus_rsp_data.value = load[1].data
                d.dBus_rsp_error.value = int(load[1].error)
            await Timer(1, unit='ns')
            fetch_address = (int(d.iBus_cmd_payload_pc.value)
                             if int(d.iBus_cmd_valid.value) and int(d.iBus_cmd_ready.value) else None)
            transfer = None
            if int(d.dBus_cmd_valid.value) and int(d.dBus_cmd_ready.value):
                transfer = (int(d.dBus_cmd_payload_address.value) & ~3,
                            bool(d.dBus_cmd_payload_wr.value),
                            int(d.dBus_cmd_payload_data.value), int(d.dBus_cmd_payload_mask.value))
            fetch_done = int(d.iBus_rsp_valid.value)
            load_done = int(d.dBus_rsp_ready.value)
            await edge()
            if fetch_done:
                fetch = None
            if load_done:
                load = None
            if fetch_address is not None:
                reply = self.memory.access(fetch_address, instruction=True)
                fetch = (cycle + 1 + reply.wait_cycles, reply)
            if transfer is not None:
                address, write, data, mask = transfer
                reply = self.memory.access(address, write=write, data=data, mask=mask)
                assert not reply.error, 'data access outside project RAM'
                if not write:
                    load = (cycle + 1 + reply.wait_cycles, reply)
            if int(d.rvfi_valid.value):
                record = {name: int(getattr(d, pin).value) for name, pin in bindings['fields'].items()}
                record['mem_fault'] = 0  # This profile serves RAM without data faults.
                if os.environ.get('RVW_VEX_CORRUPT') == '1' and self.scoreboard.checks == 5:
                    record['pc_next'] ^= 4
                self.scoreboard.observe(record)
                if record['mem_wmask'] and (record['mem_addr'] & ~3) == self.config['tohost']:
                    assert record['mem_wmask'] == 15 and record['mem_wdata'] == 1, 'ISA program failed'
                    self.scoreboard.finish(self.scoreboard.checks)
                    self.done = True
                    Path('cpu-checks.json').write_text(json.dumps({
                        'checks': self.scoreboard.checks, 'cycles': cycle + 1,
                        'coverage': self.scoreboard.coverage.report(),
                        'memory_transfers': self.memory.transfers}, indent=2)+'\n')
                    return
        raise AssertionError('CPU retirement watchdog expired before tohost pass')

    def check_phase(self):
        assert self.done and self.scoreboard.checks > 0, 'CPU program did not finish'


@pyuvm.test()
class VexIsa(pyuvm.uvm_test):
    def build_phase(self):
        elf_path = Path(os.environ['RVW_CPU_ELF']).resolve()
        elf = Elf(elf_path)
        platform = Platform.load(None, HERE.parents[2]/'examples/vexriscv/rvw/platform.json')
        self.capture = Capture(Path('spike-capture'))
        shim = capture_shim(self.capture, Path(os.environ['RVW_CPU_SHIM']))
        self.reference = Spike(platform, elf_path, shim=shim)
        bindings = json.loads((HERE/'bindings.json').read_text())
        cfg = dict(dut=cocotb.top, bindings=bindings, reference=self.reference,
                   elf=elf, memory_base=0x80000000, memory_size=0x1000000,
                   seed=int(os.environ.get('RVW_VEX_SEED', '1')), max_wait=3,
                   max_cycles=200000, retirements=1, tohost=elf.symbols['tohost'])
        pyuvm.ConfigDB().set(self, 'env', 'cpu', cfg)
        self.env = VexEnvironment('env', self)

    async def run_phase(self):
        self.raise_objection()
        try:
            for _ in range(300000):
                await Timer(10, unit='ns')
                if self.env.done:
                    return
            raise AssertionError('environment watchdog expired')
        finally:
            self.drop_objection()
            self.reference.close()
