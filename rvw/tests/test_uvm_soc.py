import asyncio
from pathlib import Path
import pytest
from rvw.uvm.soc import SocEnvironment
from rvw.vip import apb, axi, uart

MAP = Path(__file__).resolve().parents[2]/'Uvm/examples/soc/map.json'


class Frontdoor:
    def __init__(self): self.data = {}
    async def read(self, address, width): return self.data.get(address, 0)
    async def write(self, address, value, width): self.data[address] = value


def environment():
    return SocEnvironment(MAP, reference=None,
        protocols={'control':'apb','serial':'axi-lite'},
        frontdoors={'control':Frontdoor(), 'serial':Frontdoor()})


def test_composes_agents_and_ral():
    env = environment()
    assert isinstance(env.buses['control'], apb.Monitor)
    assert isinstance(env.buses['serial'], axi.Monitor)
    async def sequence():
        for name in ('control.data', 'serial.data'):
            await env.registers.write(name, 42)
            assert await env.registers.read(name, check=True) == 42
    asyncio.run(sequence())
    env.apb_transfer('control', apb.Transfer(0x10000000, True, 0x1234, 15))
    env.apb_transfer('control', apb.Transfer(0x10000000, response=0x1234))
    env.axi_transfer('serial', ('write', axi.Address(0x10001000), (axi.Write(55),), axi.Response()))
    env.axi_transfer('serial', ('read', axi.Address(0x10001000), (axi.Response(data=55),), axi.Response()))
    env.serial.expect(uart.Frame(65))
    for bit in uart.encode(uart.Frame(65)) + (1,)*16:
        env.uart.sample(bit)
    env.serial.finish()
    assert env.bus_checks == {'control':2,'serial':2}


def test_corruption_and_empty_cpu_cannot_pass():
    env = environment()
    with pytest.raises(AssertionError, match='SOC_REGISTER_DATA'):
        env.apb_transfer('control', apb.Transfer(0x10000000, response=1))
    with pytest.raises(AssertionError, match='missing CPU'):
        env.finish(1)
    with pytest.raises(AssertionError, match='SOC_REGISTER_ADDRESS'):
        env.transfer('control', 0x10001000, False, 0)
    with pytest.raises(AssertionError, match='SOC_AXI_PROFILE'):
        env.axi_transfer('serial', ('read', axi.Address(0x10001000), (axi.Response(),), axi.Response(response=2)))


def test_partial_trailing_uart_frame_cannot_pass():
    env = environment()
    env.cpu.checks = 1
    env.bus_checks = {'control':1,'serial':1}
    env.serial.expect(uart.Frame(65))
    for bit in uart.encode(uart.Frame(65))+(1,)*16:
        env.uart.sample(bit)
    # Begin another frame after the expected stream. A prefix cannot pass.
    env.uart.sample(0)
    with pytest.raises(AssertionError,match='SOC_PENDING_UART'):
        env.finish(1)
