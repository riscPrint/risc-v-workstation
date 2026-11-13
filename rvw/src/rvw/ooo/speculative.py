"""Deterministic occupancy filler when functional predicted paths are unavailable."""
from dataclasses import replace
from collections import Counter


class MixWork:
    """Sample the measured committed mix, without invented cache transactions.

    This is an occupancy approximation. It does not represent real path bytes,
    speculative dependencies, predictor repair, or speculative cache pollution.
    """
    occupancy_only = True

    def __init__(self, instructions):
        self.mix = list(instructions)
        self.cursor = 0
        self.events = Counter()

    def begin(self, op, cycle, latency, config, instruction_memory):
        result = []
        delay = 0  # Fetched work can already be at rename when the branch issues.
        for slot in range(config.fetch_width * latency):
            template = self.mix[self.cursor % len(self.mix)]
            self.cursor += 1
            # Branches become inert ALU work. There is no nested prediction.
            kind = template.kind if template.kind in ('load', 'store', 'multiply', 'divide') else 'alu'
            filler = replace(template, kind=kind, sources=(), dest=None)
            result.append((filler, cycle + slot // config.fetch_width + delay))
        return result
