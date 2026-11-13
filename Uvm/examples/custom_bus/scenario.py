"""Project-owned pin binding and checked APB4 traffic."""
import json
import os
from pathlib import Path
from types import SimpleNamespace
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge


async def run(services):
    dut = services.dut
    module = services.agent_module
    pins = SimpleNamespace(**{name: getattr(dut, port) for name, port in
                              services.config['project_adapter']['bindings'].items()})
    dut.corrupt.value = int(os.environ.get('CUSTOM_BUS_CORRUPT', '0'))
    for name in ('psel', 'penable', 'pwrite', 'paddr', 'pwdata', 'pstrb', 'pprot', 'reset_n'):
        getattr(pins, name).value = 0
    clock = cocotb.start_soon(Clock(pins.clk, 10, unit='ns').start())
    for _ in range(3):
        await RisingEdge(pins.clk)
    await FallingEdge(pins.clk)
    pins.reset_n.value = 1
    scoreboard = module.RegisterScoreboard()
    agent = module.CocotbAgent(pins)
    transfers = 0
    try:
        for transfer in module.sequences(seed=17, count=16):
            result = await agent.transfer(transfer)
            scoreboard(result)
            services.checked(not result.aborted, 'CUSTOM_BUS_ABORT')
            transfers += 1
        services.checked(scoreboard.count == transfers, 'CUSTOM_BUS_MISSING_CHECKS')
        Path('custom-checks.json').write_text(json.dumps(dict(
            transfers=transfers, checks=services.checks, seed=17,
            scope='custom pins with APB4 semantics')) + '\n')
    finally:
        clock.cancel()
