"""JTAG TAP and DTM conformance checks over any TCK transport (remote_bitbang or in-process).

The checks drive raw TMS/TDI and read TDO. They check every TAP state reaches
Test-Logic-Reset with five TMS=1 cycles, IR capture, IDCODE after reset, BYPASS,
DTMCS fields, DMI status, sticky busy, dmireset, dmihardreset and Pause-DR scans.
"""
from __future__ import annotations

import time

from .jtag import STATES, tms_path

IDCODE, DTMCS, DMI, BYPASS = 0x01, 0x10, 0x11, 0x1f


class TapError(AssertionError):
    pass


class Tap:
    def __init__(self, transport, irlen=5):
        self.t = transport
        self.irlen = irlen
        self.state = None

    def run(self, sequence):
        batch = getattr(self.t, 'clocks', None)
        if batch:
            return batch(sequence)
        return [self.t.clock(tms, tdi) for tms, tdi in sequence]

    def reset(self):
        self.run([(1, 0)] * 5 + [(0, 0)])
        self.state = 'RTI'

    def goto(self, state):
        path = tms_path(self.state, state)
        self.run([(t, 0) for t in path])
        self.state = state

    def shift(self, kind, value, bits, *, pause_at=None):
        """From RTI: shift `bits` through IR or DR and return to RTI. Optional Pause mid-scan."""
        self.goto('SHIFT_' + kind)
        tdo = []
        for bit in range(bits):
            last = bit == bits - 1
            if pause_at is not None and bit == pause_at:
                # Exit1 -> Pause -> Exit2 -> Shift, then continue.
                tdo += self.run([(1, (value >> bit) & 1)])
                self.run([(0, 0), (1, 0), (0, 0)])
                continue
            tdo += self.run([(int(last), (value >> bit) & 1)])
        self.run([(1, 0), (0, 0)])
        self.state = 'RTI'
        return sum(b << i for i, b in enumerate(tdo))

    def ir(self, value):
        return self.shift('IR', value, self.irlen)

    def dr(self, value, bits, **kw):
        return self.shift('DR', value, bits, **kw)

    def idle(self, count):
        if count:
            self.run([(0, 0)] * count)


def _dtmcs(tap):
    tap.ir(DTMCS)
    return tap.dr(0, 32)


