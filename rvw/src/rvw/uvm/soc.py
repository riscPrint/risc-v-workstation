"""Map-owned composition of existing CPU, APB, AXI and UART services.

Projects own wire bindings and active drivers. No design is inferred from a map.
"""
from rvw.soc.model import load
from rvw.sim.cpu_env import CpuScoreboard
from rvw.sim.uvm_models import RegisterModel
from rvw.vip import apb, axi, uart


class RoutedFrontdoor:
    def __init__(self, regions, adapters):
        self.regions, self.adapters = regions, adapters

    def select(self, address, width):
        for region in self.regions:
            if region['base'] <= address and address + width // 8 <= region['base'] + region['size']:
                return self.adapters[region['name']]
        raise ValueError('register address has no project frontdoor')

    async def read(self, address, width):
        return await self.select(address, width).read(address, width)

    async def write(self, address, value, width):
        await self.select(address, width).write(address, value, width)


class SocEnvironment:
    """Compose monitors and RAL for known-reset 32-bit RW register windows.

    APB4 and AXI4-Lite monitors check completed bus transfers. UART checks an
    independently supplied expected stream. CPU uses independent Spike steps.
    Projects must sample each monitor at the protocol's specified edge.
    """
    def __init__(self, map_path, *, reference, protocols, frontdoors, uart_config=None, cpu_required=True):
        self.map = load(map_path)
        regions = [r for r in self.map['regions'] if r['kind'] == 'mmio']
        names = {r['name'] for r in regions}
        if not names or set(protocols) != names or set(frontdoors) != names:
            raise ValueError('declare a protocol and frontdoor for every MMIO region')
        self.expected, self.register_info, self.bus_checks = {}, {}, dict.fromkeys(names, 0)
        for region in regions:
            for reg in region['registers']:
                if (reg['width'] != 32 or reg['access'] != 'rw' or reg['reset'] is None
                        or reg['read_action'] != 'none' or reg['write_action'] != 'normal'):
                    raise ValueError('SoC monitor requires known-reset 32-bit plain RW registers')
                address = region['base'] + reg['offset']
                self.expected[address] = reg['reset']
                self.register_info[address] = region['name']
        self.registers = RegisterModel(map_path, RoutedFrontdoor(regions, frontdoors))
        self.cpu_required = cpu_required
        self.cpu = CpuScoreboard(reference) if cpu_required else None
        self.serial = uart.Scoreboard()
        self.uart = uart.Monitor(self.serial.observe, uart_config or uart.Config())
        self.buses = {}
        for name, protocol in protocols.items():
            if protocol == 'apb':
                self.buses[name] = apb.Monitor(lambda t, n=name: self.apb_transfer(n, t))
            elif protocol == 'axi-lite':
                self.buses[name] = axi.Monitor(lambda t, n=name: self.axi_transfer(n, t), lite=True)
            else:
                raise ValueError('SoC composition supports apb and axi-lite')

    def transfer(self, region, address, write, data, mask=15):
        if self.register_info.get(address) != region:
            raise AssertionError('SOC_REGISTER_ADDRESS')
        if write:
            lanes = sum(255 << (i*8) for i in range(4) if mask & (1 << i))
            self.expected[address] = (self.expected[address] & ~lanes) | (data & lanes)
        elif data != self.expected[address]:
            raise AssertionError('SOC_REGISTER_DATA')
        self.bus_checks[region] += 1

    def apb_transfer(self, region, t):
        if t.aborted:
            raise AssertionError('SOC_APB_ABORT')
        if t.error:
            raise AssertionError('SOC_APB_ERROR')
        self.transfer(region, t.address, t.write, t.data if t.write else t.response, t.strobe)

    def axi_transfer(self, region, event):
        kind, address, beats, response = event
        if address.length or address.size != 2 or response.response or len(beats) != 1:
            raise AssertionError('SOC_AXI_PROFILE')
        write = kind == 'write'
        beat = beats[0]
        self.transfer(region, address.address, write, beat.data, beat.strobe if write else 15)

    def finish(self, retirements):
        if self.cpu_required:
            self.cpu.finish(retirements)
        elif retirements != 0:
            raise ValueError('bus-master profile has no CPU retirements')
        self.serial.finish()
        if self.uart.state != 'idle':
            raise AssertionError('SOC_PENDING_UART')
        for name, monitor in self.buses.items():
            if hasattr(monitor, 'finish'):
                monitor.finish()
            elif monitor.pending is not None:
                raise AssertionError('SOC_PENDING_APB')
            if not self.bus_checks[name]:
                raise AssertionError('SOC_NO_BUS_CHECKS:'+name)
        return dict(cpu_checks=self.cpu.checks if self.cpu else 0, bus_checks=dict(self.bus_checks),
                    uart_frames=self.serial.count)
