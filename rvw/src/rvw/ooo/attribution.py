"""A mutually exclusive model slot partition, not hardware top-down counters."""
from collections import Counter


class Attribution:
    def __init__(self, width):
        self.width = width
        self.slots = Counter(retiring=0, frontend_bound=0, bad_speculation=0, backend_bound=0)

    def observe(self, retired, recovery, backend_work):
        self.slots['retiring'] += retired
        cause = 'bad_speculation' if recovery else 'backend_bound' if backend_work else 'frontend_bound'
        self.slots[cause] += self.width - retired

    def report(self):
        total = sum(self.slots.values())
        return dict(unit='commit_slots', total_slots=total, slots=dict(self.slots),
                    fractions={key: value / total for key, value in self.slots.items()},
                    method='retired slots, then recovery, then ROB occupancy, then front end')
