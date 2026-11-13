"""Reference model of a RISC-V Debug Module (Debug 0.13.2 and 1.0 option sets).

The model is configured by a debug profile (`profile.py`). It implements DM
lifecycle, hart selection and arrays, halt groups, reset entry, abstract
register/memory/quick-access commands, the program buffer with autoexec,
system-bus access and the hart-side trigger module. It is a reference for
the compliance campaigns, not a statement about any core.
"""
from __future__ import annotations

from .hart import (Hart, Memory, Region, BusError, Trap, CAUSE_HALTREQ, CAUSE_STEP, CAUSE_RESETHALT,
                   CAUSE_GROUP)

DATA0, DMCONTROL, DMSTATUS, HARTINFO, HALTSUM1, HAWINDOWSEL, HAWINDOW = 0x04, 0x10, 0x11, 0x12, 0x13, 0x14, 0x15
ABSTRACTCS, COMMAND, ABSTRACTAUTO, NEXTDM, PROGBUF0, AUTHDATA, DMCS2 = 0x16, 0x17, 0x18, 0x1d, 0x20, 0x30, 0x32
HALTSUM2, HALTSUM3, SBCS, SBADDRESS0, SBADDRESS1, SBDATA0, SBDATA1, HALTSUM0 = 0x34, 0x35, 0x38, 0x39, 0x3a, 0x3c, 0x3d, 0x40

ERR_NONE, ERR_BUSY, ERR_UNSUPPORTED, ERR_EXCEPTION, ERR_HALTRESUME, ERR_BUS, ERR_OTHER = 0, 1, 2, 3, 4, 5, 7
PROGBUF_BASE = 0x00000800   # model-only fetch address of the program buffer

GPR, CSR_MAX, FPR = 0x1000, 0x0fff, 0x1020


class HartSlot:
    def __init__(self, hart, index):
        self.hart = hart
        self.index = index
        self.haltreq = False
        self.resumeack = False
        self.resume_pending = False
        self.havereset = True
        self.resethaltreq = False
        self.in_reset = False
        self.unavailable = False
        self.group = 0


