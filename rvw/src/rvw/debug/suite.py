"""Self-checking Debug Specification campaigns over any DMI driver.

Each check drives the target only through DMI. It asserts the spec rule and
records `observe()` values. The runner repeats the check on a fresh reference
model built from the same profile and compares the observations. Results are
a C3 suite (`rvw.results/1`). Options the profile does not declare are listed
as unsupported. A check that could not exercise its rule is inconclusive.
"""
from __future__ import annotations

from dataclasses import dataclass
import datetime as _dt
import json
from pathlib import Path
import time
import traceback

from . import dm as dmmod, dmi as dmimod, jtag
from .hart import Asm

SUITE = 'debug-compliance'
DMCONTROL, DMSTATUS, ABSTRACTCS, COMMAND, ABSTRACTAUTO = 0x10, 0x11, 0x16, 0x17, 0x18
DATA0, PROGBUF0, SBCS, SBADDRESS0, SBADDRESS1, SBDATA0, SBDATA1 = 0x04, 0x20, 0x38, 0x39, 0x3a, 0x3c, 0x3d
DCSR, DPC, MSTATUS, MTVEC, MEPC, MCAUSE, MIE, MIP = 0x7b0, 0x7b1, 0x300, 0x305, 0x341, 0x342, 0x304, 0x344
TSELECT, TDATA1, TDATA2, TINFO, TCONTROL = 0x7a0, 0x7a1, 0x7a2, 0x7a4, 0x7a5
S0, S1, A0, T0, T1 = 8, 9, 10, 5, 6
CODE, HANDLER, DATA, UCODE, IDLE = 0x000, 0x400, 0x800, 0xc00, 0x3fc


class Fail(AssertionError):
    pass


class Unsupported(Exception):
    pass


class Inconclusive(Exception):
    pass


@dataclass
class Check:
    id: str
    group: str
    func: object
    doc: str
    reference: bool = True


CHECKS: dict[str, Check] = {}


def check(identifier, reference=True):
    """Register a check. reference=False: timing-dependent, no reference-model comparison."""
    def wrap(func):
        CHECKS[identifier] = Check(identifier, identifier.split('.')[0], func, (func.__doc__ or '').strip(),
                                   reference)
        return func
    return wrap


def expect(condition, message):
    if not condition:
        raise Fail(message)


