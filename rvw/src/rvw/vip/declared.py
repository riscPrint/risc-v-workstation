"""Bench skeletons with an explicit plain HDL bus declaration."""
import json
from pathlib import Path
from rvw.common.hdl_ports import load


def skeleton(db, out, port_map, bus=None, uvm=False):
    spec=load(db,port_map)
    selected=[b for b in spec['buses'] if bus is None or b['name']==bus]
    if len(selected)!=1: raise ValueError('select exactly one declared bus')
    config=dict(declaration=spec,bus=selected[0])
    text='''"""Project-owned reset, stimulus and expected results are required."""
import cocotb
from rvw.sim.uvm import require_evidence
from rvw.vip.ready_valid import CocotbAgent
CONFIG = CONFIG_JSON

@cocotb.test()
async def declared_bus(dut):
    agent = CocotbAgent(dut, CONFIG['declaration'], CONFIG['bus'])
    task = cocotb.start_soon(agent.run_monitor())
    try:
        from scenario import run
        checks = await run(dut, agent)
        require_evidence(isinstance(checks, int) and checks > 0, 'scenario must check positive expected results')
        require_evidence(agent.monitor.transfers > 0, 'scenario must complete a transfer')
    finally:
        task.cancel()
'''.replace('CONFIG_JSON',repr(config))
    target=Path(out);target.parent.mkdir(parents=True,exist_ok=True)
    if uvm:
        text=text.replace('import cocotb\n','import cocotb\nimport pyuvm\n')
        text=text.replace('@cocotb.test()\nasync def declared_bus(dut):',
            'async def declared_bus(dut):')
        text+='''
@pyuvm.test()
class DeclaredBusTest(pyuvm.uvm_test):
    async def run_phase(self):
        self.raise_objection()
        try:
            await declared_bus(cocotb.top)
        finally:
            self.drop_objection()
'''
    with target.open('x') as f: f.write(text)
    return dict(status='skeleton',path=str(target),bus=selected[0],bindings=config,
                note='No DUT execution. Project reset, stimulus and expected results are required.')
