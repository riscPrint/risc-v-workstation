"""Expose observed native component counts to the existing RTL event mapper."""


def counters(stats):
    events = {}
    memory = stats.get('memory', {})
    for level in ('l1i','l1d','l2','llc'):
        cache = memory.get(level, {})
        for source in ('demand_accesses','demand_hits','demand_misses','writebacks'):
            if source in cache and type(cache[source]) is int:
                events[f'{level}_{source}'] = cache[source]
        for source, value in cache.get('prefetch', {}).items():
            if type(value) is int:
                events[f'{level}_prefetch_{source}'] = value
    tlb = memory.get('tlb', {})
    for source, value in tlb.items():
        if type(value) is int:
            events[f'tlb_{source}'] = value
    for level in ('l1','l2'):
        for source in ('accesses','misses'):
            if source in tlb.get(level, {}):
                events[f'tlb_{level}_{source}'] = tlb[level][source]
    return events