def run(transport, *, irlen=5, idcode=None, busy_probe=True):
    """Return C3-style entries for the TAP/DTM checks."""
    tap = Tap(transport, irlen)
    entries = []

    def record(identifier, func):
        started = time.monotonic()
        entry = {'id': identifier, 'group': 'tap'}
        try:
            tap.reset()
            func()
            entry['status'] = 'pass'
        except TapError as exc:
            entry.update(status='fail', message=str(exc))
        except Inconclusive as exc:
            entry.update(status='inconclusive', reason=str(exc))
        except (OSError, ValueError) as exc:
            entry.update(status='inconclusive', reason=f'transport: {type(exc).__name__}: {exc}')
        entry['wall_s'] = round(time.monotonic() - started, 4)
        entries.append(entry)

    def expect(condition, message):
        if not condition:
            raise TapError(message)

    def reset_idcode():
        code = tap.dr(0, 32)
        expect(code & 1, f'IDCODE 0x{code:08x} after reset has bit 0 clear')
        if idcode is not None:
            expect(code == idcode, f'IDCODE 0x{code:08x}, declared 0x{idcode:08x}')

    def every_state_resets():
        reference = tap.dr(0, 32)
        for state in STATES:
            tap.reset()
            tap.ir(DTMCS)                  # move IR away from IDCODE
            tap.goto(state)
            tap.run([(1, 0)] * 5)
            tap.state = 'TLR'
            tap.goto('RTI')
            code = tap.dr(0, 32)
            expect(code == reference, f'five TMS=1 cycles from {state} did not reset the TAP')

    def ir_capture():
        captured = tap.ir(IDCODE)
        expect(captured & 3 == 1, f'IR capture 0b{captured:0{irlen}b}: two LSBs must be 01')

    def bypass():
        tap.ir((1 << irlen) - 1)
        pattern = 0b1011001110001111
        out = tap.dr(pattern, 17)
        expect(out & 1 == 0, 'BYPASS first bit is not 0')
        expect(out >> 1 == pattern, 'BYPASS does not delay data by one bit')

    def dtmcs_fields():
        value = _dtmcs(tap)
        expect(value & 15 == 1, f'dtmcs.version {value & 15}, expected 1')
        abits = (value >> 4) & 63
        expect(7 <= abits <= 32, f'dtmcs.abits {abits} out of range')
        expect((value >> 10) & 3 == 0, 'dtmcs.dmistat is not 0 after reset')

    def dmi_read_status():
        value = _dtmcs(tap)
        abits, idle = (value >> 4) & 63, (value >> 12) & 7
        tap.ir(DMI)
        width = abits + 34
        tap.dr((0x11 << 34) | 1, width)
        tap.idle(idle + 8)
        response = tap.dr(0, width)
        expect(response & 3 == 0, f'DMI read status {response & 3}')
        version = (response >> 2) & 15
        expect(version in (2, 3), f'dmstatus.version {version} through DMI')

    def paused_scan():
        value = _dtmcs(tap)
        abits, idle = (value >> 4) & 63, (value >> 12) & 7
        tap.ir(DMI)
        width = abits + 34
        tap.dr((0x11 << 34) | 1, width)
        tap.idle(idle + 8)
        plain = tap.dr((0x11 << 34) | 1, width)
        tap.idle(idle + 8)
        paused = tap.dr(0, width, pause_at=width // 2)
        # Hart state bits may change between reads; compare version and authenticated.
        expect((plain >> 2) & 0xff == (paused >> 2) & 0xff, 'Pause-DR changed the shifted DMI data')

    def sticky_busy():
        if not busy_probe:
            raise Inconclusive('busy probing disabled')
        value = _dtmcs(tap)
        abits = (value >> 4) & 63
        tap.ir(DMI)
        width = abits + 34
        tap.dr((0x11 << 34) | 1, width)
        status = tap.dr(0, width) & 3          # no Run-Test/Idle cycles: may be busy
        if status != 3:
            raise Inconclusive('the DTM completed the request with zero idle cycles; busy not observed')
        tap.idle(64)
        expect(tap.dr(0, width) & 3 == 3, 'busy status is not sticky')
        expect((_dtmcs(tap) >> 10) & 3 == 3, 'dtmcs.dmistat does not show busy')
        tap.ir(DTMCS)
        tap.dr(1 << 16, 32)                    # dmireset
        expect((_dtmcs(tap) >> 10) & 3 == 0, 'dmireset did not clear dmistat')
        tap.ir(DMI)
        tap.dr((0x11 << 34) | 1, width)
        tap.idle(64)
        expect(tap.dr(0, width) & 3 == 0, 'request after dmireset failed')

    def hardreset():
        value = _dtmcs(tap)
        abits = (value >> 4) & 63
        tap.ir(DMI)
        width = abits + 34
        tap.dr((0x11 << 34) | 1, width)
        tap.ir(DTMCS)
        tap.dr(1 << 17, 32)                    # dmihardreset
        after = _dtmcs(tap)
        expect((after >> 10) & 3 == 0, 'dmihardreset left dmistat set')
        tap.ir(DMI)
        tap.dr((0x11 << 34) | 1, width)
        tap.idle(64)
        expect(tap.dr(0, width) & 3 == 0, 'request after dmihardreset failed')

    for identifier, func in (('tap.reset_idcode', reset_idcode), ('tap.every_state_resets', every_state_resets),
                             ('tap.ir_capture', ir_capture), ('tap.bypass', bypass),
                             ('tap.dtmcs_fields', dtmcs_fields), ('tap.dmi_read', dmi_read_status),
                             ('tap.pause_dr', paused_scan), ('tap.sticky_busy', sticky_busy),
                             ('tap.dmihardreset', hardreset)):
        record(identifier, func)
    return entries


class Inconclusive(Exception):
    pass
