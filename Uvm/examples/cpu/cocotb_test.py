"""Live cocotb CPU path. ELF and matched shim come from explicit environment."""
import os
from pathlib import Path
import tempfile
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, Timer, ReadOnly
from rvw.common.capture import Capture
from rvw.cosim.elf import Elf
from rvw.cosim.platform import Platform
from rvw.cosim.spike import capture_shim, Spike
from rvw.sim.cpu_env import CpuMemory, CpuScoreboard


@cocotb.test()
async def live_addi(dut):
    elf = Elf(Path(os.environ['RVW_CPU_ELF']))
    platform = Platform.load(None, Path(os.environ['RVW_CPU_PLATFORM']))
    with tempfile.TemporaryDirectory() as temporary:
        capture = Capture(Path(temporary)/'capture')
        shim = capture_shim(capture, Path(os.environ['RVW_CPU_SHIM']))
        reference = Spike(platform, Path(os.environ['RVW_CPU_ELF']), shim=shim)
        try:
            sc = CpuScoreboard(reference)
            mem = CpuMemory(0x80000000,4096,seed=3)
            mem.preload(elf)
            dut.reset_n.value = 0; dut.grant.value = 0; dut.instruction.value = 0
            cocotb.start_soon(Clock(dut.clk,10,unit='ns').start())
            for _ in range(5): await FallingEdge(dut.clk)
            dut.reset_n.value = 1
            fields = 'pc pc_next insn mode rd rd_wdata mem_addr mem_rmask mem_wmask mem_rdata mem_wdata trap mem_fault rs1 rs1_rdata rs2 rs2_rdata intr halt'.split()
            async def memory_agent():
                while True:
                    await FallingEdge(dut.clk)
                    if int(dut.request.value):
                        reply = mem.access(int(dut.address.value),instruction=True)
                        assert not reply.error
                        for _ in range(reply.wait_cycles): await FallingEdge(dut.clk)
                        dut.instruction.value = reply.data; dut.grant.value = 1
                        await FallingEdge(dut.clk)
                        dut.grant.value = 0
            agent = cocotb.start_soon(memory_agent())
            try:
                for _ in range(100):
                    await FallingEdge(dut.clk); await ReadOnly()
                    if int(dut.valid.value):
                        record = dict(zip(fields,(int(dut.values[i].value) for i in range(19))))
                        record['order'] = int(dut.order.value)
                        record['gpr_state'] = [int(dut.core.registers[i].value) for i in range(32)]
                        record['csr_state'] = {'0x301':int(dut.core.misa_value.value)}
                        sc.observe(record)
                        if sc.checks == 6: break
                sc.finish(6)
            finally:
                agent.cancel()
        finally:
            reference.close()
