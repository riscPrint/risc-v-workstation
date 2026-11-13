"""Real RTL checks with solver-derived data and observed functional counters."""
import json
from pathlib import Path
import cocotb
from cocotb.triggers import Timer
import pyuvm
from rvw.uvm.constraints import ConstraintSolver, FunctionalCoverage


@pyuvm.test()
class ConstrainedMemory(pyuvm.uvm_test):
    async def run_phase(self):
        self.raise_objection()
        try:
            dut = cocotb.top
            dut.clk.value = 0
            dut.write_enable.value = 0
            # Directed addresses ensure each declared bin is exercised.
            coverage = FunctionalCoverage({'write':[True,False], 'address':[0,1,2,3]})
            solver = ConstraintSolver({'address':(0,3),'data':(0,65535)},
                lambda v:[v['data'] % 4 == v['address']], seed=3)
            expected = {}
            items = [dict(address=i,data=0x100+i) for i in range(4)]
            items += [solver.sample() for _ in range(32)]
            for item in items:
                address, data = item['address'], item['data']
                assert data % 4 == address
                dut.address.value = address
                dut.write_data.value = data
                dut.write_enable.value = 1
                await Timer(1, unit='ns')
                dut.clk.value = 1
                await Timer(1, unit='ns')
                expected[address] = data
                assert int(dut.read_data.value) == expected[address]
                coverage.sample(dict(write=True,address=address))
                dut.clk.value = 0
                dut.write_enable.value = 0
                await Timer(1, unit='ns')
                assert int(dut.read_data.value) == expected[address]
                coverage.sample(dict(write=False,address=address))
            Path('functional.json').write_text(json.dumps(coverage.export(
                context=dict(bench='constrained_memory',seed=3,checks=len(items)*2)),indent=2)+'\n')
        finally:
            self.drop_objection()
