"""Shared execution ports and distributed scheduler capacity."""
from collections import Counter


class Execution:
    def __init__(self, description):
        if not isinstance(description, dict) or set(description) - {'ports', 'bindings', 'queues', 'intervals'}:
            raise ValueError('invalid execution description')
        self.ports = description.get('ports', {})
        self.bindings = description.get('bindings', {})
        self.queues = description.get('queues', {})
        self.intervals = description.get('intervals', {})
        for group in (self.ports, self.queues, self.intervals):
            if not isinstance(group, dict) or any(type(v) is not int or v < 1 for v in group.values()):
                raise ValueError('execution capacities and intervals must be positive integers')
        if not isinstance(self.bindings, dict):
            raise ValueError('execution bindings must be an object')
        for kind, names in self.bindings.items():
            if not isinstance(names, list) or not names or any(p not in self.ports for p in names):
                raise ValueError(f'invalid port binding for {kind}')
        if set(self.ports) - {p for names in self.bindings.values() for p in names}:
            raise ValueError('execution ports must have bindings')
        self.ready = {name: [0] * count for name, count in self.ports.items()}
        self.events = Counter()

    def queue_full(self, kind, waiting):
        return kind in self.queues and sum(e.insn.kind == kind for e in waiting) >= self.queues[kind]

    def reserve(self, kind, cycle, commit=True):
        if kind not in self.bindings:
            return True
        # Choose the least occupied compatible port, then its first ready lane.
        candidates = []
        for port in self.bindings[kind]:
            for lane, ready in enumerate(self.ready[port]):
                if ready <= cycle:
                    candidates.append((ready, port, lane))
        if not candidates:
            self.events['shared_port_blocked'] += 1
            return False
        if not commit:
            return True
        _, port, lane = min(candidates)
        self.ready[port][lane] = cycle + self.intervals.get(kind, 1)
        self.events[f'port_{port}_issued'] += 1
        return True