class Ctx:
    """DMI helpers shared by the checks. Only DMI accesses reach the target."""

    def __init__(self, dmi, profile, *, polls=None):
        self.dmi = dmi
        self.p = profile
        self.xlen = profile['xlen']
        self.polls = polls or 400
        self.hart = 0
        self.observations = {}
        self.accesses = 0

    # -- raw ---------------------------------------------------------------------
    def read(self, address):
        self.accesses += 1
        return self.dmi.read(address)

    def write(self, address, value):
        self.accesses += 1
        self.dmi.write(address, value & 0xffffffff)

    def observe(self, key, value):
        self.observations[key] = value

    def require(self, condition, reason):
        if not condition:
            raise Unsupported(reason)

    @property
    def scratch(self):
        if self.p['scratch'] is None:
            raise Unsupported('profile declares no scratch memory')
        return self.p['scratch']

    # -- dmcontrol ---------------------------------------------------------------
    def control(self, *, haltreq=0, resumereq=0, ackhavereset=0, ndmreset=0, hasel=0, extra=0, hart=None):
        hart = self.hart if hart is None else hart
        value = ((haltreq << 31) | (resumereq << 30) | (ackhavereset << 28) | (hasel << 26)
                 | ((hart & 0x3ff) << 16) | (((hart >> 10) & 0x3ff) << 6) | (ndmreset << 1) | 1 | extra)
        self.write(DMCONTROL, value)

    def status(self):
        return self.read(DMSTATUS)

    def poll(self, predicate, what):
        for _ in range(self.polls):
            value = predicate()
            if value:
                return value
        raise Fail(f'timeout waiting for {what}')

    def activate(self):
        self.write(DMCONTROL, 1)
        self.poll(lambda: self.read(DMCONTROL) & 1, 'dmactive')

    def select(self, hart):
        self.hart = hart
        self.control()

    def halted(self):
        return (self.status() >> 9) & 1

    def halt(self, hart=None):
        if hart is not None:
            self.hart = hart
        self.control(haltreq=1)
        self.poll(lambda: (self.status() >> 9) & 1, 'allhalted')
        self.control()

    def resume(self):
        self.control(resumereq=1)
        self.poll(lambda: (self.status() >> 17) & 1, 'allresumeack')
        self.control()

    def wait_halt(self, polls=None):
        """Wait for a halt the hart enters itself. Returns True when it halted."""
        for _ in range(polls or self.polls):
            if (self.status() >> 9) & 1:
                return True
        return False

    def prepare(self):
        """Common start state: active DM, hart 0 halted, no sticky errors, no reset flags."""
        self.activate()
        self.hart = 0
        self.control(ackhavereset=1)
        self.write(ABSTRACTCS, 0x700)
        self.write(ABSTRACTAUTO, 0)
        self.halt(0)
        try:
            self._prepare_hart()
        except Unsupported:
            pass   # no CSR path: checks that need one report unsupported themselves

    def _prepare_hart(self):
        if self.p['scratch'] is not None:
            # Fresh haltreq entry from a known idle loop, so no earlier check leaves its cause.
            self.set_csr(DPC, self.write_code(IDLE, [Asm.j(0)]))
            self.resume()
            self.halt()
        self.set_csr(DCSR, (self.csr(DCSR) & ~((1 << 2) | (7 << 12) | (1 << 15))) | 3 | (1 << 15))
        if self.p['triggers']['count']:
            for index in range(self.p['triggers']['count']):
                self.set_csr(TSELECT, index)
                self.set_csr(TDATA1, 0)
            self.set_csr(TSELECT, 0)

    # -- abstract commands -------------------------------------------------------
    def cmderr(self):
        return (self.read(ABSTRACTCS) >> 8) & 7

    def clear_cmderr(self):
        self.write(ABSTRACTCS, 0x700)

    def command(self, value, *, clear=True):
        self.write(COMMAND, value)
        cs = self.poll(lambda: (v := self.read(ABSTRACTCS)) & 0x1000 == 0 and (v | (1 << 31)), 'abstract busy=0')
        error = (cs >> 8) & 7
        if error and clear:
            self.clear_cmderr()
        return error

    def size_code(self):
        return 3 if self.xlen == 64 else 2

    def access_reg(self, regno, value=None, *, postexec=False, transfer=True, postinc=False, clear=True):
        if value is not None:
            self.write(DATA0, value & 0xffffffff)
            if self.xlen == 64:
                self.write(DATA0 + 1, (value >> 32) & 0xffffffff)
        command = ((self.size_code() << 20) | (int(postinc) << 19) | (int(postexec) << 18)
                   | (int(transfer) << 17) | (int(value is not None) << 16) | regno)
        error = self.command(command, clear=clear)
        if error or value is not None:
            return error, None
        result = self.read(DATA0)
        if self.xlen == 64:
            result |= self.read(DATA0 + 1) << 32
        return 0, result

    def reg(self, regno):
        error, value = self.access_reg(regno)
        expect(not error, f'abstract read of 0x{regno:x} failed with cmderr {error}')
        return value

    def set_reg(self, regno, value):
        error, _ = self.access_reg(regno, value)
        expect(not error, f'abstract write of 0x{regno:x} failed with cmderr {error}')

    def gpr(self, n):
        return self.reg(0x1000 + n)

    def set_gpr(self, n, value):
        self.set_reg(0x1000 + n, value)

    def csr(self, address):
        if 'csr' in self.p['abstract']:
            return self.reg(address)
        self._csr_path()
        saved = self.gpr(S1)
        error = self.exec_progbuf(Asm.csrrs(S1, address, 0))
        expect(not error, f'program-buffer CSR read of 0x{address:x} failed with cmderr {error}')
        value = self.gpr(S1)
        self.set_gpr(S1, saved)
        return value

    def set_csr(self, address, value):
        if 'csr' in self.p['abstract']:
            return self.set_reg(address, value)
        self._csr_path()
        saved = self.gpr(S1)
        self.set_gpr(S1, value)
        error = self.exec_progbuf(Asm.csrrw(0, address, S1))
        self.set_gpr(S1, saved)
        expect(not error, f'program-buffer CSR write of 0x{address:x} failed with cmderr {error}')
        return None

    def _csr_path(self):
        if 'gpr' not in self.p['abstract'] or self.p['progbufsize'] + int(self.p['impebreak']) < 2:
            raise Unsupported('no CSR access path (abstract CSR access or program buffer)')

    # -- program buffer ----------------------------------------------------------
    def progbuf(self, *words):
        """Write words (and an ebreak if room and no impebreak). Requires enough progbuf."""
        need = len(words) + (0 if self.p['impebreak'] else 1)
        self.require(self.p['progbufsize'] >= need, f'needs {need} program-buffer words')
        # Unused words hold ebreak, so no stale instruction from an earlier command runs.
        words = list(words) + [Asm.EBREAK] * (self.p['progbufsize'] - len(words))
        for index, word in enumerate(words):
            self.write(PROGBUF0 + index, word)

    def exec_progbuf(self, *words, clear=True):
        self.progbuf(*words)
        return self.command((self.size_code() << 20) | (1 << 18), clear=clear)

    # -- memory ------------------------------------------------------------------
    def mem_write(self, address, value, size=4, *, via=None):
        via = via or self.mem_path()
        if via == 'memory':
            self._abstract_mem(address, size, value)
        elif via == 'progbuf':
            saved = self.gpr(S0), self.gpr(S1)
            self.set_gpr(S0, address)
            self.set_gpr(S1, value)
            store = {1: Asm.sb, 4: Asm.sw, 8: Asm.sd}[size]
            error = self.exec_progbuf(store(S1, S0))
            self.set_gpr(S0, saved[0])
            self.set_gpr(S1, saved[1])
            expect(not error, f'program-buffer store failed with cmderr {error}')
        else:
            self.sba_write(address, value, size)

    def mem_read(self, address, size=4, *, via=None):
        via = via or self.mem_path()
        if via == 'memory':
            return self._abstract_mem(address, size)
        if via == 'progbuf':
            saved = self.gpr(S0), self.gpr(S1)
            self.set_gpr(S0, address)
            load = {4: Asm.lw, 8: Asm.ld}[size]
            error = self.exec_progbuf(load(S1, S0))
            value = self.gpr(S1) & ((1 << (8 * size)) - 1)
            self.set_gpr(S0, saved[0])
            self.set_gpr(S1, saved[1])
            expect(not error, f'program-buffer load failed with cmderr {error}')
            return value
        return self.sba_read(address, size)

    def mem_path(self):
        if 'memory' in self.p['abstract']:
            return 'memory'
        if self.p['progbufsize'] + int(self.p['impebreak']) >= 2:
            return 'progbuf'
        if self.p['sba']:
            return 'sba'
        raise Unsupported('no memory access path (abstract memory, program buffer or SBA)')

    def _abstract_mem(self, address, size, value=None):
        words = self.xlen // 32
        for i in range(words):
            self.write(DATA0 + words + i, (address >> (32 * i)) & 0xffffffff)
        if value is not None:
            self.write(DATA0, value & 0xffffffff)
            if size == 8:
                self.write(DATA0 + 1, value >> 32)
        code = {1: 0, 2: 1, 4: 2, 8: 3}[size]
        error = self.command((2 << 24) | (code << 20) | (int(value is not None) << 16))
        expect(not error, f'abstract memory access failed with cmderr {error}')
        if value is None:
            result = self.read(DATA0)
            if size == 8:
                result |= self.read(DATA0 + 1) << 32
            return result & ((1 << (8 * size)) - 1)
        return None

    def write_code(self, offset, words):
        base = self.scratch + offset
        for index, word in enumerate(words):
            self.mem_write(base + 4 * index, word, 4)
        if self.p['fence_i'] and self.p['progbufsize'] + int(self.p['impebreak']) >= 2:
            self.exec_progbuf(Asm.FENCE_I)
        return base

    def install_handler(self):
        """Trap handler at scratch+HANDLER: spin, so the debugger halts it (no ebreak recursion)."""
        base = self.write_code(HANDLER, [Asm.j(0)])
        self.set_csr(MTVEC, base)
        return base

    def run(self, words, *, offset=CODE, prv=3, regs=None, step=False, spin_halt=True, polls=None):
        """Load code, set dpc, resume and wait for a halt. Returns (cause, dpc)."""
        base = self.write_code(offset, words)
        for reg, value in (regs or {}).items():
            self.set_gpr(reg, value)
        self.set_csr(DPC, base)
        dcsr = self.csr(DCSR)
        dcsr = (dcsr & ~(3 | 4)) | prv | (int(step) << 2)
        self.set_csr(DCSR, dcsr)
        self.resume()
        if not self.wait_halt(polls):
            if not spin_halt:
                raise Fail('hart did not halt')
            self.halt()
        cause = (self.csr(DCSR) >> 6) & 7
        return cause, self.csr(DPC)

    def set_ebreak(self, m=1, s=0, u=0):
        dcsr = self.csr(DCSR) & ~((1 << 15) | (1 << 13) | (1 << 12))
        self.set_csr(DCSR, dcsr | (m << 15) | (s << 13) | (u << 12))

    # -- system bus --------------------------------------------------------------
    def sbcs(self, **fields):
        names = dict(busyerror=22, readonaddr=20, access=17, autoinc=16, readondata=15, error=12)
        value = 0
        for name, field in fields.items():
            value |= field << names[name]
        self.write(SBCS, value)

    def sb_wait(self):
        return self.poll(lambda: (v := self.read(SBCS)) & (1 << 21) == 0 and (v | (1 << 31)), 'sbbusy=0')

    def sba_write(self, address, value, size=4):
        self.sbcs(access={1: 0, 2: 1, 4: 2, 8: 3}[size], error=7, busyerror=1)
        self.write(SBADDRESS1, address >> 32) if self.p['sba']['asize'] > 32 else None
        self.write(SBADDRESS0, address & 0xffffffff)
        if size == 8:
            self.write(SBDATA1, value >> 32)
        self.write(SBDATA0, value & 0xffffffff)
        cs = self.sb_wait()
        expect((cs >> 12) & 7 == 0, f'SBA write error {(cs >> 12) & 7}')

    def sba_read(self, address, size=4):
        self.sbcs(access={1: 0, 2: 1, 4: 2, 8: 3}[size], readonaddr=1, error=7, busyerror=1)
        self.write(SBADDRESS1, address >> 32) if self.p['sba']['asize'] > 32 else None
        self.write(SBADDRESS0, address & 0xffffffff)
        cs = self.sb_wait()
        expect((cs >> 12) & 7 == 0, f'SBA read error {(cs >> 12) & 7}')
        value = self.read(SBDATA0)
        if size == 8:
            value |= self.read(SBDATA1) << 32
        return value