class DebugModule:
    def __init__(self, profile):
        self.p = profile
        self.xlen = profile['xlen']
        self.version = 3 if profile['version'] == '1.0' else 2
        regions = [Region(**r) for r in profile['memory']]
        self.memory = Memory(regions)
        for address, data in profile.get('image', []):
            self.memory.load(address, data)
        if profile.get('idle_loop') and not profile.get('image'):
            try:
                self.memory.write(profile['reset_vector'], 4, 0x6f, source='init')   # j .
            except BusError:
                pass
        self.slots = []
        for i in range(profile['harts']):
            hart = Hart(self.memory, hartid=i, xlen=self.xlen, modes=profile['modes'],
                        reset_pc=profile['reset_vector'], trigger_profile=profile['triggers'])
            slot = HartSlot(hart, i)
            slot.unavailable = i in profile['unavailable']
            self.slots.append(slot)
        self.hartsellen = profile['hartsellen']
        self.datacount = profile['datacount']
        self.progbufsize = profile['progbufsize']
        self.ticks = 0
        self.reset_dm(power_on=True)

    # -- reset -------------------------------------------------------------------
    def reset_dm(self, power_on=False):
        self.dmactive = 0
        self.hartsel = 0
        self.hasel = 0
        self.hawindowsel = 0
        self.ndmreset = 0
        self.data = [0] * 12
        self.progbuf = [0] * 16
        self.command = 0
        self.cmderr = 0
        self.busy = 0
        self.abstractauto = 0
        self.sb = dict(busyerror=0, busy=0, readonaddr=0, access=2, autoinc=0, readondata=0, error=0,
                       address=0, data=0)
        for slot in self.slots:
            slot.haltreq = slot.resume_pending = False
            slot.hawindow = False
            slot.group = 0
            if power_on:
                slot.havereset = True

    def system_reset(self):
        for slot in self.slots:
            self.hart_reset(slot)

    def hart_reset(self, slot):
        slot.hart.reset()
        slot.havereset = True
        slot.resumeack = False
        slot.in_reset = False
        if slot.resethaltreq and self.p['resethaltreq'] and not slot.unavailable:
            slot.hart.enter_debug(CAUSE_RESETHALT, slot.hart.reset_pc)

    # -- hart selection ----------------------------------------------------------
    def selected(self):
        indices = {self.hartsel}
        if self.hasel and self.p['hart_array']:
            base = self.hawindowsel * 32
            indices |= {base + i for i in range(32) if (getattr(self, '_hawindow', 0) >> i) & 1}
        return sorted(indices)

    def state(self, index):
        if index >= len(self.slots):
            return 'nonexistent'
        slot = self.slots[index]
        if slot.unavailable or slot.in_reset:
            return 'unavailable'
        return 'halted' if slot.hart.debug_mode else 'running'

    def current(self):
        """The single hart selected by hartsel, for abstract commands."""
        if self.hartsel >= len(self.slots):
            return None
        return self.slots[self.hartsel]

    # -- DMI ---------------------------------------------------------------------
    def read(self, address):
        self.tick()
        if address != DMCONTROL and not self.dmactive and address != DMSTATUS:
            return 0
        if DATA0 <= address < DATA0 + 12:
            index = address - DATA0
            if index >= self.datacount:
                return 0
            if self.busy:
                self._set_err(ERR_BUSY)
                return self.data[index]
            value = self.data[index]
            if (self.abstractauto >> index) & 1:
                self.execute()
            return value
        if PROGBUF0 <= address < PROGBUF0 + 16:
            index = address - PROGBUF0
            if index >= self.progbufsize:
                return 0
            if self.busy:
                self._set_err(ERR_BUSY)
                return self.progbuf[index]
            value = self.progbuf[index]
            if (self.abstractauto >> (16 + index)) & 1:
                self.execute()
            return value
        if address == DMCONTROL:
            return self.read_dmcontrol()
        if address == DMSTATUS:
            return self.read_dmstatus()
        if address == HARTINFO:
            return 1 << 20   # nscratch=1, no memory-mapped data registers
        if address == ABSTRACTCS:
            return ((self.progbufsize << 24) | ((1 if self.busy else 0) << 12) | (self.cmderr << 8)
                    | self.datacount)
        if address == COMMAND:
            return 0
        if address == ABSTRACTAUTO:
            return self.abstractauto
        if address == HAWINDOWSEL:
            return self.hawindowsel if self.p['hart_array'] else 0
        if address == HAWINDOW:
            return getattr(self, '_hawindow', 0) if self.p['hart_array'] else 0
        if address == HALTSUM0:
            base = self.hartsel & ~31
            return sum(1 << i for i in range(32) if self.state(base + i) == 'halted')
        if address == HALTSUM1:
            base = self.hartsel & ~0x3ff
            return sum(1 << g for g in range(32)
                       if any(self.state(base + g * 32 + i) == 'halted' for i in range(32)))
        if address == DMCS2:
            if not self.p['haltgroups']:
                return 0
            slot = self.current()
            return (slot.group << 2) if slot else 0
        if address == SBCS:
            return self.read_sbcs()
        if address in (SBADDRESS0, SBADDRESS1):
            return (self.sb['address'] >> (32 * (address - SBADDRESS0))) & 0xffffffff
        if address in (SBDATA0, SBDATA1):
            return self.read_sbdata(address - SBDATA0)
        return 0

    def write(self, address, value):
        self.tick()
        value &= 0xffffffff
        if address == DMCONTROL:
            return self.write_dmcontrol(value)
        if not self.dmactive:
            return None
        if DATA0 <= address < DATA0 + 12:
            index = address - DATA0
            if index < self.datacount:
                if self.busy:
                    return self._set_err(ERR_BUSY)
                self.data[index] = value
                if (self.abstractauto >> index) & 1:
                    self.execute()
        elif PROGBUF0 <= address < PROGBUF0 + 16:
            index = address - PROGBUF0
            if index < self.progbufsize:
                if self.busy:
                    return self._set_err(ERR_BUSY)
                self.progbuf[index] = value
                if (self.abstractauto >> (16 + index)) & 1:
                    self.execute()
        elif address == ABSTRACTCS:
            self.cmderr &= ~((value >> 8) & 7)
        elif address == COMMAND:
            if self.busy:
                return self._set_err(ERR_BUSY)
            self.command = value
            self.execute()
        elif address == ABSTRACTAUTO:
            if self.busy:
                return self._set_err(ERR_BUSY)
            mask = ((1 << self.datacount) - 1) | (((1 << self.progbufsize) - 1) << 16)
            self.abstractauto = value & mask if self.p['autoexec'] else 0
        elif address == HAWINDOWSEL and self.p['hart_array']:
            self.hawindowsel = value & 0x7fff
        elif address == HAWINDOW and self.p['hart_array']:
            self._hawindow = value & sum(1 << i for i in range(32)
                                         if self.hawindowsel * 32 + i < len(self.slots))
        elif address == DMCS2 and self.p['haltgroups']:
            if value & 2 and not value & 1:
                for index in self.selected():
                    if index < len(self.slots):
                        self.slots[index].group = (value >> 2) & 31
        elif address == SBCS:
            self.write_sbcs(value)
        elif address in (SBADDRESS0, SBADDRESS1):
            self.write_sbaddress(address - SBADDRESS0, value)
        elif address in (SBDATA0, SBDATA1):
            self.write_sbdata(address - SBDATA0, value)
        return None

    def _set_err(self, error):
        if self.cmderr == 0:
            self.cmderr = error

    # -- dmcontrol / dmstatus ----------------------------------------------------
    def read_dmcontrol(self):
        if not self.dmactive:
            return 0
        hartsel = self.hartsel
        value = ((hartsel & 0x3ff) << 16) | (((hartsel >> 10) & 0x3ff) << 6) | (self.ndmreset << 1) | 1
        if self.hasel and self.p['hart_array']:
            value |= 1 << 26
        return value

    def write_dmcontrol(self, value):
        active = value & 1
        if not active:
            if self.dmactive:
                self.reset_dm()
            self.dmactive = 0
            return
        self.dmactive = 1
        hartsel = (((value >> 6) & 0x3ff) << 10) | ((value >> 16) & 0x3ff)
        self.hartsel = hartsel & ((1 << self.hartsellen) - 1)
        self.hasel = (value >> 26) & 1 if self.p['hart_array'] else 0
        selected = [self.slots[i] for i in self.selected() if i < len(self.slots)]
        if (value >> 28) & 1:            # ackhavereset
            for slot in selected:
                slot.havereset = False
        if self.p['resethaltreq']:
            if (value >> 3) & 1:
                for slot in selected:
                    slot.resethaltreq = True
            if (value >> 2) & 1:
                for slot in selected:
                    slot.resethaltreq = False
        haltreq = (value >> 31) & 1
        for slot in selected:
            slot.haltreq = bool(haltreq)
        if (value >> 30) & 1 and not haltreq:      # resumereq is ignored while haltreq is set
            for slot in selected:
                if slot.hart.debug_mode and self.state(slot.index) == 'halted':
                    slot.resumeack = False
                    slot.resume_pending = True
        if self.p['hartreset'] and (value >> 29) & 1:
            for slot in selected:
                slot.in_reset = True
        elif self.p['hartreset']:
            for slot in selected:
                if slot.in_reset:
                    self.hart_reset(slot)
        ndmreset = (value >> 1) & 1
        if ndmreset and not self.ndmreset:
            for slot in self.slots:
                slot.in_reset = True
        if not ndmreset and self.ndmreset:
            self.system_reset()
        self.ndmreset = ndmreset
        return None

    def read_dmstatus(self):
        states = [self.state(i) for i in self.selected()]
        slots = [self.slots[i] for i in self.selected() if i < len(self.slots)]
        def flags(name, low):
            present = [s for s in states]
            anyv = any(s == name for s in present)
            allv = bool(present) and all(s == name for s in present)
            return (int(allv) << (low + 1)) | (int(anyv) << low)
        value = self.version | (1 << 7)          # authenticated
        if self.p['resethaltreq']:
            value |= 1 << 5
        if self.p['impebreak']:
            value |= 1 << 22
        value |= flags('halted', 8) | flags('running', 10) | flags('unavailable', 12) | flags('nonexistent', 14)
        if slots:
            value |= (int(all(s.resumeack for s in slots)) << 17) | (int(any(s.resumeack for s in slots)) << 16)
            value |= (int(all(s.havereset for s in slots)) << 19) | (int(any(s.havereset for s in slots)) << 18)
        return value

    # -- time --------------------------------------------------------------------
    def tick(self, count=None):
        for _ in range(self.p['ticks_per_access'] if count is None else count):
            self.ticks += 1
            if self.busy:
                self.busy -= 1
            if self.sb['busy']:
                self.sb['busy'] -= 1
            halted_now = []
            for slot in self.slots:
                if self.state(slot.index) == 'unavailable':
                    continue
                hart = slot.hart
                if hart.debug_mode:
                    if slot.resume_pending:
                        slot.resume_pending = False
                        hart.leave_debug()
                        slot.resumeack = True
                        if (hart.dcsr >> 2) & 1:
                            hart.stepping = True
                            cause = hart.step()
                            hart.stepping = False
                            if cause is None and not hart.debug_mode:
                                hart.enter_debug(CAUSE_STEP, hart.pc)
                            halted_now.append(slot)
                    continue
                if slot.haltreq:
                    hart.enter_debug(CAUSE_HALTREQ, hart.pc)
                    halted_now.append(slot)
                    continue
                for _ in range(self.p['ips']):
                    if hart.step() is not None:
                        halted_now.append(slot)
                        break
            if self.p['haltgroups']:
                for slot in halted_now:
                    if slot.group:
                        for other in self.slots:
                            if (other.group == slot.group and not other.hart.debug_mode
                                    and self.state(other.index) == 'running'):
                                other.hart.enter_debug(CAUSE_GROUP, other.hart.pc)

    # -- abstract commands -------------------------------------------------------
    def execute(self):
        if self.cmderr:
            return
        command = self.command
        cmdtype = command >> 24
        slot = self.current()
        self.busy = self.p['abstract_latency']
        if cmdtype == 0:
            self.access_register(slot, command)
        elif cmdtype == 1 and 'quick' in self.p['abstract']:
            self.quick_access(slot)
        elif cmdtype == 2 and 'memory' in self.p['abstract']:
            self.access_memory(slot, command)
        else:
            self._set_err(ERR_UNSUPPORTED)

    def _arg(self, index, width):
        words = width // 32
        value = 0
        for i in range(words):
            value |= self.data[index * words + i] << (32 * i)
        return value

    def _set_arg(self, index, width, value):
        words = width // 32
        for i in range(words):
            self.data[index * words + i] = (value >> (32 * i)) & 0xffffffff

    def access_register(self, slot, command):
        size = (command >> 20) & 7
        postinc, postexec, transfer, write = (command >> 19) & 1, (command >> 18) & 1, (command >> 17) & 1, (command >> 16) & 1
        regno = command & 0xffff
        if slot is None or self.state(slot.index) != 'halted':
            return self._set_err(ERR_HALTRESUME)
        if postinc and not self.p['postincrement']:
            return self._set_err(ERR_UNSUPPORTED)
        if transfer:
            width = {2: 32, 3: 64, 4: 128}.get(size)
            if width is None or width > self.xlen or size not in self.p['aarsizes']:
                return self._set_err(ERR_UNSUPPORTED)
            hart = slot.hart
            if GPR <= regno < GPR + 32:
                if 'gpr' not in self.p['abstract']:
                    return self._set_err(ERR_UNSUPPORTED)
                if write:
                    value = self._arg(0, width)
                    hart.setx(regno - GPR, value if width == self.xlen else _sext32(value, self.xlen))
                else:
                    self._set_arg(0, width, hart.x[regno - GPR])
            elif regno <= CSR_MAX:
                if 'csr' not in self.p['abstract']:
                    return self._set_err(ERR_UNSUPPORTED)
                try:
                    if write:
                        hart.write_csr(regno, self._arg(0, width), debugger=True)
                    else:
                        self._set_arg(0, width, hart.read_csr(regno, debugger=True))
                except Trap:
                    return self._set_err(self.p['csr_missing_cmderr'])
            else:
                return self._set_err(ERR_UNSUPPORTED)   # FPRs and custom registers are not modeled
        if postinc:
            self.command = (command & ~0xffff) | ((regno + 1) & 0xffff)
        if postexec:
            self.run_progbuf(slot)

    def run_progbuf(self, slot):
        words = self.progbuf[:self.progbufsize]
        if self.p['impebreak']:
            words = words + [0x00100073]
        hart = slot.hart
        saved_pc = hart.pc
        error = hart.run_debug(words, PROGBUF_BASE)
        hart.pc = saved_pc
        if error is not None:
            self._set_err(ERR_EXCEPTION)

    def quick_access(self, slot):
        if slot is None or self.state(slot.index) != 'running':
            return self._set_err(ERR_HALTRESUME)
        hart = slot.hart
        hart.enter_debug(CAUSE_HALTREQ, hart.pc)
        dcsr = hart.dcsr
        self.run_progbuf(slot)
        hart.dcsr = dcsr
        hart.leave_debug()

    def access_memory(self, slot, command):
        size = (command >> 20) & 7
        virtual, postinc, write = (command >> 23) & 1, (command >> 19) & 1, (command >> 16) & 1
        if slot is None or self.state(slot.index) != 'halted':
            return self._set_err(ERR_HALTRESUME)
        if virtual or size > 3 or (8 << size) > self.xlen:
            return self._set_err(ERR_UNSUPPORTED)
        nbytes = 1 << size
        address = self._arg(1, self.xlen)
        if address % nbytes:
            return self._set_err(ERR_BUS)
        try:
            if write:
                self.memory.write(address, nbytes, self._arg(0, max(32, nbytes * 8)) & ((1 << (8 * nbytes)) - 1),
                                  source='abstract')
            else:
                self._set_arg(0, max(32, nbytes * 8), self.memory.read(address, nbytes, source='abstract'))
        except BusError:
            return self._set_err(ERR_BUS)
        if postinc:
            self._set_arg(1, self.xlen, (address + nbytes) & ((1 << self.xlen) - 1))
        return None

    # -- system bus --------------------------------------------------------------
    def read_sbcs(self):
        if not self.p['sba']:
            return 0
        sb = self.sb
        sizes = sum(1 << {8: 0, 16: 1, 32: 2, 64: 3, 128: 4}[s] for s in self.p['sba']['sizes'])
        return ((1 << 29) | (sb['busyerror'] << 22) | ((1 if sb['busy'] else 0) << 21) | (sb['readonaddr'] << 20)
                | (sb['access'] << 17) | (sb['autoinc'] << 16) | (sb['readondata'] << 15) | (sb['error'] << 12)
                | (self.p['sba']['asize'] << 5) | sizes)

    def write_sbcs(self, value):
        if not self.p['sba']:
            return
        sb = self.sb
        if (value >> 22) & 1:
            sb['busyerror'] = 0
        sb['error'] &= ~((value >> 12) & 7)
        sb['readonaddr'] = (value >> 20) & 1
        sb['access'] = (value >> 17) & 7
        sb['autoinc'] = (value >> 16) & 1
        sb['readondata'] = (value >> 15) & 1

    def _sb_blocked(self):
        sb = self.sb
        if sb['busy']:
            sb['busyerror'] = 1
            return True
        return bool(sb['busyerror'] or sb['error'])

    def write_sbaddress(self, index, value):
        if not self.p['sba'] or self._sb_blocked():
            return
        shift = 32 * index
        if shift >= self.p['sba']['asize']:
            return
        sb = self.sb
        sb['address'] = ((sb['address'] & ~(0xffffffff << shift)) | (value << shift)) & ((1 << self.p['sba']['asize']) - 1)
        if index == 0 and sb['readonaddr']:
            self._sb_access(write=False)

    def write_sbdata(self, index, value):
        if not self.p['sba'] or self._sb_blocked():
            return
        sb = self.sb
        sb['data'] = (sb['data'] & ~(0xffffffff << (32 * index))) | (value << (32 * index))
        if index == 0:
            self._sb_access(write=True)

    def read_sbdata(self, index):
        if not self.p['sba']:
            return 0
        sb = self.sb
        value = (sb['data'] >> (32 * index)) & 0xffffffff
        if self._sb_blocked():
            return value
        if index == 0 and sb['readondata']:
            self._sb_access(write=False)
        return value

    def _sb_access(self, *, write):
        sb = self.sb
        bits = 8 << sb['access']
        if bits not in self.p['sba']['sizes']:
            sb['error'] = self.p['sba']['size_error']
            return
        nbytes = bits // 8
        if sb['address'] % nbytes:
            sb['error'] = self.p['sba']['misaligned_error']
            return
        try:
            if write:
                self.memory.write(sb['address'], nbytes, sb['data'] & ((1 << bits) - 1), source='sba')
            else:
                sb['data'] = self.memory.read(sb['address'], nbytes, source='sba')
        except BusError as error:
            sb['error'] = error.sberror
            return
        sb['busy'] = self.p['sba']['latency']
        if sb['autoinc']:
            sb['address'] = (sb['address'] + nbytes) & ((1 << self.p['sba']['asize']) - 1)


def _sext32(value, xlen):
    value &= 0xffffffff
    if value >> 31:
        value |= ((1 << xlen) - 1) & ~0xffffffff
    return value


class ModelBus:
    """DMI bus over a model Debug Module: op 1 read, op 2 write. Never busy at DMI level."""

    def __init__(self, dm):
        self.dm = dm

    def dmi(self, op, address, data):
        if op == 1:
            return 0, self.dm.read(address)
        if op == 2:
            self.dm.write(address, data)
            return 0, 0
        return 0, 0
