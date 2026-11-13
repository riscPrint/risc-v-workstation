import cocotb
from cocotb.triggers import Timer
import pyuvm
from rvw_env import BaseEnvironment
from rvw.sim.uvm_models import Transaction


@pyuvm.test()
class BaseParity(pyuvm.uvm_test):
    def build_phase(self):
        self.env = BaseEnvironment('env', self)

    async def run_phase(self):
        self.raise_objection()
        dut = cocotb.top
        dut.clk.value = 0
        dut.write_enable.value = 0
        for i in range(4):
            dut.address.value = i
            dut.write_enable.value = 1
            dut.write_data.value = 0x100 + i
            await Timer(1,unit='ns')
            dut.clk.value = 1
            await Timer(1,unit='ns')
            self.env.scoreboard.expect(Transaction(True,i*4,0x100+i))
            self.env.scoreboard.observe(Transaction(True,i*4,int(dut.read_data.value)))
            dut.clk.value = 0
        dut.write_enable.value = 0
        for i in range(4):
            dut.address.value = i
            await Timer(1,unit='ns')
            self.env.scoreboard.expect(Transaction(False,i*4,0x100+i))
            self.env.scoreboard.observe(Transaction(False,i*4,int(dut.read_data.value)))
        assert len(self.env.scoreboard.model.hit_bins) == 8
        self.drop_objection()
