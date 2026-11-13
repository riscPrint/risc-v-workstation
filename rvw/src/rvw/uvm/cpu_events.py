"""Independent reference synchronization for project CPU control observations."""


class CpuEvents:
    def __init__(self, reference, *, xlen, irq_inputs=()):
        self.reference, self.xlen = reference, xlen
        self.irq_inputs = set(irq_inputs)
        self.traps = self.interrupts = self.debug_checks = 0

    def trap(self, cause, tval, *, driven_irqs=0):
        interrupt = bool(cause & (1 << (self.xlen-1)))
        if interrupt:
            code = cause & ((1 << (self.xlen-1))-1)
            if code not in self.irq_inputs or not driven_irqs & (1 << code):
                raise AssertionError('CPU_UNREQUESTED_INTERRUPT')
        effect = self.reference.step(interrupt=cause if interrupt else 0)
        if (not effect['trap'] or bool(effect['intr']) != interrupt or
                effect['cause'] != cause or effect['tval'] != tval):
            raise AssertionError('SPIKE_TRAP_MISMATCH')
        self.traps += 1
        self.interrupts += interrupt
        return effect

    def debug(self, action, observed):
        # Spike currently exposes halt and observation, not a generic resume API.
        if action not in ('halt','observe'):
            raise ValueError('unsupported:cpu_debug_resume')
        expected = self.reference.debug_event(action)
        fields = ('mode','dpc','dcsr','step')
        if (observed.get('pc') != expected['pc'] or
                any(observed.get('debug',{}).get(k) != expected['debug'][k] for k in fields)):
            raise AssertionError('SPIKE_DEBUG_MISMATCH')
        self.debug_checks += 1
        return expected
