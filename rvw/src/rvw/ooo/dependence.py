"""A bounded PC-pair dependence predictor, distinct from memory renaming."""


def overlaps(a, b):
    return a.address < b.address + b.size and b.address < a.address + a.size


class Dependence:
    def __init__(self, entries):
        self.entries = entries
        self.pairs = {}

    def waits(self, load, store):
        return (load.pc, store.pc) in self.pairs

    def train(self, load, store):
        pair = (load.pc, store.pc)
        if pair not in self.pairs and len(self.pairs) >= self.entries:
            del self.pairs[next(iter(self.pairs))]
        self.pairs[pair] = True

    def violations(self, store, younger):
        loads = [entry for entry in younger if entry.insn.kind == 'load' and
                 entry.done is not None and overlaps(store, entry.insn)]
        for entry in loads:
            self.train(entry.insn, store)
        return loads
