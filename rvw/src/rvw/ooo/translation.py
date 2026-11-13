"""Page-granular translation timing with finite concurrent page walks."""
from collections import Counter


class Translation:
    def __init__(self, description):
        expected = {'entries', 'page_bytes', 'hit_latency', 'walk_latency', 'walkers'}
        if not isinstance(description, dict) or set(description) != expected:
            raise ValueError('translation requires entries, page_bytes, hit_latency, walk_latency, walkers')
        if any(type(v) is not int or v < 1 for v in description.values()):
            raise ValueError('translation fields must be positive integers')
        if description['page_bytes'] & (description['page_bytes'] - 1):
            raise ValueError('translation page_bytes must be a power of two')
        self.config = description
        self.tags, self.pending = {}, {}
        self.events = Counter()

    def access(self, address, size, cycle):
        """Return delay, or None on walker backpressure. Faults are unsupported.

        Cross-page accesses require all pages. No partial walk reservation is
        made when there are not enough walkers. Fills occur at walk completion.
        """
        c = self.config
        for page, ready in list(self.pending.items()):
            if ready <= cycle:
                if page not in self.tags and len(self.tags) >= c['entries']:
                    del self.tags[next(iter(self.tags))]
                self.tags[page] = True
                del self.pending[page]
        pages = range(address // c['page_bytes'], (address + size - 1) // c['page_bytes'] + 1)
        missing = [p for p in pages if p not in self.tags and p not in self.pending]
        if len(missing) + len(self.pending) > c['walkers']:
            self.events['walker_full'] += 1
            return None
        for page in missing:
            self.pending[page] = cycle + c['walk_latency']
            self.events['page_walks'] += 1
        delay = max([c['hit_latency']] + [self.pending[p] - cycle for p in pages if p in self.pending])
        self.events['tlb_misses' if missing or any(p in self.pending for p in pages) else 'tlb_hits'] += 1
        return delay
