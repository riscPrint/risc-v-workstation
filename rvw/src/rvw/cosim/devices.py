"""Deterministic reference devices. Project data supplies every MMIO address.

These models do not drive an RTL bus. A load of a claim register has side effects.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class PlicMap:
    priority: int
    pending: int
    enable: int
    enable_stride: int
    context: int
    context_stride: int
    sources: int
    contexts: int
    max_priority: int = 7

    def __post_init__(self):
        if not (1 <= self.sources <= 1023 and self.contexts > 0 and self.max_priority > 0
                and self.max_priority & (self.max_priority + 1) == 0):
            raise ValueError('invalid PLIC dimensions')
        if any(a < 0 or a % 4 for a in (self.priority, self.pending, self.enable,
                                       self.context, self.enable_stride, self.context_stride)):
            raise ValueError('PLIC addresses and strides must be word aligned')
        if self.enable_stride < 4 * (self.sources // 32 + 1) or self.context_stride < 8:
            raise ValueError('overlapping PLIC registers')


class Plic:
    """Level gateways, one global pending request per source, ordered bus actions."""
    def __init__(self, layout: PlicMap):
        self.map = layout
        self.reset()

    def reset(self):
        m = self.map
        self.priority = [0] * (m.sources + 1)
        self.pending = set()
        self.busy = set()
        self.level = set()
        self.enable = [set() for _ in range(m.contexts)]
        self.threshold = [0] * m.contexts

    def set_level(self, source, level):
        if not 1 <= source <= self.map.sources:
            raise ValueError('invalid source')
        if level:
            self.level.add(source)
            if source not in self.busy:
                self.pending.add(source)
                self.busy.add(source)
        else:
            self.level.discard(source)

    def best(self, context, *, threshold=True):
        eligible = [s for s in self.pending & self.enable[context]
                    if self.priority[s] > (self.threshold[context] if threshold else 0)]
        return min(eligible, key=lambda s: (-self.priority[s], s), default=0)

    def irq(self, context):
        return bool(self.best(context))

    def _decode(self, address, size):
        if size != 4 or address % 4:
            raise ValueError('PLIC needs aligned 32-bit accesses')
        m = self.map
        for base, count, stride, kind in [(m.priority, m.sources + 1, 4, 'priority'),
                                         (m.pending, m.sources // 32 + 1, 4, 'pending')]:
            if base <= address < base + count * stride:
                return kind, (address - base) // stride, 0
        for c in range(m.contexts):
            off = address - (m.enable + c * m.enable_stride)
            if 0 <= off < 4 * (m.sources // 32 + 1):
                return 'enable', c, off // 4
            off = address - (m.context + c * m.context_stride)
            if off in (0, 4):
                return ('threshold' if off == 0 else 'claim'), c, 0
        raise ValueError('unmapped PLIC address')

    def read(self, address, size=4):
        kind, i, word = self._decode(address, size)
        if kind == 'priority':
            return self.priority[i]
        if kind in ('enable', 'pending'):
            bits = self.enable[i] if kind == 'enable' else self.pending
            word = word if kind == 'enable' else i
            return sum(1 << (s % 32) for s in bits if s // 32 == word)
        if kind == 'threshold':
            return self.threshold[i]
        source = self.best(i, threshold=False)
        self.pending.discard(source)
        return source

    def write(self, address, value, size=4):
        if not 0 <= value < 1 << 32:
            raise ValueError('invalid word')
        kind, i, word = self._decode(address, size)
        if kind == 'priority':
            if i:
                self.priority[i] = value & self.map.max_priority
        elif kind == 'enable':
            for s in range(max(1, word * 32), min(self.map.sources + 1, (word + 1) * 32)):
                (self.enable[i].add if value & (1 << (s % 32)) else self.enable[i].discard)(s)
        elif kind == 'threshold':
            self.threshold[i] = value & self.map.max_priority
        elif kind == 'claim' and value in self.enable[i]:
            # Completions from contexts that do not enable this source are ignored.
            if value in self.busy and value not in self.pending:
                self.busy.remove(value)
                if value in self.level:
                    self.set_level(value, True)
        # Writes to pending bits have no effect.


@dataclass(frozen=True)
class TimerMap:
    """Absolute CLINT or ACLINT MTIMER/MSWI addresses, in hart index order."""
    mtime: int
    mtimecmp: tuple[int, ...]
    msip: tuple[int, ...]
    reset_mtime: int
    reset_mtimecmp: int

    def __post_init__(self):
        if not self.mtimecmp or len(self.msip) != len(self.mtimecmp):
            raise ValueError('timer and software hart counts differ')
        ranges = [(self.mtime, 8)] + [(a, 8) for a in self.mtimecmp] + [(a, 4) for a in self.msip]
        used = set()
        for address, width in ranges:
            if address < 0 or address % width or used.intersection(range(address, address + width)):
                raise ValueError('invalid or overlapping timer registers')
            used.update(range(address, address + width))
        if any(not 0 <= value < 1 << 64 for value in (self.reset_mtime, self.reset_mtimecmp)):
            raise ValueError('invalid timer reset value')

    @classmethod
    def from_dict(cls, data):
        """Parse a project-owned JSON object. No core name or default map."""
        return cls(mtime=data['mtime'], mtimecmp=tuple(data['mtimecmp']),
                   msip=tuple(data['msip']), reset_mtime=data['reset_mtime'],
                   reset_mtimecmp=data['reset_mtimecmp'])


class Timer:
    """CLINT/ACLINT MTIMER and MSWI model, with explicit time advancement."""
    MASK = (1 << 64) - 1

    def __init__(self, layout: TimerMap):
        self.map = layout
        self.reset()

    def reset(self):
        self.mtime = self.map.reset_mtime
        self.compare = [self.map.reset_mtimecmp] * len(self.map.mtimecmp)
        self.software = [0] * len(self.map.msip)

    def tick(self, ticks=1):
        if type(ticks) is not int or ticks < 0:
            raise ValueError('ticks must be a nonnegative integer')
        self.mtime = (self.mtime + ticks) & self.MASK

    def irq(self, hart):
        return (8 if self.software[hart] else 0) | (128 if self.mtime >= self.compare[hart] else 0)

    def _decode(self, address, size):
        if size not in (4, 8) or address % size:
            raise ValueError('timer needs aligned 32-bit or 64-bit accesses')
        for kind, addresses, width in [('mtime', (self.map.mtime,), 8),
                                       ('compare', self.map.mtimecmp, 8),
                                       ('software', self.map.msip, 4)]:
            for hart, base in enumerate(addresses):
                if base <= address and address + size <= base + width:
                    return kind, hart, 8 * (address - base)
        raise ValueError('unmapped timer address')

    def read(self, address, size=4):
        kind, hart, shift = self._decode(address, size)
        value = self.mtime if kind == 'mtime' else getattr(self, kind)[hart]
        return (value >> shift) & ((1 << (size * 8)) - 1)

    def write(self, address, value, size=4):
        kind, hart, shift = self._decode(address, size)
        if not 0 <= value < 1 << (size * 8):
            raise ValueError('value exceeds access width')
        if kind == 'software':
            self.software[hart] = value & 1
        else:
            old = self.mtime if kind == 'mtime' else self.compare[hart]
            mask = ((1 << (size * 8)) - 1) << shift
            new = (old & ~mask) | (value << shift)
            if kind == 'mtime':
                self.mtime = new
            else:
                self.compare[hart] = new


class Ns16550:
    """Single-byte, output-only ns16550a register subset for boot polling.

    No RX, modem input or baud timing is modeled. Unsupported requests fail.
    THRE interrupts use a latched source cleared by IIR reads or TX writes.
    """
    def __init__(self):
        self.reset()

    def reset(self):
        self.ier = self.lcr = self.scr = self.dll = self.dlm = 0
        self.thre = False
        self.output = bytearray()

    def irq(self):
        return bool(self.ier & 2 and self.thre)

    def read(self, register):
        if register == 0:
            if self.lcr & 0x80:
                return self.dll
            raise ValueError('UART RX input is not supported')
        if register == 1:
            return self.dlm if self.lcr & 0x80 else self.ier
        if register == 2:
            value = 2 if self.irq() else 1
            self.thre = False
            return value
        if register == 3:
            return self.lcr
        if register == 5:
            return 0x60  # TX holding and shift registers are empty.
        if register == 7:
            return self.scr
        raise ValueError('unsupported UART register')

    def write(self, register, value):
        if not 0 <= value <= 255:
            raise ValueError('UART requires byte values')
        if register == 0:
            if self.lcr & 0x80:
                self.dll = value
            else:
                self.output.append(value)
                self.thre = True
        elif register == 1:
            if self.lcr & 0x80:
                self.dlm = value
            else:
                if value & ~2:
                    raise ValueError('only UART TX interrupts are supported')
                if value & 2 and not self.ier & 2:
                    self.thre = True
                self.ier = value
        elif register == 2:
            if value & ~6:
                raise ValueError('UART FIFO mode is not supported')
        elif register == 3:
            self.lcr = value
        elif register == 7:
            self.scr = value
        else:
            raise ValueError('unsupported UART register')
