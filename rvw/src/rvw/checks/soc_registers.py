"""Independent register side-effect oracle for observed completed APB accesses."""
from rvw.soc.model import load


class RegisterEffects:
    def __init__(self, source):
        self.registers, self.state = {}, {}
        self.checks, self.unknown_reads = 0, 0
        for region in load(source)['regions']:
            for reg in region['registers']:
                address = region['base'] + reg['offset']
                self.registers[address] = reg
                self.state[address] = reg['reset']

    def reset(self):
        self.state = {addr:reg['reset'] for addr,reg in self.registers.items()}

    def observe(self, address, write, data, response=0, *, error=False, strobe=None):
        reg = self.registers.get(address)
        if reg is None:
            return False  # Device-specific undefined-address behavior is not in rvw.soc/1.
        allowed = ('w' if write else 'r') in reg['access']
        if not allowed:
            if not error:
                raise AssertionError('SOC_REGISTER_ACCESS')
            self.checks += 1
            return True
        if error:
            raise AssertionError('SOC_REGISTER_ERROR')
        width = reg['width']
        mask = (1 << width)-1
        if not 0 <= (data if write else response) <= mask:
            raise AssertionError('SOC_REGISTER_WIDTH')
        old = self.state[address]
        if write:
            lanes = (1 << (width//8))-1 if strobe is None else strobe
            if not 0 <= lanes < 1 << (width//8):
                raise ValueError('strobe exceeds register width')
            bits = sum(255 << (8*i) for i in range(width//8) if lanes & (1 << i))
            if reg['write_action'] == 'one_to_clear':
                self.state[address] = (old & ~(data & bits)) if old is not None else (0 if data & bits == mask else None)
            else:
                self.state[address] = (old & ~bits | data & bits) if old is not None else (data if bits == mask else None)
        else:
            if old is None:
                self.unknown_reads += 1
            elif response != old:
                raise AssertionError('SOC_REGISTER_DATA')
            else:
                self.checks += 1
            if reg['read_action'] == 'clear':
                self.state[address] = 0
        return True

    def finish(self):
        return dict(status='samples_match' if self.checks else 'no_checks', checks=self.checks,
                    unknown_reads=self.unknown_reads,
                    scope='observed mapped register reads and access errors; no autonomous device behavior')
