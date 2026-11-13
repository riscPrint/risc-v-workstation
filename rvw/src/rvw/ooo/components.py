"""Timing adapters over the component worker's native library."""
from collections import Counter
from rvw.csim.lib import Components
from rvw.csim.traces import branch_kind


class Adapter:
    def __init__(self, description):
        self.description = description
        try:
            self.models = Components(description)
        except RuntimeError as exc:
            raise ValueError(str(exc)) from exc
        self.events = Counter()
        self.pending = None
        self.last_delay = 0
        self.fetch_cycle = None
        self.fetch_lines = {}

    def __enter__(self): return self
    def __exit__(self, *exc): self.models.close()

    def kind(self, op):
        if op.mnemonic == 'c.jal':
            return 'call'
        return branch_kind(op.encoding, op.dest or 0) or ('cond' if op.kind == 'branch' else 'jump')

    def predict_instruction(self, op):
        c = self.models
        kind = self.kind(op)
        ticket, taken = c.predict(op.pc) if kind == 'cond' else (0, True)
        indirect = None
        self.last_delay = 0
        predicted = op.pc + op.length
        if taken:
            level, target = c.btb_lookup(op.pc)
            if level >= 0:
                predicted = target
                levels = self.description.get('btb', {}).get('levels')
                self.last_delay = levels[level].get('latency', 0) if levels and level < len(levels) else self.description.get('btb', {}).get('latency', 0)
                self.events[f'btb_level_{level}_hits'] += 1
            else:
                self.events['btb_misses'] += 1
            if kind == 'ret' and 'ras' in self.description:
                target = c.ras_pop()
                if target is not None:
                    predicted = target
            elif kind in ('ijump','icall') and 'indirect' in self.description:
                indirect, target = c.indirect_predict(op.pc)
                if target:
                    predicted = target
        self.pending = (ticket, indirect, kind)
        self.events['btb_lookup_delay_cycles'] += self.last_delay
        return predicted

    def update_instruction(self, op):
        ticket, indirect, kind = self.pending
        taken = op.next_pc != op.pc + op.length
        self.models.history(op.pc, kind, taken, op.next_pc)
        self.models.update(ticket, taken)
        if indirect is not None:
            self.models.indirect_update(indirect, op.next_pc)
        self.models.btb_update(op.pc, kind, taken, op.next_pc)
        if kind in ('call','icall'):
            self.models.ras_push(op.pc + op.length)
        self.pending = None

    def access_instruction(self, op, cycle):
        memory = self.description.get('memory', {})
        line = memory.get('l1d', {}).get('line_bytes', 64)
        page = 1 << memory.get('tlb', {}).get('page_bits', 12)
        # Split on both line and translation boundaries. All subrequests start
        # at the current issue cycle. The last completion determines latency.
        end = op.address + op.size
        address, done = op.address, cycle
        while address < end:
            done = max(done, self.models.access(cycle, op.pc, address, store=op.kind == 'store'))
            address = min(end, (address//line+1)*line, (address//page+1)*page)
        return done-cycle

    def fetch(self, op, cycle):
        if self.fetch_cycle != cycle:
            self.fetch_cycle, self.fetch_lines = cycle, {}
        line = self.description.get('memory', {}).get('l1i', {}).get('line_bytes', 64)
        first, last = op.pc//line, (op.pc + op.length-1)//line
        done = cycle
        for block in range(first, last+1):
            if block not in self.fetch_lines:
                self.fetch_lines[block] = self.models.access(cycle, op.pc, block*line, fetch=True)
            done = max(done, self.fetch_lines[block])
        return done-cycle

    def stats(self, instructions):
        return self.models.stats(instructions)