# -- targets -------------------------------------------------------------------
def model_driver(profile, *, jtag_level=False):
    module = dmmod.DebugModule(profile)
    bus = dmmod.ModelBus(module)
    if jtag_level:
        dtm = jtag.DTM(bus, latency=1, idle=0)
        return dmimod.JtagDMI(jtag.InProcessJtag(dtm)), module
    return dmimod.BusDMI(bus), module


def open_target(profile, *, log=None):
    transport = profile['transport']
    kind = transport['kind']
    if kind == 'model':
        return model_driver(profile)[0]
    if kind == 'jtag-model':
        return model_driver(profile, jtag_level=True)[0]
    if kind == 'remote_bitbang':
        return dmimod.RemoteDMI(transport['host'], transport['port'], irlen=transport.get('irlen', 5))
    return dmimod.BusDMI(dmimod.ProcessBus(transport['command'], log=log))


def run_one(item, profile, driver):
    ctx = Ctx(driver, profile)
    started = time.monotonic()
    entry = {'id': item.id, 'group': item.group}
    try:
        try:
            ctx.prepare()
        except Fail as exc:
            raise Fail(f'setup: {exc}') from None
        item.func(ctx)
        entry['status'] = 'pass'
    except Unsupported as exc:
        entry['status'] = 'unsupported'
        entry['reason'] = str(exc)
    except Inconclusive as exc:
        entry['status'] = 'inconclusive'
        entry['reason'] = str(exc)
    except Fail as exc:
        entry['status'] = 'fail'
        entry['message'] = str(exc)
    except (dmimod.DMIError, TimeoutError, OSError, ValueError) as exc:
        entry['status'] = 'inconclusive'
        entry['reason'] = f'transport: {type(exc).__name__}: {exc}'
    except Exception as exc:   # a broken check is a tool error, never a pass
        entry['status'] = 'inconclusive'
        entry['reason'] = 'check error: ' + ''.join(traceback.format_exception_only(type(exc), exc)).strip()
    entry['observations'] = ctx.observations
    entry['dmi_accesses'] = ctx.accesses
    entry['wall_s'] = round(time.monotonic() - started, 4)
    return entry


