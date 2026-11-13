"""Deterministic plugin devices. Addresses and interrupt routing are project data."""
import json
from rvw.cosim.devices import Ns16550, Timer, TimerMap, Plic, PlicMap


def encode(value):
    if isinstance(value, (bytes, bytearray)):
        return {'bytes': bytes(value).hex()}
    if isinstance(value, set):
        return {'set': sorted(value)}
    if isinstance(value, list):
        return [encode(v) for v in value]
    if isinstance(value, dict):
        return {k: encode(v) for k, v in value.items()}
    return value


def decode(value):
    if isinstance(value, dict):
        if set(value) == {'bytes'}:
            return bytearray.fromhex(value['bytes'])
        if set(value) == {'set'}:
            return set(value['set'])
        return {k: decode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [decode(v) for v in value]
    return value


def exact(value):
    """One map integer: a JSON integer or a decimal/0x string, as in rvw.sim-map/1.

    Hosts that parse JSON numbers as doubles (Scala ujson, JavaScript) cannot keep
    64-bit values such as an all-ones mtimecmp. Refuse floats instead of rounding."""
    if isinstance(value, bool):
        raise ValueError('device map integer must not be boolean')
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value, 16) if value.lower().startswith('0x') else int(value)
    if isinstance(value, list):
        return [exact(v) for v in value]
    raise ValueError(f'device map integer must be exact; got {value!r} '
                     '(write values above 2**53 as "0x..." strings)')


def exact_map(data):
    return {k: exact(v) for k, v in data.items()}


class Console:
    """HTIF console output command only. No host file or input effects."""
    def __init__(self):
        self.output = bytearray()
        self.fromhost = 0

    def read(self, offset, size):
        if (offset, size) == (8, 8):
            return self.fromhost
        raise ValueError('HTIF needs a 64-bit fromhost read')

    def write(self, offset, value, size):
        if (offset, size) == (8, 8) and value == 0:
            self.fromhost = 0
        elif (offset, size) == (0, 8) and value >> 48 == 0x101:
            self.output.append(value & 255)
            self.fromhost = 0x101 << 48
        else:
            raise ValueError('unsupported HTIF command')


class Block:
    """Simple byte-addressed RAM disk window. No virtio transport claim."""
    def __init__(self, image):
        self.image = bytearray.fromhex(image)
        if not self.image:
            raise ValueError('block image must not be empty')

    def read(self, offset, size):
        if offset < 0 or offset + size > len(self.image):
            raise ValueError('block access out of range')
        return int.from_bytes(self.image[offset:offset + size], 'little')

    def write(self, offset, value, size):
        self.read(offset, size)
        self.image[offset:offset + size] = value.to_bytes(size, 'little')


class Device:
    """One ABI handle, one selected device, one absolute cycle clock."""
    def __init__(self, config, seed=0):
        self.config = json.loads(config)
        c = self.config
        self.kind = c['model']
        if self.kind == 'ns16550':
            self.model = Ns16550()
        elif self.kind in ('clint', 'aclint'):
            self.model = Timer(TimerMap.from_dict(exact_map(c['map'])))
        elif self.kind == 'plic':
            self.model = Plic(PlicMap(**exact_map(c['map'])))
        elif self.kind == 'htif-console':
            self.model = Console()
        elif self.kind == 'simple-block':
            self.model = Block(c['image_hex'])
        else:
            raise ValueError('unsupported device model')
        self.cycle = 0

    def read(self, offset, size):
        if not 1 <= size <= 8:
            raise ValueError('invalid access width')
        if self.kind == 'ns16550':
            if size != 1:
                raise ValueError('UART needs byte accesses')
            return self.model.read(offset)
        return self.model.read(offset, size)

    def write(self, offset, size, value, mask):
        if not 1 <= size <= 8 or mask != (1 << size) - 1:
            # Reading a device to merge lanes could acknowledge an interrupt.
            raise ValueError('device registers require full byte masks')
        if not 0 <= value < 1 << (8 * size):
            raise ValueError('write value exceeds width')
        if self.kind == 'ns16550':
            if size != 1:
                raise ValueError('UART needs byte accesses')
            self.model.write(offset, value)
        else:
            self.model.write(offset, value, size)

    def tick(self, cycle):
        if cycle < self.cycle:
            raise ValueError('device time moved backward')
        if self.kind in ('clint', 'aclint'):
            ratio = self.config['cycles_per_tick']
            if type(ratio) is not int or ratio < 1:
                raise ValueError('cycles_per_tick must be positive')
            self.model.tick(cycle // ratio - self.cycle // ratio)
        if self.kind == 'plic':
            for event in self.config.get('levels', []):
                if self.cycle < event['cycle'] <= cycle:
                    self.model.set_level(event['source'], event['level'])
        self.cycle = cycle

    def interrupts(self):
        if self.kind == 'ns16550':
            return int(self.model.irq())
        if self.kind in ('clint', 'aclint'):
            # Two output bits per hart: software then timer. Routing is external.
            return sum(((self.model.irq(i) >> 3 & 1) | (self.model.irq(i) >> 6 & 2)) << (2*i)
                       for i in range(len(self.model.compare)))
        if self.kind == 'plic':
            return sum(int(self.model.irq(i)) << i for i in range(self.model.map.contexts))
        return 0

    def set_level(self, source, level):
        """Project scheduler supplies gateway levels before each access or tick."""
        if self.kind != 'plic':
            raise ValueError('device has no gateway inputs')
        self.model.set_level(source, level)

    def snapshot(self):
        state = {k: v for k, v in vars(self.model).items() if k != 'map'}
        return json.dumps(dict(schema='rvw.standard-device/1', config=self.config,
                               cycle=self.cycle, state=encode(state)), sort_keys=True).encode()

    def restore(self, payload):
        saved = json.loads(payload)
        if saved['schema'] != 'rvw.standard-device/1' or saved['config'] != self.config:
            raise ValueError('device checkpoint identity differs')
        state = decode(saved['state'])
        if set(state) != set(vars(self.model)) - {'map'} or saved['cycle'] < 0:
            raise ValueError('invalid device checkpoint')
        vars(self.model).update(state)
        self.cycle = saved['cycle']
