"""Project-owned Linux device composition. No RTL bus connection or time claim."""
import json
from pathlib import Path
from rvw.cosim.devices import Ns16550, Timer, TimerMap, Plic, PlicMap


class LinuxDevices:
    def __init__(self, path=Path(__file__).with_name('devices.json')):
        self.data = json.loads(Path(path).read_text())
        if self.data['schema'] != 'rvw.linux-devices/1':
            raise ValueError('unsupported Linux device schema')
        self.uart = Ns16550()
        self.timer = Timer(TimerMap.from_dict(self.data['timer']))
        self.plic = Plic(PlicMap(**self.data['plic']))

    def reset(self):
        for device in (self.uart, self.timer, self.plic):
            device.reset()

    def irq(self):
        self.plic.set_level(self.data['uart']['plic_source'], self.uart.irq())
        return self.timer.irq(0) | (0x800 if self.plic.irq(0) else 0) | (0x200 if self.plic.irq(1) else 0)

    def device(self, address, size):
        uart = self.data['uart']
        if uart['base'] <= address < uart['base'] + uart['size']:
            if size != 1:
                raise ValueError('UART requires byte accesses')
            return self.uart, address - uart['base'], True
        if self.data['clint_base'] <= address < self.data['clint_base'] + 0x10000:
            return self.timer, address, False
        if self.data['plic']['priority'] <= address < self.data['plic']['priority'] + 0x600000:
            return self.plic, address, False
        raise ValueError('unmapped Linux device address')

    def read(self, address, size):
        self.irq()
        device, register, byte = self.device(address, size)
        value = device.read(register) if byte else device.read(register, size)
        self.irq()
        return value

    def write(self, address, value, size):
        self.irq()
        device, register, byte = self.device(address, size)
        if byte:
            device.write(register, value)
        else:
            device.write(register, value, size)
        self.irq()