def select(groups=None, ids=None):
    chosen = [c for c in CHECKS.values()
              if (not groups or c.group in groups) and (not ids or c.id in ids)]
    return chosen


def run(profile, *, driver=None, groups=None, ids=None, reference=True, log=None):
    """Run the selected checks. Returns the result summary (not yet C3)."""
    from . import checks  # noqa: F401  (registers the checks)
    own = driver is None
    driver = driver or open_target(profile, log=log)
    entries = []
    try:
        for item in select(groups, ids):
            if item.id in profile['skip']:
                entries.append({'id': item.id, 'group': item.group, 'status': 'unsupported',
                                'reason': 'skipped by profile: ' + profile['skip'][item.id]})
                continue
            entry = run_one(item, profile, driver)
            if reference and item.reference and entry['status'] in ('pass', 'fail') and profile['transport']['kind'] != 'model':
                expected = run_one(item, profile, model_driver(profile)[0])
                entry['reference_status'] = expected['status']
                diff = {k: (v, expected['observations'].get(k)) for k, v in entry['observations'].items()
                        if expected['observations'].get(k) != v}
                missing = sorted(set(expected['observations']) - set(entry['observations']))
                if expected['status'] != 'pass':
                    entry['status'] = 'inconclusive'
                    entry['reason'] = f'reference model did not pass: {expected.get("message") or expected.get("reason")}'
                elif entry['status'] == 'pass' and (diff or missing):
                    entry['status'] = 'fail'
                    entry['message'] = 'observations differ from the reference model'
                entry['reference_diff'] = {k: list(v) for k, v in diff.items()}
            entries.append(entry)
    finally:
        if own:
            close = getattr(driver, 'close', None)
            if close:
                close()
    return entries


