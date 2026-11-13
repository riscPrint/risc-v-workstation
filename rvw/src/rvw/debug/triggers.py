"""Sdtrig trigger model: mcontrol (2), icount (3), itrigger (4), etrigger (5), mcontrol6 (6).

The model follows the profile's declared WARL choices. It does not model
virtualization (vs/vu read 0), textra (tdata3 reads 0) or size matching
other than "any size". Unsupported choices legalize as the profile declares.
"""
from __future__ import annotations

MCONTROL, ICOUNT, ITRIGGER, ETRIGGER, MCONTROL6, DISABLED = 2, 3, 4, 5, 6, 15
TYPES = {MCONTROL: 'mcontrol', ICOUNT: 'icount', ITRIGGER: 'itrigger', ETRIGGER: 'etrigger',
         MCONTROL6: 'mcontrol6'}
ALL_MATCHES = (0, 1, 2, 3, 4, 5, 8, 9, 12, 13)


def bits(value, hi, lo):
    return (value >> lo) & ((1 << (hi - lo + 1)) - 1)


def put(value, hi, lo, field):
    mask = ((1 << (hi - lo + 1)) - 1) << lo
    return (value & ~mask) | ((field << lo) & mask)


# Field positions shared by the address/data match types. (hi, lo) per field.
MC_FIELDS = {
    MCONTROL: dict(hit=(20, 20), select=(19, 19), timing=(18, 18), size=(17, 16), action=(15, 12),
                   chain=(11, 11), match=(10, 7), m=(6, 6), s=(4, 4), u=(3, 3), execute=(2, 2),
                   store=(1, 1), load=(0, 0)),
    MCONTROL6: dict(vs=(24, 24), vu=(23, 23), hit=(22, 22), select=(21, 21), size=(18, 16),
                    action=(15, 12), chain=(11, 11), match=(10, 7), m=(6, 6), s=(4, 4), u=(3, 3),
                    execute=(2, 2), store=(1, 1), load=(0, 0)),
    ICOUNT: dict(vs=(26, 26), vu=(25, 25), hit=(24, 24), count=(23, 10), m=(9, 9), pending=(8, 8),
                 s=(7, 7), u=(6, 6), action=(5, 0)),
    ITRIGGER: dict(vs=(12, 12), vu=(11, 11), nmi=(10, 10), m=(9, 9), s=(7, 7), u=(6, 6), action=(5, 0)),
    ETRIGGER: dict(vs=(12, 12), vu=(11, 11), m=(9, 9), s=(7, 7), u=(6, 6), action=(5, 0)),
}


class Trigger:
    def __init__(self, types):
        self.types = list(types)
        self.tdata1 = 0
        self.tdata2 = 0


