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