def to_c3(entries, profile, *, run_id=None):
    created = _dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    tests, unsupported = [], []
    for entry in entries:
        if entry['status'] == 'unsupported':
            unsupported.append({'id': entry['id'], 'reason': entry['reason']})
            continue
        test = {'id': entry['id'], 'wall_s': entry['wall_s'], 'group': entry['group'],
                'observations': entry['observations'], 'dmi_accesses': entry['dmi_accesses']}
        for key in ('reference_status', 'reference_diff'):
            if key in entry:
                test[key] = entry[key]
        if entry['status'] == 'pass':
            test['status'] = 'pass'
        elif entry['status'] == 'fail':
            test.update(status='fail', signature=f'debug:{entry["id"]}', message=entry['message'],
                        message_complete=True)
        else:
            test.update(status='error', signature='inconclusive', inconclusive=entry['reason'])
        tests.append(test)
    return {
        'schema': 'rvw.results/1', 'run_id': run_id or f'{created.replace(":", "-")}-{SUITE}',
        'suite': SUITE, 'core': profile['name'], 'config': f'debug-{profile["version"]}',
        'created': created, 'source': {'profile_sha256': profile.get('sha256')},
        'tests': tests, 'unsupported': unsupported,
        'transport': profile['transport']['kind'],
        'scope': 'declared debug profile options only; a reference-model pass is not core evidence',
    }


def verdict(results):
    tests = results['tests']
    if not tests:
        return 'no_checks', 3
    if any(t['status'] == 'fail' for t in tests):
        return 'fail', 1
    if any(t['status'] != 'pass' for t in tests):
        return 'inconclusive', 3
    return 'pass', 0


def write(results, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / 'results.json'
    path.write_text(json.dumps(results, indent=2, sort_keys=True) + '\n')
    return path