class TriggerUnit:
    """Profile keys: count, types (list, or list per trigger), matches, actions, timing,
    chain, unsupported_type, tcontrol, maskmax, version."""

    def __init__(self, hart, profile):
        self.hart = hart
        self.profile = profile
        types = profile.get('types', [MCONTROL6])
        count = int(profile.get('count', 0))
        per = types if types and isinstance(types[0], list) else [types] * count
        self.slots = [Trigger(per[i]) for i in range(count)]
        self.matches = tuple(profile.get('matches', ALL_MATCHES))
        self.actions = tuple(profile.get('actions', (0, 1)))
        self.timings = tuple(profile.get('timing', (0, 1)))
        self.chain_ok = bool(profile.get('chain', True))
        self.unsupported = int(profile.get('unsupported_type', DISABLED))
        self.has_tcontrol = bool(profile.get('tcontrol', True))
        self.maskmax = int(profile.get('maskmax', 31))
        self.version = int(profile.get('version', 1))
        self.sizes = tuple(profile.get('sizes', (0,)))
        self.reset()

    @property
    def xlen(self):
        return self.hart.xlen

    def reset(self):
        self.tselect = 0
        self.tcontrol = 0
        self.mcontext = 0
        self.pending = []
        self.exec_mode = 3
        for slot in self.slots:
            slot.tdata1 = self._make(slot.types[0], 0, 0) if slot.types else 0
            slot.tdata2 = 0

    def _make(self, kind, dmode, fields):
        value = (kind << (self.xlen - 4)) | (dmode << (self.xlen - 5)) | fields
        if kind == MCONTROL:
            value = put(value, self.xlen - 6, self.xlen - 11, self.maskmax)
        return value

    def kind(self, slot):
        return slot.tdata1 >> (self.xlen - 4)

    def dmode(self, slot):
        return (slot.tdata1 >> (self.xlen - 5)) & 1

    def field(self, slot, name):
        spec = MC_FIELDS.get(self.kind(slot), {}).get(name)
        if spec is None:
            if name == 'hit' and self.kind(slot) in (ITRIGGER, ETRIGGER):
                return (slot.tdata1 >> (self.xlen - 6)) & 1
            return 0
        return bits(slot.tdata1, *spec)

    def set_hit(self, slot):
        kind = self.kind(slot)
        if kind in (ITRIGGER, ETRIGGER):
            slot.tdata1 |= 1 << (self.xlen - 6)
        elif kind in MC_FIELDS:
            slot.tdata1 = put(slot.tdata1, *MC_FIELDS[kind]['hit'], 1)

    # -- CSR interface -----------------------------------------------------------
    def read(self, address):
        if not self.slots:
            if address == 0x7a0:
                return 0
            raise _illegal()
        slot = self.slots[self.tselect]
        if address == 0x7a0:
            return self.tselect
        if address == 0x7a1:
            return slot.tdata1
        if address == 0x7a2:
            return slot.tdata2
        if address == 0x7a3:
            return 0
        if address == 0x7a4:
            mask = 0
            for kind in slot.types:
                mask |= 1 << kind
            return mask | (self.version << 24) if mask else 1
        if address == 0x7a5:
            if not self.has_tcontrol:
                raise _illegal()
            return self.tcontrol
        return self.mcontext

    def write(self, address, value, *, debug):
        if address == 0x7a0:
            if value < len(self.slots):
                self.tselect = value
            return
        if not self.slots:
            raise _illegal()
        slot = self.slots[self.tselect]
        if address == 0x7a5:
            if not self.has_tcontrol:
                raise _illegal()
            self.tcontrol = value & ((1 << 3) | (1 << 7))
            return
        if address == 0x7a8:
            self.mcontext = value & 0x1fff
            return
        if address == 0x7a4:
            return
        if self.dmode(slot) and not debug:
            return   # only Debug Mode writes a dmode trigger
        if address == 0x7a2:
            slot.tdata2 = value & self.hart.mask
        elif address == 0x7a1:
            slot.tdata1 = self.legalize(slot, value, debug)

    def legalize(self, slot, value, debug):
        xl = self.xlen
        kind = value >> (xl - 4)
        dmode = (value >> (xl - 5)) & 1 if debug else 0
        if kind not in slot.types:
            return self._make(self.unsupported, dmode if self.unsupported else 0, 0) if self.unsupported else 0
        modes = self.hart._modes_int()
        fields = {}
        for name, spec in MC_FIELDS[kind].items():
            fields[name] = bits(value, *spec)
        if kind in (ITRIGGER, ETRIGGER):
            fields['hit'] = (value >> (xl - 6)) & 1
        fields['vs'] = fields['vu'] = 0
        fields['nmi'] = 0
        if 1 not in modes:
            fields['s'] = 0
        if 0 not in modes:
            fields['u'] = 0
        action = fields.get('action', 0)
        if action not in self.actions or (action == 1 and not dmode):
            fields['action'] = 0
        if kind in (MCONTROL, MCONTROL6):
            if fields['match'] not in self.matches:
                fields['match'] = 0
            if fields['size'] not in self.sizes:
                fields['size'] = 0
            if kind == MCONTROL and fields['timing'] not in self.timings:
                fields['timing'] = 0
            last = self.slots.index(slot) == len(self.slots) - 1
            if not self.chain_ok or last:
                fields['chain'] = 0
        if kind == ICOUNT:
            fields['pending'] = 0
        result = self._make(kind, dmode, 0)
        for name, spec in MC_FIELDS[kind].items():
            result = put(result, *spec, fields.get(name, 0))
        if kind in (ITRIGGER, ETRIGGER) and fields['hit']:
            result |= 1 << (xl - 6)
        return result

    # -- matching ----------------------------------------------------------------
    def _value_match(self, slot, value):
        t2 = slot.tdata2
        xl = self.xlen
        half = xl // 2
        low = (1 << half) - 1
        match = self.field(slot, 'match')
        base = match & 7 if match >= 8 else match
        if base == 0:
            hit = value == t2
        elif base == 1:
            mask = t2 ^ (t2 + 1)
            hit = (value | mask) == (t2 | mask)
        elif base == 2:
            hit = value >= t2
        elif base == 3:
            hit = value < t2
        elif base == 4:
            hit = (value & (t2 >> half) & low) == (t2 & low & (t2 >> half))
        else:
            hit = ((value >> half) & (t2 >> half) & low) == (t2 & low & (t2 >> half))
        return not hit if match >= 8 else hit

    def _mode_ok(self, slot, mode):
        return bool(self.field(slot, {3: 'm', 1: 's', 0: 'u'}[mode]))

    def _fire(self, matched, after, *, before):
        """matched/after: per-slot flags for this event. Apply chains; return the action to take."""
        fired = None
        group = []
        for index, slot in enumerate(self.slots):
            group.append(index)
            if self.field(slot, 'chain') and self.kind(slot) in (MCONTROL, MCONTROL6):
                continue
            last = group[-1]
            if all(matched[i] for i in group) and after[last] == (not before):
                action = self.field(self.slots[last], 'action')
                if action == 0 and self.hart.mode == 3 and not (self.tcontrol >> 3) & 1:
                    group = []
                    continue   # M-mode breakpoint triggers need tcontrol.mte
                for i in group:
                    self.set_hit(self.slots[i])
                fired = 1 if 1 in (fired, action) else action
            group = []
        return fired

    def check_execute(self, pc):
        hart = self.hart
        self.exec_mode = hart.mode
        self.pending = []
        if hart.debug_mode or not self.slots:
            return
        matched = [self.kind(s) in (MCONTROL, MCONTROL6) and self.field(s, 'execute')
                   and not self.field(s, 'select') and self._mode_ok(s, hart.mode)
                   and self._value_match(s, pc) for s in self.slots]
        after = [self.kind(s) == MCONTROL and bool(self.field(s, 'timing')) for s in self.slots]
        action = self._fire(matched, after, before=True)
        if action is not None:
            self._act(action, pc, tval=pc)
        # A "timing after" execute match fires once the instruction retires.
        action = self._fire(matched, after, before=False)
        if action is not None:
            self.pending.append((action, pc))

    def _access_after(self, slot, store):
        if self.field(slot, 'select'):
            timing = self.profile.get('store_data_timing' if store else 'load_data_timing', 'after')
            return None if timing is None else timing == 'after'
        return self.kind(slot) == MCONTROL and bool(self.field(slot, 'timing'))

    def check_access(self, address, size, *, load=False, store=False, before=False, data=None):
        hart = self.hart
        size_bytes = size
        if hart.debug_mode or not self.slots:
            return
        after = []
        def hits(slot):
            after.append(self._access_after(slot, store) if self.kind(slot) in (MCONTROL, MCONTROL6) else False)
            if self.kind(slot) not in (MCONTROL, MCONTROL6) or not self._mode_ok(slot, hart.mode):
                return False
            if not ((load and self.field(slot, 'load')) or (store and self.field(slot, 'store'))):
                return False
            if after[-1] is None or after[-1] == before:
                return False
            size = self.field(slot, 'size')
            if size and {1: 1, 2: 2, 3: 4, 4: 6, 5: 8}.get(size) != size_bytes:
                return False   # size matching: the access must have the selected size
            value = data if self.field(slot, 'select') else address
            return value is not None and self._value_match(slot, value)
        matched = [hits(s) for s in self.slots]
        action = self._fire(matched, after, before=before)
        if action is None:
            return
        if before:
            self._act(action, hart.pc, tval=address)
        else:
            self.pending.append((action, address))

    def retired(self):
        mode = self.exec_mode
        for slot in self.slots:
            if self.kind(slot) != ICOUNT or not self._mode_ok(slot, mode):
                continue
            count = self.field(slot, 'count')
            if count == 0:
                continue
            count -= 1
            slot.tdata1 = put(slot.tdata1, *MC_FIELDS[ICOUNT]['count'], count)
            if count == 0:
                self.set_hit(slot)
                self.pending.append((self.field(slot, 'action'), self.hart.next_pc))

    def after(self):
        """Fire pending after-timing triggers. The hart pc already points at the next instruction."""
        pending, self.pending = self.pending, []
        if not pending:
            return
        action = 1 if any(a == 1 for a, _ in pending) else pending[0][0]
        if action == 1:
            from .hart import DebugEntry, CAUSE_TRIGGER
            raise DebugEntry(CAUSE_TRIGGER, self.hart.pc)
        hart = self.hart
        if hart.mode == 3 and not (self.tcontrol >> 3) & 1:
            return
        hart.take_trap(3, pending[0][1], hart.pc)

    def trap_taken(self, cause, *, interrupt):
        """Called after the hart entered the trap handler."""
        hart = self.hart
        mode = getattr(hart, 'trap_from', 3)
        for slot in self.slots:
            kind = self.kind(slot)
            if kind != (ITRIGGER if interrupt else ETRIGGER) or not self._mode_ok(slot, mode):
                continue
            if cause >= hart.xlen or not (slot.tdata2 >> cause) & 1:
                continue
            self.set_hit(slot)
            if self.field(slot, 'action') == 1:
                from .hart import DebugEntry, CAUSE_TRIGGER
                raise DebugEntry(CAUSE_TRIGGER, hart.pc)

    def _act(self, action, pc, tval):
        from .hart import DebugEntry, Trap, CAUSE_TRIGGER
        if action == 1:
            raise DebugEntry(CAUSE_TRIGGER, pc)
        raise Trap(3, tval)

    def on_trap(self):
        mte = (self.tcontrol >> 3) & 1
        self.tcontrol = (mte << 7)

    def on_mret(self):
        mpte = (self.tcontrol >> 7) & 1
        self.tcontrol = (self.tcontrol & (1 << 7)) | (mpte << 3)


def _illegal():
    from .hart import Trap, ILLEGAL
    return Trap(ILLEGAL)
