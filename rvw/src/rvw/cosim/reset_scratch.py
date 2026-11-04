"""Track only the unspecified reset bits of machine scratch (mscratch)."""
from .checker import csr_access


class ResetScratch:
    def __init__(self, mask):
        self.mask = mask

    @staticmethod
    def seed(model, value):
        if not hasattr(model, 'set_mscratch'):
            raise ValueError('reference cannot synchronize unspecified mscratch reset state')
        model.set_mscratch(value)

    def observe(self, expected, actual, model):
        """Return the old-value read mask and separate snapshot observations."""
        read_mask, entries = 0, []
        insn = expected['insn']
        if self.mask and not expected['trap'] and csr_access(insn) == 0x340:
            op, source = (insn >> 12) & 7, (insn >> 15) & 31
            if op >= 5:
                value = source
            elif source:
                if 'before' not in expected:
                    raise ValueError('reference lacks operands for mscratch reset tracking')
                value = expected['before'][source]
            else:
                value = 0
            if expected['rd']:
                read_mask = self.mask
                old = ((expected['rd_wdata'] & ~read_mask)
                       | (actual['rd_wdata'] & read_mask))
                updated = (value if op in (1, 5) else old | value if op in (2, 6)
                           else old & ~value)
                self.seed(model, updated)
                self.mask = 0
            elif op in (1, 5):
                self.mask = 0
            else:
                self.mask &= ~value
        snapshot = actual.get('csr_state', {})
        if self.mask and '0x340' in snapshot:
            if not hasattr(model, 'csr_snapshot'):
                raise ValueError('reference cannot check CSR snapshots')
            reference = model.csr_snapshot(['0x340'])['0x340']
            observed = snapshot['0x340']
            self.seed(model, (reference & ~self.mask) | (observed & self.mask))
            entries.append(dict(order=actual['order'], reason='csr_reset_unknown',
                                csr='0x340', mask=hex(self.mask), source='csr_state',
                                reference=hex(reference), core=hex(observed)))
            self.mask = 0
        return read_mask, entries
