"""Replay harness-owned inputs at an explicit retirement boundary."""


class Environment:
    def __init__(self):
        self.order = 0
        self.levels = 0
        self.seen_pins = False
        self.read = None
        self.write = None
        self.events = 0

    def event(self, record, model, platform):
        if record['before_order'] != self.order:
            raise ValueError('environment event is at the wrong retirement boundary')
        self.events += 1
        kind = record['kind']
        if kind == 'pins':
            if not hasattr(model, 'environment_inputs'):
                raise ValueError('reference cannot replay declared environment inputs')
            self.seen_pins = True
            self.levels = record['levels']
            model.environment_inputs(self.levels)
        elif kind == 'device-write':
            if self.write is not None:
                raise ValueError('multiple device writes at one scalar retirement')
            self.write = record
        elif kind == 'device-read':
            if self.read is not None:
                raise ValueError('multiple device responses for one scalar retirement')
            if not any(a <= record['address'] and record['address'] + record['size'] <= a+n for a,n in platform.mmio):
                raise ValueError('environment device response lies outside declared MMIO')
            self.read = record

    def retire(self, actual):
        if not self.seen_pins:
            raise ValueError('missing initial pin evidence')
        if actual['order'] != self.order:
            raise ValueError('ordered environment requires contiguous retirements from reset')
        self.order += 1
        if self.write is not None:
            write, self.write = self.write, None
            if (actual['mem_addr'] != write['address'] or actual['mem_wmask'] != (1 << write['size'])-1
                    or actual['mem_wdata'] & ((1 << (8*write['size']))-1) != write['data']):
                raise ValueError('device write event differs from retirement')
        read, self.read = self.read, None
        if read is None:
            return None
        mask = (1 << read['size']) - 1
        if actual['mem_addr'] != read['address'] or actual['mem_rmask'] != mask:
            raise ValueError('device response has no matching retired read')
        return read['address'], read['data']
