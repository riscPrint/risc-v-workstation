"""Debug Specification checks. Each docstring names the rule it tests."""
from __future__ import annotations

from .hart import Asm
from .suite import (check, expect, Fail, Inconclusive, CODE, HANDLER, DATA, UCODE, S0, S1, A0, T0, T1,
                    DMCONTROL, DMSTATUS, ABSTRACTCS, COMMAND, ABSTRACTAUTO, DATA0, PROGBUF0,
                    SBCS, SBADDRESS0, SBADDRESS1, SBDATA0, SBDATA1, DCSR, DPC, MSTATUS, MTVEC, MEPC, MCAUSE,
                    MIE, MIP, TSELECT, TDATA1, TDATA2, TINFO, TCONTROL)

HALTSUM0, DMCS2, HAWINDOWSEL, HAWINDOW = 0x40, 0x32, 0x14, 0x15
ADDI8 = [Asm.addi(S0, S0, 1)] * 8


def cause_of(ctx):
    return (ctx.csr(DCSR) >> 6) & 7


def bit(value, n):
    return (value >> n) & 1


# ============================================================================ DM lifecycle (#127)
@check('dm.dmactive_reset')
def dmactive_reset(ctx):
    """dmactive=0 resets the DM: dmcontrol and data registers return to reset values."""
    ctx.write(DATA0, 0x5a5a5a5a)
    ctx.write(DMCONTROL, 0)
    value = ctx.read(DMCONTROL)
    expect(value & 1 == 0, 'dmactive still reads 1 after writing 0')
    ctx.activate()
    expect(ctx.read(DATA0) == 0, 'data0 kept its value across dmactive=0')
    expect((ctx.read(ABSTRACTCS) >> 8) & 7 == 0, 'cmderr not reset by dmactive=0')
    ctx.observe('data0_after_reset', 0)


@check('dm.version')
def version(ctx):
    """dmstatus.version matches the declared Debug Specification version; authenticated is 1."""
    status = ctx.status()
    want = 3 if ctx.p['version'] == '1.0' else 2
    expect(status & 15 == want, f'dmstatus.version {status & 15}, declared {want}')
    expect(bit(status, 7), 'dmstatus.authenticated is 0 (authentication is not in the profile)')
    expect(bit(status, 22) == int(ctx.p['impebreak']), 'dmstatus.impebreak differs from the profile')
    expect(bit(status, 5) == int(ctx.p['resethaltreq']), 'dmstatus.hasresethaltreq differs from the profile')
    ctx.observe('version', status & 15)


@check('dm.hartsellen')
def hartsellen(ctx):
    """hartsel is WARL: writing all ones reads back the implemented HARTSELLEN bits."""
    ctx.write(DMCONTROL, (0x3ff << 16) | (0x3ff << 6) | 1)
    value = ctx.read(DMCONTROL)
    hartsel = ((value >> 16) & 0x3ff) | (((value >> 6) & 0x3ff) << 10)
    width = hartsel.bit_length()
    expect(hartsel == (1 << width) - 1, f'hartsel readback 0x{hartsel:x} is not a low mask')
    expect(width == ctx.p['hartsellen'], f'HARTSELLEN {width}, declared {ctx.p["hartsellen"]}')
    expect(width >= max(1, (ctx.p['harts'] - 1).bit_length()), 'hartsel cannot address every hart')
    ctx.select(0)
    ctx.observe('hartsellen', width)


@check('dm.hart_enumeration')
def hart_enumeration(ctx):
    """Every declared hart exists; the first index past them reports allnonexistent."""
    harts = ctx.p['harts']
    for index in range(min(harts, 64)):
        ctx.select(index)
        expect(not bit(ctx.status(), 14), f'hart {index} reports nonexistent')
    if harts < 1 << ctx.p['hartsellen']:
        ctx.select(harts)
        status = ctx.status()
        expect(bit(status, 15) and bit(status, 14), f'hart {harts} does not report allnonexistent')
        expect(not bit(status, 9) and not bit(status, 11), 'a nonexistent hart reports halted or running')
    ctx.select(0)
    ctx.observe('harts', harts)


@check('dm.halt')
def halt(ctx):
    """haltreq halts a running hart: allhalted, not running, dcsr.cause=haltreq."""
    ctx.resume()
    status = ctx.status()
    expect(bit(status, 11) and not bit(status, 9), 'hart not running after resume')
    ctx.halt()
    status = ctx.status()
    expect(bit(status, 9) and bit(status, 8) and not bit(status, 10), 'dmstatus does not show halted')
    expect(cause_of(ctx) == 3, f'dcsr.cause {cause_of(ctx)}, expected 3 (haltreq)')
    ctx.observe('cause', 3)


@check('dm.halt_stops_execution')
def halt_stops_execution(ctx):
    """Independent hart-state observer: a halted hart stops changing memory; a resumed hart changes it."""
    counter = ctx.scratch + DATA
    ctx.mem_write(counter, 0)
    loop = [Asm.lw(T0, A0), Asm.addi(T0, T0, 1), Asm.sw(T0, A0), Asm.j(-12)]
    base = ctx.write_code(CODE, loop)
    ctx.set_gpr(A0, counter)
    ctx.set_csr(DPC, base)
    ctx.resume()
    for _ in range(20):
        ctx.status()
    ctx.halt()
    first = ctx.mem_read(counter)
    for _ in range(20):
        ctx.status()
    second = ctx.mem_read(counter)
    expect(first == second, 'memory changed while dmstatus reported halted')
    expect(first > 0, 'counter did not advance while dmstatus reported running')
    ctx.resume()
    for _ in range(20):
        ctx.status()
    ctx.halt()
    expect(ctx.mem_read(counter) > second, 'counter did not advance after resume')


@check('dm.resume')
def resume(ctx):
    """resumereq resumes a halted hart: allresumeack and allrunning."""
    ctx.resume()
    status = ctx.status()
    expect(bit(status, 17) and bit(status, 16), 'resumeack not set')
    expect(bit(status, 11) and not bit(status, 9), 'hart not running after resumereq')
    ctx.halt()


@check('dm.resume_ignored_with_haltreq')
def resume_with_haltreq(ctx):
    """resumereq is ignored while haltreq is set in the same write."""
    ctx.control(haltreq=1, resumereq=1)
    for _ in range(10):
        ctx.status()
    ctx.control()
    expect(ctx.halted(), 'hart resumed although haltreq was set')


@check('dm.haltreq_while_halted')
def haltreq_while_halted(ctx):
    """haltreq on a halted hart leaves dpc and dcsr.cause unchanged."""
    dpc = ctx.csr(DPC)
    ctx.halt()
    expect(ctx.csr(DPC) == dpc, 'dpc changed on a second haltreq')
    expect(cause_of(ctx) == 3, 'dcsr.cause changed on a second haltreq')


@check('dm.unavailable')
def unavailable(ctx):
    """A declared unavailable hart reports anyunavail and cannot halt."""
    ctx.require(ctx.p['unavailable'], 'profile declares no unavailable hart')
    index = ctx.p['unavailable'][0]
    ctx.select(index)
    status = ctx.status()
    expect(bit(status, 12) and bit(status, 13), 'anyunavail/allunavail not set')
    ctx.control(haltreq=1)
    for _ in range(10):
        ctx.status()
    expect(not bit(ctx.status(), 9), 'an unavailable hart reports halted')
    ctx.control()
    ctx.select(0)
    ctx.observe('unavailable', index)


@check('dm.ndmreset')
def ndmreset(ctx):
    """ndmreset resets the system: havereset sets for the hart; ackhavereset clears it."""
    ctx.control(ndmreset=1)
    ctx.control(ndmreset=0)
    status = ctx.poll(lambda: (v := ctx.status()) & (1 << 18) and v, 'anyhavereset after ndmreset')
    expect(bit(status, 19), 'allhavereset not set')
    ctx.control(ackhavereset=1)
    expect(not bit(ctx.status(), 18), 'ackhavereset did not clear havereset')
    ctx.halt()


@check('dm.reset_halt')
def reset_halt(ctx):
    """setresethaltreq halts the hart out of reset with dcsr.cause=5 at the reset vector."""
    ctx.require(ctx.p['resethaltreq'], 'profile declares no resethaltreq')
    ctx.control(extra=1 << 3)               # setresethaltreq
    ctx.control(ndmreset=1)
    ctx.control(ndmreset=0)
    ctx.poll(lambda: (ctx.status() >> 9) & 1, 'halt out of reset')
    cause = cause_of(ctx)
    dpc = ctx.csr(DPC)
    ctx.control(extra=1 << 2)               # clrresethaltreq
    ctx.control(ackhavereset=1)
    expect(cause == 5, f'dcsr.cause {cause}, expected 5 (resethaltreq)')
    expect(dpc == ctx.p['reset_vector'], f'dpc 0x{dpc:x}, expected reset vector 0x{ctx.p["reset_vector"]:x}')
    ctx.observe('dpc', dpc)
    ctx.observe('cause', cause)


@check('dm.hartreset')
def hartreset(ctx):
    """hartreset resets the selected hart only: havereset sets."""
    ctx.require(ctx.p['hartreset'], 'profile declares no hartreset')
    ctx.control(extra=1 << 29)
    ctx.control()
    ctx.poll(lambda: (ctx.status() >> 18) & 1, 'havereset after hartreset')
    ctx.control(ackhavereset=1)
    ctx.halt()


@check('dm.haltsum0')
def haltsum0(ctx):
    """haltsum0 bit i is set exactly for halted harts in the window."""
    harts = min(ctx.p['harts'], 32)
    if harts > 1:
        ctx.select(1)
        if not ctx.halted():
            pass
    ctx.select(0)
    summary = ctx.read(HALTSUM0)
    expect(summary & 1, 'haltsum0 bit 0 clear for a halted hart')
    for index in range(1, harts):
        ctx.select(index)
        state = ctx.halted()
        ctx.select(0)
        expect(bit(ctx.read(HALTSUM0), index) == state, f'haltsum0 bit {index} disagrees with hart state')


@check('dm.multi_hart_independent')
def multi_hart_independent(ctx):
    """Halting hart 0 does not halt hart 1 outside a halt group."""
    ctx.require(ctx.p['harts'] >= 2, 'needs two harts')
    ctx.select(1)
    if ctx.halted():
        ctx.resume()
    ctx.select(0)
    ctx.halt()
    ctx.select(1)
    expect(not ctx.halted(), 'hart 1 halted with hart 0')
    ctx.halt()
    ctx.resume()
    ctx.select(0)


@check('dm.hart_array')
def hart_array(ctx):
    """hasel with hawindow selects several harts: one haltreq halts all of them."""
    ctx.require(ctx.p['hart_array'] and ctx.p['harts'] >= 2, 'profile declares no hart array mask')
    count = min(ctx.p['harts'], 32)
    ctx.write(HAWINDOWSEL, 0)
    ctx.write(HAWINDOW, (1 << count) - 1)
    ctx.control(hasel=1, resumereq=1)
    ctx.poll(lambda: (ctx.status() >> 11) & 1, 'allrunning')
    ctx.control(hasel=1, haltreq=1)
    ctx.poll(lambda: (ctx.status() >> 9) & 1, 'allhalted')
    ctx.control(hasel=1)
    ctx.control()
    for index in range(count):
        ctx.select(index)
        expect(ctx.halted(), f'hart {index} in the window did not halt')
    ctx.select(0)


@check('dm.halt_groups')
def halt_groups(ctx):
    """Harts in one halt group halt together; the other hart reports dcsr.cause=6."""
    ctx.require(ctx.p['haltgroups'] and ctx.p['harts'] >= 2, 'profile declares no halt groups')
    for index in (0, 1):
        ctx.select(index)
        ctx.write(DMCS2, (1 << 2) | 2)
        if ctx.halted():
            ctx.resume()
    ctx.select(0)
    ctx.halt()
    ctx.select(1)
    ctx.poll(lambda: ctx.halted(), 'group member halt')
    expect(cause_of(ctx) == 6, f'dcsr.cause {cause_of(ctx)}, expected 6 (group)')
    for index in (0, 1):
        ctx.select(index)
        ctx.write(DMCS2, 2)
    ctx.select(0)


# ============================================================================ abstract commands (#153)
@check('abs.gpr_roundtrip')
def gpr_roundtrip(ctx):
    """Access Register reads back every GPR written; x0 stays zero."""
    ctx.require('gpr' in ctx.p['abstract'], 'profile declares no abstract GPR access')
    mask = (1 << ctx.xlen) - 1
    for n in range(1, 32):
        value = (0x0123456789abcdef * n) & mask
        ctx.set_gpr(n, value)
        expect(ctx.gpr(n) == value, f'x{n} readback differs')
    ctx.set_gpr(0, 0x1234)
    expect(ctx.gpr(0) == 0, 'x0 is not zero after a write')
    if ctx.xlen == 64 and 2 in ctx.p['aarsizes']:
        ctx.set_gpr(S0, 0x1122334455667788)
        error = ctx.command((2 << 20) | (1 << 17) | 0x1008)
        expect(not error, f'32-bit GPR read failed with cmderr {error}')
        expect(ctx.read(DATA0) == 0x55667788, '32-bit read does not return the low word')
    ctx.observe('x0', 0)


@check('abs.csr_roundtrip')
def csr_roundtrip(ctx):
    """Access Register reads back dpc, dscratch0 and mscratch."""
    ctx.require('csr' in ctx.p['abstract'], 'profile declares no abstract CSR access')
    value = ctx.scratch + 0x100 if ctx.p['scratch'] is not None else 0x80000100
    for csr, written in ((DPC, value), (0x340, 0xfeedface)):
        ctx.set_csr(csr, written)
        expect(ctx.csr(csr) == written, f'CSR 0x{csr:x} readback differs')
    ctx.observe('dpc', value)


@check('abs.fpr_roundtrip')
def fpr_roundtrip(ctx):
    """Access Register reads back every FPR written (raw 64-bit bits)."""
    ctx.require('fpr' in ctx.p['abstract'] and ctx.xlen == 64, 'profile declares no abstract FPR access')
    if 'csr' in ctx.p['abstract']:
        ctx.set_csr(MSTATUS, ctx.csr(MSTATUS) | (1 << 13))   # mstatus.FS = Initial
    for n in range(32):
        value = (0x3ff0000000000000 | (n * 0x10101)) & ((1 << 64) - 1)
        ctx.set_reg(0x1020 + n, value)
        expect(ctx.reg(0x1020 + n) == value, f'f{n} readback differs')
    ctx.observe('f31', 0x3ff0000000000000 | (31 * 0x10101))


@check('abs.unsupported_regno')
def unsupported_regno(ctx):
    """An unimplemented register number gives cmderr 2 (not supported)."""
    regno = 0x1020 if 'fpr' not in ctx.p['abstract'] else 0xc000
    error, _ = ctx.access_reg(regno)
    expect(error == 2, f'regno 0x{regno:x} gave cmderr {error}, expected 2')
    ctx.observe('cmderr', error)


@check('abs.unsupported_size')
def unsupported_size(ctx):
    """aarsize larger than XLEN gives cmderr 2."""
    size = 4 if ctx.xlen == 64 else 3
    error = ctx.command((size << 20) | (1 << 17) | 0x1008)
    expect(error == 2, f'aarsize {size} gave cmderr {error}, expected 2')
    ctx.observe('cmderr', error)


@check('abs.unsupported_cmdtype')
def unsupported_cmdtype(ctx):
    """Undeclared command types give cmderr 2."""
    kinds = [0xff] + [k for k, name in ((1, 'quick'), (2, 'memory')) if name not in ctx.p['abstract']]
    for kind in kinds:
        error = ctx.command(kind << 24)
        expect(error == 2, f'cmdtype {kind} gave cmderr {error}, expected 2')
    ctx.observe('cmdtypes', kinds)


@check('abs.cmderr_sticky')
def cmderr_sticky(ctx):
    """cmderr is sticky: later commands do not run until it is cleared with W1C."""
    ctx.set_gpr(S0, 0x11)
    ctx.command(0xff << 24, clear=False)
    ctx.write(DATA0, 0x22)
    if ctx.xlen == 64:
        ctx.write(DATA0 + 1, 0)
    ctx.write(COMMAND, (ctx.size_code() << 20) | (1 << 17) | (1 << 16) | 0x1008)
    error = ctx.cmderr()
    ctx.write(ABSTRACTCS, 0x700)
    expect(error == 2, f'cmderr changed to {error} while sticky')
    expect(ctx.cmderr() == 0, 'W1C did not clear cmderr')
    expect(ctx.gpr(S0) == 0x11, 'a command ran while cmderr was set')
    ctx.observe('s0', 0x11)


@check('abs.running_haltresume')
def running_haltresume(ctx):
    """Access Register on a running hart gives cmderr 4 (halt/resume)."""
    ctx.resume()
    error, _ = ctx.access_reg(0x1008)
    ctx.halt()
    expect(error == 4, f'cmderr {error}, expected 4')
    ctx.observe('cmderr', error)


@check('abs.transfer_none')
def transfer_none(ctx):
    """transfer=0, postexec=0 does nothing and succeeds even with an invalid size."""
    error = ctx.command((7 << 20) | 0x1008)
    expect(error == 0, f'cmderr {error}, expected 0')


@check('abs.postincrement')
def postincrement(ctx):
    """aarpostincrement with autoexecdata reads consecutive GPRs."""
    ctx.require(ctx.p['autoexec'] and ctx.p['postincrement'], 'profile declares no autoexec postincrement')
    ctx.set_gpr(S0, 0xaaaa)
    ctx.set_gpr(S1, 0xbbbb)
    ctx.write(COMMAND, (ctx.size_code() << 20) | (1 << 19) | (1 << 17) | 0x1008)
    ctx.poll(lambda: ctx.read(ABSTRACTCS) & 0x1000 == 0, 'busy=0')
    ctx.write(ABSTRACTAUTO, 1)
    first = ctx.read(DATA0)                # this read re-executes the command for x9
    ctx.poll(lambda: ctx.read(ABSTRACTCS) & 0x1000 == 0, 'busy=0')
    ctx.write(ABSTRACTAUTO, 0)
    second = ctx.read(DATA0)
    expect(ctx.cmderr() == 0, 'autoexec postincrement set cmderr')
    expect((first, second) == (0xaaaa, 0xbbbb), f'read 0x{first:x}, 0x{second:x}')
    ctx.observe('values', [first, second])


@check('abs.dpc_resume')
def dpc_resume(ctx):
    """A resumed hart starts at dpc; ebreak with ebreakm=1 halts with cause 1 at the ebreak."""
    cause, dpc = ctx.run([Asm.addi(S0, S0, 1), Asm.EBREAK], regs={S0: 5})
    expect(cause == 1, f'cause {cause}, expected 1')
    expect(dpc == ctx.scratch + 4, f'dpc 0x{dpc:x}, expected the ebreak')
    expect(ctx.gpr(S0) == 6, 'the instruction at dpc did not run once')
    ctx.observe('result', [cause, dpc, 6])


@check('abs.busy_collision', reference=False)
def busy_collision(ctx):
    """A data write while an abstract command is busy gives cmderr 1."""
    ctx.require(ctx.p['busy_probe'], 'profile disables busy probing')
    ctx.write(COMMAND, (ctx.size_code() << 20) | (1 << 17) | 0x1008)
    ctx.write(DATA0, 1)
    still_busy = ctx.read(ABSTRACTCS) & 0x1000
    if not still_busy:
        ctx.poll(lambda: ctx.read(ABSTRACTCS) & 0x1000 == 0, 'busy=0')
        ctx.clear_cmderr()
        raise Inconclusive('busy was not observed after the colliding write')
    ctx.poll(lambda: ctx.read(ABSTRACTCS) & 0x1000 == 0, 'busy=0')
    error = ctx.cmderr()
    ctx.clear_cmderr()
    expect(error == 1, f'cmderr {error}, expected 1 (busy)')


@check('abs.memory_access')
def memory_access(ctx):
    """Access Memory writes and reads each size; postincrement advances arg1."""
    ctx.require('memory' in ctx.p['abstract'], 'profile declares no abstract memory access')
    base = ctx.scratch + DATA
    sizes = [s for s in (1, 2, 4, 8) if 8 * s <= ctx.xlen]
    for size in sizes:
        value = 0x8877665544332211 & ((1 << (8 * size)) - 1)
        ctx.mem_write(base, value, size, via='memory')
        expect(ctx.mem_read(base, size, via='memory') == value, f'{8 * size}-bit readback differs')
    words = ctx.xlen // 32
    for i in range(words):
        ctx.write(DATA0 + words + i, (base >> (32 * i)) & 0xffffffff)
    for value in (1, 2):
        ctx.write(DATA0, value)
        error = ctx.command((2 << 24) | (2 << 20) | (1 << 19) | (1 << 16))
        expect(not error, f'postincrement write failed with cmderr {error}')
    address = ctx.read(DATA0 + words) | (ctx.read(DATA0 + words + 1) << 32 if words == 2 else 0)
    expect(address == base + 8, f'arg1 0x{address:x}, expected 0x{base + 8:x}')
    expect(ctx.mem_read(base + 4, 4, via='memory') == 2, 'postincrement wrote the wrong word')
    ctx.observe('sizes', sizes)


@check('abs.memory_independent')
def memory_independent(ctx):
    """Memory written by Access Memory is seen by a program-buffer load, and the reverse."""
    ctx.require('memory' in ctx.p['abstract'], 'profile declares no abstract memory access')
    ctx.require(ctx.p['progbufsize'] + int(ctx.p['impebreak']) >= 2, 'needs a program buffer')
    base = ctx.scratch + DATA
    ctx.mem_write(base, 0x13579bdf, 4, via='memory')
    expect(ctx.mem_read(base, 4, via='progbuf') == 0x13579bdf, 'program-buffer load disagrees')
    ctx.mem_write(base, 0x2468ace0, 4, via='progbuf')
    expect(ctx.mem_read(base, 4, via='memory') == 0x2468ace0, 'Access Memory read disagrees')


@check('abs.quick_access')
def quick_access(ctx):
    """Quick Access halts, runs the program buffer and resumes a running hart."""
    ctx.require('quick' in ctx.p['abstract'], 'profile declares no quick access')
    ctx.set_gpr(S0, 0)
    loop = ctx.write_code(CODE, [Asm.j(0)])
    ctx.progbuf(Asm.addi(S0, S0, 1))
    ctx.set_csr(DPC, loop)
    ctx.resume()
    error = ctx.command(1 << 24)
    expect(not error, f'quick access failed with cmderr {error}')
    expect(not ctx.halted(), 'hart stayed halted after quick access')
    ctx.halt()
    expect(ctx.gpr(S0) == 1, 'program buffer did not run once')


# ============================================================================ program buffer (#153)
@check('pb.declared_sizes')
def declared_sizes(ctx):
    """abstractcs.progbufsize and datacount match the profile."""
    cs = ctx.read(ABSTRACTCS)
    expect((cs >> 24) & 31 == ctx.p['progbufsize'], f'progbufsize {(cs >> 24) & 31}')
    expect(cs & 15 == ctx.p['datacount'], f'datacount {cs & 15}')
    ctx.observe('abstractcs', cs & ~(0x1700))


@check('pb.exec')
def pb_exec(ctx):
    """postexec runs the program buffer after the transfer."""
    ctx.progbuf(Asm.addi(S0, S0, 1))
    ctx.set_gpr(S1, 0)
    error, _ = ctx.access_reg(0x1008, 5, postexec=True)
    expect(not error, f'postexec failed with cmderr {error}')
    expect(ctx.gpr(S0) == 6, 'program buffer did not run after the write')
    ctx.observe('s0', 6)


@check('pb.exception')
def pb_exception(ctx):
    """An exception in the program buffer gives cmderr 3, keeps the hart halted and leaves mepc/mcause/dpc."""
    ctx.set_csr(MEPC, 0x100)
    ctx.set_csr(MCAUSE, 0)
    dpc = ctx.csr(DPC)
    error = ctx.exec_progbuf(0)             # all-zero word: illegal instruction
    expect(error == 3, f'cmderr {error}, expected 3 (exception)')
    expect(ctx.halted(), 'hart left Debug Mode after a program-buffer exception')
    expect(ctx.csr(MEPC) == 0x100 and ctx.csr(MCAUSE) == 0, 'program-buffer exception updated mepc/mcause')
    expect(ctx.csr(DPC) == dpc, 'program-buffer exception changed dpc')
    expect(cause_of(ctx) == 3, 'program-buffer exception changed dcsr.cause')


@check('pb.ebreak_ends')
def pb_ebreak_ends(ctx):
    """ebreak in the program buffer ends execution before later words."""
    ctx.require(ctx.p['progbufsize'] >= 2, 'needs two program-buffer words')
    ctx.set_gpr(S0, 1)
    ctx.write(PROGBUF0, Asm.EBREAK)
    ctx.write(PROGBUF0 + 1, Asm.addi(S0, S0, 1))
    error = ctx.command((ctx.size_code() << 20) | (1 << 18))
    expect(not error, f'cmderr {error}')
    expect(ctx.gpr(S0) == 1, 'words after ebreak executed')


@check('pb.autoexecprogbuf')
def autoexecprogbuf(ctx):
    """autoexecprogbuf re-runs the last command on each program-buffer access."""
    ctx.require(ctx.p['autoexec'], 'profile declares no autoexec')
    ctx.set_gpr(S0, 0)
    ctx.exec_progbuf(Asm.addi(S0, S0, 1))
    ctx.write(ABSTRACTAUTO, 1 << 16)
    for _ in range(3):
        ctx.write(PROGBUF0, Asm.addi(S0, S0, 1))
        ctx.poll(lambda: ctx.read(ABSTRACTCS) & 0x1000 == 0, 'busy=0')
    ctx.write(ABSTRACTAUTO, 0)
    expect(ctx.cmderr() == 0, 'autoexec set cmderr')
    expect(ctx.gpr(S0) == 4, f's0 {ctx.gpr(S0)}, expected 4')
    ctx.observe('s0', 4)


@check('pb.memory')
def pb_memory(ctx):
    """Program-buffer stores and loads reach memory."""
    ctx.require(ctx.p['progbufsize'] + int(ctx.p['impebreak']) >= 2, 'needs a program buffer')
    base = ctx.scratch + DATA
    ctx.mem_write(base, 0xcafe0001, 4, via='progbuf')
    expect(ctx.mem_read(base, 4, via='progbuf') == 0xcafe0001, 'program-buffer memory round trip')


@check('pb.fence_i')
def pb_fence_i(ctx):
    """Code rewritten by the debugger and fenced runs in its new form."""
    ctx.require(ctx.p['fence_i'], 'profile declares no fence.i on code writes')
    ctx.run([Asm.addi(S0, S0, 1), Asm.EBREAK], regs={S0: 0})
    ctx.run([Asm.addi(S0, S0, 7), Asm.EBREAK], regs={S0: 0})
    expect(ctx.gpr(S0) == 7, 'the hart executed stale code')


# ============================================================================ Debug Mode rules
@check('dbg.dcsr_fields')
def dcsr_fields(ctx):
    """dcsr.debugver is 4, prv shows M on entry from M, cause is haltreq."""
    dcsr = ctx.csr(DCSR)
    expect(dcsr >> 28 == 4, f'debugver {dcsr >> 28}, expected 4')
    expect(dcsr & 3 == 3, f'prv {dcsr & 3}, expected 3')
    expect((dcsr >> 6) & 7 == 3, 'cause is not haltreq')
    ctx.observe('debugver', dcsr >> 28)


@check('dbg.ebreak_m_exception')
def ebreak_m_exception(ctx):
    """ebreakm=0: ebreak in M raises a breakpoint exception (mcause 3, mepc at the ebreak)."""
    handler = ctx.install_handler()
    ctx.set_ebreak(m=0)
    cause, dpc = ctx.run([Asm.NOP, Asm.EBREAK])
    ctx.set_ebreak(m=1)
    expect(dpc == handler, f'dpc 0x{dpc:x}, expected the trap handler')
    expect(ctx.csr(MCAUSE) == 3, f'mcause {ctx.csr(MCAUSE)}, expected 3')
    expect(ctx.csr(MEPC) == ctx.scratch + 4, 'mepc is not the ebreak')
    ctx.observe('mcause', 3)


def _lower_mode(ctx, mode, letter):
    ctx.require(letter in ctx.p['modes'], f'profile declares no {letter}-mode')
    handler = ctx.install_handler()
    field = {'S': 's', 'U': 'u'}[letter]
    ctx.set_ebreak(m=1, **{field: 1})
    cause, dpc = ctx.run([Asm.NOP, Asm.EBREAK], offset=UCODE, prv=mode)
    dcsr = ctx.csr(DCSR)
    expect(cause == 1 and dpc == ctx.scratch + UCODE + 4, f'ebreak{field}=1: cause {cause}, dpc 0x{dpc:x}')
    expect(dcsr & 3 == mode, f'dcsr.prv {dcsr & 3}, expected {mode}')
    ctx.set_ebreak(m=1, **{field: 0})
    cause, dpc = ctx.run([Asm.NOP, Asm.EBREAK], offset=UCODE, prv=mode)
    expect(dpc == handler and ctx.csr(MCAUSE) == 3, f'ebreak{field}=0 did not raise a breakpoint exception')
    expect((ctx.csr(MSTATUS) >> 11) & 3 == mode, 'mstatus.MPP does not show the trapping mode')
    ctx.set_ebreak(m=1)
    ctx.observe('prv', mode)


@check('dbg.ebreak_s')
def ebreak_s(ctx):
    """ebreaks selects Debug Mode entry or a breakpoint exception for ebreak in S-mode."""
    _lower_mode(ctx, 1, 'S')


@check('dbg.ebreak_u')
def ebreak_u(ctx):
    """ebreaku selects Debug Mode entry or a breakpoint exception for ebreak in U-mode."""
    _lower_mode(ctx, 0, 'U')


@check('dbg.prv_switch')
def prv_switch(ctx):
    """Writing dcsr.prv changes the mode the hart resumes in (ecall cause shows it)."""
    ctx.require('U' in ctx.p['modes'], 'profile declares no U-mode')
    handler = ctx.install_handler()
    cause, dpc = ctx.run([Asm.ECALL], offset=UCODE, prv=0)
    expect(dpc == handler, 'ecall did not reach the handler')
    expect(ctx.csr(MCAUSE) == 8, f'mcause {ctx.csr(MCAUSE)}, expected 8 (ecall from U)')


@check('dbg.step')
def step(ctx):
    """dcsr.step executes one instruction and halts with cause 4 at the next pc."""
    cause, dpc = ctx.run(ADDI8, regs={S0: 0}, step=True)
    expect(cause == 4, f'cause {cause}, expected 4 (step)')
    expect(dpc == ctx.scratch + 4, f'dpc 0x{dpc:x}, expected the second instruction')
    expect(ctx.gpr(S0) == 1, f'{ctx.gpr(S0)} instructions ran in one step')
    ctx.resume()
    ctx.poll(lambda: ctx.halted(), 'second step')
    expect(ctx.csr(DPC) == ctx.scratch + 8 and ctx.gpr(S0) == 2, 'second step did not advance one instruction')
    dcsr = ctx.csr(DCSR)
    ctx.set_csr(DCSR, dcsr & ~4)
    ctx.observe('dpc', [dpc - ctx.scratch, 8])


@check('dbg.step_trap')
def step_trap(ctx):
    """Stepping a trapping instruction halts at the trap handler with cause 4."""
    handler = ctx.install_handler()
    cause, dpc = ctx.run([Asm.ECALL], step=True)
    ctx.set_csr(DCSR, ctx.csr(DCSR) & ~4)
    expect(cause == 4, f'cause {cause}, expected 4')
    expect(dpc == handler, f'dpc 0x{dpc:x}, expected the handler')
    expect(ctx.csr(MCAUSE) == 11, f'mcause {ctx.csr(MCAUSE)}, expected 11')


@check('dbg.step_ebreak')
def step_ebreak(ctx):
    """Stepping an ebreak with ebreakm=1 reports cause 1 (ebreak has priority over step)."""
    cause, dpc = ctx.run([Asm.EBREAK], step=True)
    ctx.set_csr(DCSR, ctx.csr(DCSR) & ~4)
    expect(cause == 1, f'cause {cause}, expected 1')
    expect(dpc == ctx.scratch, 'dpc is not the ebreak')


@check('dbg.stepie')
def stepie(ctx):
    """stepie=0 masks a pending interrupt during a step; stepie=1 lets it trap."""
    ctx.require('S' in ctx.p['modes'], 'needs S-mode for a software-writable SSIP')
    handler = ctx.install_handler()
    ctx.set_csr(MIE, 2)
    ctx.set_csr(MSTATUS, ctx.csr(MSTATUS) | 8)
    ctx.set_csr(DCSR, ctx.csr(DCSR) | (1 << 11))
    if not (ctx.csr(DCSR) >> 11) & 1:
        ctx.set_csr(MIE, 0)
        ctx.require(False, 'dcsr.stepie is hardwired to 0; stepping interrupt behavior is not tested')
    results = []
    for stepie in (0, 1):
        ctx.set_csr(MIP, 2)
        ctx.set_csr(DCSR, (ctx.csr(DCSR) & ~(1 << 11)) | (stepie << 11))
        cause, dpc = ctx.run([Asm.NOP, Asm.NOP], step=True)
        results.append(dpc)
        ctx.set_csr(MIP, 0)
        ctx.set_csr(MSTATUS, ctx.csr(MSTATUS) | 8)
    ctx.set_csr(MIE, 0)
    ctx.set_csr(DCSR, ctx.csr(DCSR) & ~((1 << 11) | 4))
    expect(results[0] == ctx.scratch + 4, 'stepie=0 took the interrupt')
    expect(results[1] == handler, 'stepie=1 did not take the pending interrupt')


@check('dbg.dret_illegal')
def dret_illegal(ctx):
    """dret outside Debug Mode is an illegal instruction."""
    handler = ctx.install_handler()
    cause, dpc = ctx.run([Asm.DRET])
    expect(dpc == handler and ctx.csr(MCAUSE) == 2, f'mcause {ctx.csr(MCAUSE)}, expected 2')


@check('dbg.debug_csr_hidden')
def debug_csr_hidden(ctx):
    """dpc is not accessible from M-mode outside Debug Mode."""
    handler = ctx.install_handler()
    cause, dpc = ctx.run([Asm.csrrs(T0, DPC, 0)])
    expect(dpc == handler and ctx.csr(MCAUSE) == 2, f'mcause {ctx.csr(MCAUSE)}, expected 2')


# ============================================================================ triggers (#144)
def _types(ctx):
    count = ctx.p['triggers']['count']
    ctx.require(count > 0, 'profile declares no triggers')
    types = ctx.p['triggers']['types']
    return [types[i] if types and isinstance(types[0], list) else types for i in range(count)]


def _addr_type(ctx, index=0):
    types = _types(ctx)[index]
    for kind in (6, 2):
        if kind in types:
            return kind
    raise_unsupported(ctx, 'no mcontrol or mcontrol6 trigger')


def raise_unsupported(ctx, reason):
    ctx.require(False, reason)


def mc(ctx, kind, *, execute=0, load=0, store=0, match=0, action=1, chain=0, m=1, s=0, u=0, select=0,
       timing=0, dmode=1, size=0):
    xl = ctx.xlen
    value = (kind << (xl - 4)) | (dmode << (xl - 5)) | (action << 12) | (chain << 11) | (match << 7) \
        | (m << 6) | (s << 4) | (u << 3) | (execute << 2) | (store << 1) | load
    value |= (select << (21 if kind == 6 else 19))
    if kind == 2:
        value |= (timing << 18) | ((size & 3) << 16)
        if xl == 64:
            value |= ((size >> 2) & 3) << 21
    else:
        value |= (size & 7) << 16
    return value


def set_trigger(ctx, index, tdata1, tdata2=0):
    ctx.set_csr(TSELECT, index)
    ctx.set_csr(TDATA1, 0)
    ctx.set_csr(TDATA2, tdata2)
    ctx.set_csr(TDATA1, tdata1)
    return ctx.csr(TDATA1)


def clear_triggers(ctx):
    for index in range(ctx.p['triggers']['count']):
        ctx.set_csr(TSELECT, index)
        ctx.set_csr(TDATA1, 0)


@check('trig.enumerate')
def trig_enumerate(ctx):
    """tselect enumerates the declared triggers; tinfo lists the declared types."""
    types = _types(ctx)
    for index, kinds in enumerate(types):
        ctx.set_csr(TSELECT, index)
        expect(ctx.csr(TSELECT) == index, f'tselect {index} not writable')
        info = ctx.csr(TINFO) & 0xffff
        want = sum(1 << k for k in kinds)
        expect(info == want, f'trigger {index} tinfo 0x{info:x}, declared 0x{want:x}')
    ctx.set_csr(TSELECT, len(types))
    expect(ctx.csr(TSELECT) != len(types), 'tselect accepted an index past the declared triggers')
    ctx.observe('count', len(types))


@check('trig.warl_type')
def trig_warl_type(ctx):
    """Writing an unsupported trigger type legalizes to the declared value."""
    _types(ctx)
    ctx.set_csr(TSELECT, 0)
    ctx.set_csr(TDATA1, 7 << (ctx.xlen - 4))
    kind = ctx.csr(TDATA1) >> (ctx.xlen - 4)
    want = ctx.p['triggers']['unsupported_type']
    expect(kind == want, f'type {kind} after an unsupported write, declared {want}')
    ctx.observe('type', kind)


@check('trig.warl_action')
def trig_warl_action(ctx):
    """action=1 (enter Debug Mode) is not kept on a trigger with dmode=0."""
    kind = _addr_type(ctx)
    value = set_trigger(ctx, 0, mc(ctx, kind, execute=1, action=1, dmode=0), ctx.scratch)
    action = (value >> 12) & 15
    expect(action != 1, 'action=1 kept with dmode=0')
    clear_triggers(ctx)
    ctx.observe('action', action)


@check('trig.warl_virtualization')
def trig_warl_virtualization(ctx):
    """Without the H extension, mcontrol6 vs/vu read 0."""
    ctx.require(6 in _types(ctx)[0], 'trigger 0 has no mcontrol6')
    value = set_trigger(ctx, 0, mc(ctx, 6, execute=1) | (1 << 24) | (1 << 23), ctx.scratch)
    expect(not (value >> 23) & 3, 'vs/vu kept without the H extension')
    clear_triggers(ctx)


@check('trig.dmode_protect')
def trig_dmode_protect(ctx):
    """M-mode code cannot change a trigger with dmode=1."""
    kind = _addr_type(ctx)
    before = set_trigger(ctx, 0, mc(ctx, kind, execute=1, action=1, dmode=1), ctx.scratch + 0x3f0)
    ctx.run([Asm.csrrw(0, TSELECT, 0), Asm.csrrw(0, TDATA1, 0), Asm.csrrw(0, TDATA2, 0), Asm.EBREAK])
    ctx.set_csr(TSELECT, 0)
    expect(ctx.csr(TDATA1) == before, 'M-mode changed tdata1 of a dmode trigger')
    expect(ctx.csr(TDATA2) == ctx.scratch + 0x3f0, 'M-mode changed tdata2 of a dmode trigger')
    clear_triggers(ctx)


def _first(ctx, predicate, start, end):
    for pc in range(start, end, 4):
        if predicate(pc):
            return pc
    return None


def _match_predicate(ctx, match, t2):
    xl = ctx.xlen
    half = xl // 2
    low = (1 << half) - 1
    base = match & 7 if match >= 8 else match
    def pred(v):
        if base == 0:
            hit = v == t2
        elif base == 1:
            m = t2 ^ (t2 + 1)
            hit = (v | m) == (t2 | m)
        elif base == 2:
            hit = v >= t2
        elif base == 3:
            hit = v < t2
        elif base == 4:
            hit = (v & (t2 >> half) & low) == (t2 & low & (t2 >> half))
        else:
            hit = ((v >> half) & (t2 >> half) & low) == (t2 & low & (t2 >> half))
        return not hit if match >= 8 else hit
    return pred


@check('trig.execute_matches')
def trig_execute_matches(ctx):
    """Execute triggers fire before the first instruction that satisfies each declared match type."""
    kind = _addr_type(ctx)
    base = ctx.scratch
    xl, half = ctx.xlen, ctx.xlen // 2
    hmask = ((1 << half) - 1) & ~0xf
    tdata2 = {0: base + 8, 1: (base + 0x10) | 3, 2: base + 0xc, 3: base + 4, 4: (hmask << half) | ((base + 0x10) & hmask),
              5: (hmask << half) | ((base >> half) & hmask)}
    results = {}
    for match in ctx.p['triggers']['matches']:
        t2 = tdata2[match - 8 if match >= 8 else match]
        value = set_trigger(ctx, 0, mc(ctx, kind, execute=1, match=match), t2)
        if (value >> 7) & 15 != match:
            raise Fail(f'declared match type {match} not kept in tdata1')
        cause, dpc = ctx.run(ADDI8 + [Asm.EBREAK], regs={S0: 0})
        first = _first(ctx, _match_predicate(ctx, match, t2), base, base + 0x20)
        want = (2, first) if first is not None else (1, base + 0x20)
        expect((cause, dpc) == want, f'match {match}: halted cause {cause} at 0x{dpc:x}, expected {want[0]} at 0x{want[1]:x}')
        expect(ctx.gpr(S0) == (dpc - base) // 4, f'match {match}: trigger did not fire before the instruction')
        results[match] = dpc - base
    clear_triggers(ctx)
    ctx.observe('halts', results)


@check('trig.hit')
def trig_hit(ctx):
    """A firing trigger sets its hit bit."""
    kind = _addr_type(ctx)
    set_trigger(ctx, 0, mc(ctx, kind, execute=1), ctx.scratch + 8)
    ctx.run(ADDI8 + [Asm.EBREAK])
    ctx.set_csr(TSELECT, 0)
    value = ctx.csr(TDATA1)
    hit = (value >> (22 if kind == 6 else 20)) & 1
    clear_triggers(ctx)
    expect(hit == 1, 'hit bit not set after the trigger fired')


@check('trig.load_address')
def trig_load_address(ctx):
    """A load-address trigger fires before the load: dpc is the load and rd is unchanged."""
    ctx.require('load' in ctx.p['triggers']['accesses'], 'profile declares no load triggers')
    kind = _addr_type(ctx)
    data = ctx.scratch + DATA
    ctx.mem_write(data, 0x55)
    set_trigger(ctx, 0, mc(ctx, kind, load=1), data)
    cause, dpc = ctx.run([Asm.NOP, Asm.lw(T0, A0), Asm.EBREAK], regs={A0: data, T0: 0x77})
    clear_triggers(ctx)
    expect((cause, dpc) == (2, ctx.scratch + 4), f'cause {cause} at 0x{dpc:x}')
    expect(ctx.gpr(T0) == 0x77, 'the load completed before the trigger')


@check('trig.store_address')
def trig_store_address(ctx):
    """A store-address trigger fires before the store: memory is unchanged."""
    ctx.require('store' in ctx.p['triggers']['accesses'], 'profile declares no store triggers')
    kind = _addr_type(ctx)
    data = ctx.scratch + DATA
    ctx.mem_write(data, 0x55)
    set_trigger(ctx, 0, mc(ctx, kind, store=1), data)
    cause, dpc = ctx.run([Asm.NOP, Asm.sw(S1, A0), Asm.EBREAK], regs={A0: data, S1: 0x99})
    clear_triggers(ctx)
    expect((cause, dpc) == (2, ctx.scratch + 4), f'cause {cause} at 0x{dpc:x}')
    expect(ctx.mem_read(data) == 0x55, 'the store completed before the trigger')


def _data_trigger(ctx, store):
    ctx.require(('store' if store else 'load') in ctx.p['triggers']['accesses'],
                'profile declares no trigger of this access kind')
    kind = _addr_type(ctx)
    timing = ctx.p['triggers']['store_data_timing' if store else 'load_data_timing']
    ctx.require(timing is not None, 'profile declares no data-match trigger of this kind')
    data = ctx.scratch + DATA
    ctx.mem_write(data, 0x1234 if not store else 0)
    ctx.mem_write(data + 4, 0x1111)
    set_trigger(ctx, 0, mc(ctx, kind, load=int(not store), store=int(store), select=1), 0x1234)
    if store:
        code = [Asm.sw(T1, A0, 4), Asm.sw(S1, A0), Asm.NOP, Asm.EBREAK]
        regs = {A0: data, S1: 0x1234, T1: 0x1111}
    else:
        code = [Asm.lw(T1, A0, 4), Asm.lw(T0, A0), Asm.NOP, Asm.EBREAK]
        regs = {A0: data, T0: 0}
    cause, dpc = ctx.run(code, regs=regs)
    clear_triggers(ctx)
    want = ctx.scratch + (8 if timing == 'after' else 4)
    expect((cause, dpc) == (2, want), f'cause {cause} at 0x{dpc:x}, expected 2 at 0x{want:x} ({timing})')
    if store:
        stored = ctx.mem_read(data)
        expect(stored == (0x1234 if timing == 'after' else 0), f'memory 0x{stored:x} disagrees with {timing} timing')
    else:
        expect(ctx.gpr(T0) == 0x1234, 'the matching load did not complete')
    ctx.observe('timing', timing)


@check('trig.store_data')
def trig_store_data(ctx):
    """A store-data trigger (select=1) fires at the declared timing for the matching store."""
    _data_trigger(ctx, True)


@check('trig.load_data')
def trig_load_data(ctx):
    """A load-data trigger (select=1) fires after the matching load returns data."""
    _data_trigger(ctx, False)


@check('trig.size_match')
def trig_size_match(ctx):
    """A store trigger with size=16-bit ignores a 32-bit store to the same address and fires on a 16-bit store."""
    ctx.require('store' in ctx.p['triggers']['accesses'], 'profile declares no store triggers')
    kind = _addr_type(ctx)
    ctx.require(2 in ctx.p['triggers']['sizes'], 'profile declares no 16-bit size matching')
    data = ctx.scratch + DATA
    ctx.mem_write(data, 0)
    value = set_trigger(ctx, 0, mc(ctx, kind, store=1, size=2), data)
    expect((value >> 16) & (7 if kind == 6 else 3) == 2, 'declared size 2 not kept in tdata1')
    cause, dpc = ctx.run([Asm.sw(S1, A0), Asm.sh(S1, A0), Asm.EBREAK], regs={A0: data, S1: 0x1234})
    clear_triggers(ctx)
    expect((cause, dpc) == (2, ctx.scratch + 4), f'cause {cause} at 0x{dpc:x}, expected 2 at the 16-bit store')


@check('trig.privilege')
def trig_privilege(ctx):
    """A trigger with only u=1 ignores M-mode execution and fires in U-mode."""
    ctx.require('U' in ctx.p['modes'], 'profile declares no U-mode')
    kind = _addr_type(ctx)
    set_trigger(ctx, 0, mc(ctx, kind, execute=1, m=0, u=1), ctx.scratch + UCODE + 8)
    ctx.set_ebreak(m=1, u=1)
    in_m = ctx.run(ADDI8 + [Asm.EBREAK], offset=UCODE, prv=3)
    in_u = ctx.run(ADDI8 + [Asm.EBREAK], offset=UCODE, prv=0)
    ctx.set_ebreak(m=1)
    clear_triggers(ctx)
    expect(in_m == (1, ctx.scratch + UCODE + 0x20), f'trigger fired in M-mode: {in_m}')
    expect(in_u == (2, ctx.scratch + UCODE + 8), f'trigger did not fire in U-mode: {in_u}')


@check('trig.chain')
def trig_chain(ctx):
    """Chained triggers fire only when every trigger in the chain matches."""
    types = _types(ctx)
    ctx.require(len(types) >= 2 and ctx.p['triggers']['chain'], 'needs two chainable triggers')
    ctx.require({2, 3} <= set(ctx.p['triggers']['matches']), 'needs >= and < match types')
    kind = _addr_type(ctx)
    base = ctx.scratch
    set_trigger(ctx, 0, mc(ctx, kind, execute=1, match=2, chain=1), base + 0x10)
    set_trigger(ctx, 1, mc(ctx, kind, execute=1, match=3), base + 0x18)
    inside = ctx.run(ADDI8 + [Asm.EBREAK])
    set_trigger(ctx, 0, mc(ctx, kind, execute=1, match=2, chain=1), base + 0x18)
    set_trigger(ctx, 1, mc(ctx, kind, execute=1, match=3), base + 0x10)
    never = ctx.run(ADDI8 + [Asm.EBREAK])
    clear_triggers(ctx)
    expect(inside == (2, base + 0x10), f'chain did not fire at the range start: {inside}')
    expect(never == (1, base + 0x20), f'chain fired although one trigger never matched: {never}')


@check('trig.timing_after')
def trig_timing_after(ctx):
    """mcontrol timing=1 fires after the matching instruction executes."""
    ctx.require(2 in _types(ctx)[0] and 1 in ctx.p['triggers']['timing'], 'profile declares no mcontrol timing=1')
    value = set_trigger(ctx, 0, mc(ctx, 2, execute=1, timing=1), ctx.scratch + 8)
    expect((value >> 18) & 1, 'declared timing=1 not kept in tdata1')
    cause, dpc = ctx.run(ADDI8 + [Asm.EBREAK], regs={S0: 0})
    clear_triggers(ctx)
    expect((cause, dpc) == (2, ctx.scratch + 12), f'cause {cause} at 0x{dpc:x}')
    expect(ctx.gpr(S0) == 3, 'the matching instruction did not execute')


@check('trig.icount')
def trig_icount(ctx):
    """icount with count=3 halts after three instructions and sets hit."""
    ctx.require(3 in _types(ctx)[0], 'trigger 0 has no icount')
    xl = ctx.xlen
    value = (3 << (xl - 4)) | (1 << (xl - 5)) | (3 << 10) | (1 << 9) | 1
    set_trigger(ctx, 0, value)
    cause, dpc = ctx.run(ADDI8 + [Asm.EBREAK], regs={S0: 0})
    ctx.set_csr(TSELECT, 0)
    after = ctx.csr(TDATA1)
    clear_triggers(ctx)
    expect((cause, dpc) == (2, ctx.scratch + 12), f'cause {cause} at 0x{dpc:x}')
    expect(ctx.gpr(S0) == 3, 'icount did not count three instructions')
    expect((after >> 24) & 1, 'icount hit not set')


@check('trig.etrigger')
def trig_etrigger(ctx):
    """etrigger on ecall from M halts in the trap handler with mcause 11."""
    ctx.require(5 in _types(ctx)[0], 'trigger 0 has no etrigger')
    handler = ctx.install_handler()
    xl = ctx.xlen
    set_trigger(ctx, 0, (5 << (xl - 4)) | (1 << (xl - 5)) | (1 << 9) | 1, 1 << 11)
    cause, dpc = ctx.run([Asm.NOP, Asm.ECALL, Asm.EBREAK])
    clear_triggers(ctx)
    expect((cause, dpc) == (2, handler), f'cause {cause} at 0x{dpc:x}, expected 2 at the handler')
    expect(ctx.csr(MCAUSE) == 11, 'the exception was not taken before the trigger')


@check('trig.itrigger')
def trig_itrigger(ctx):
    """itrigger on the supervisor software interrupt halts in the handler."""
    ctx.require(4 in _types(ctx)[0], 'trigger 0 has no itrigger')
    ctx.require('S' in ctx.p['modes'], 'needs S-mode for a software-writable SSIP')
    handler = ctx.install_handler()
    xl = ctx.xlen
    set_trigger(ctx, 0, (4 << (xl - 4)) | (1 << (xl - 5)) | (1 << 9) | 1, 1 << 1)
    ctx.set_csr(MIE, 2)
    ctx.set_csr(MIP, 2)
    ctx.set_csr(MSTATUS, ctx.csr(MSTATUS) | 8)
    cause, dpc = ctx.run([Asm.NOP, Asm.NOP, Asm.EBREAK])
    ctx.set_csr(MIP, 0)
    ctx.set_csr(MIE, 0)
    clear_triggers(ctx)
    expect((cause, dpc) == (2, handler), f'cause {cause} at 0x{dpc:x}, expected 2 at the handler')
    expect(ctx.csr(MCAUSE) == (1 << (xl - 1)) | 1, 'the interrupt was not taken')


@check('trig.action_breakpoint')
def trig_action_breakpoint(ctx):
    """action=0 raises a breakpoint exception (mcause 3, mepc at the match) when tcontrol.mte=1."""
    kind = _addr_type(ctx)
    ctx.require(0 in ctx.p['triggers']['actions'] and ctx.p['triggers']['tcontrol'],
                'profile declares no action=0 with tcontrol')
    handler = ctx.install_handler()
    ctx.set_csr(TCONTROL, 1 << 3)
    set_trigger(ctx, 0, mc(ctx, kind, execute=1, action=0, dmode=0), ctx.scratch + 8)
    cause, dpc = ctx.run(ADDI8 + [Asm.EBREAK])
    clear_triggers(ctx)
    expect(dpc == handler, f'dpc 0x{dpc:x}, expected the handler')
    expect(ctx.csr(MCAUSE) == 3 and ctx.csr(MEPC) == ctx.scratch + 8, 'not a breakpoint exception at the match')
    expect(not (ctx.csr(TCONTROL) >> 3) & 1, 'trap entry did not clear tcontrol.mte')


@check('trig.action_breakpoint_u')
def trig_action_breakpoint_u(ctx):
    """action=0 in U-mode raises a breakpoint exception (mcause 3, mepc at the match, MPP=U)."""
    kind = _addr_type(ctx)
    ctx.require('U' in ctx.p['modes'] and 0 in ctx.p['triggers']['actions'], 'needs U-mode and action=0')
    handler = ctx.install_handler()
    set_trigger(ctx, 0, mc(ctx, kind, execute=1, action=0, dmode=0, m=0, u=1), ctx.scratch + UCODE + 8)
    cause, dpc = ctx.run(ADDI8 + [Asm.EBREAK], offset=UCODE, prv=0)
    clear_triggers(ctx)
    expect(dpc == handler, f'dpc 0x{dpc:x}, expected the handler')
    expect(ctx.csr(MCAUSE) == 3 and ctx.csr(MEPC) == ctx.scratch + UCODE + 8, 'not a breakpoint exception at the match')
    expect((ctx.csr(MSTATUS) >> 11) & 3 == 0, 'mstatus.MPP does not show U-mode')


@check('trig.mte_gating')
def trig_mte_gating(ctx):
    """With tcontrol.mte=0, an action=0 trigger does not fire in M-mode."""
    kind = _addr_type(ctx)
    ctx.require(0 in ctx.p['triggers']['actions'] and ctx.p['triggers']['tcontrol'],
                'profile declares no action=0 with tcontrol')
    ctx.install_handler()
    ctx.set_csr(TCONTROL, 0)
    set_trigger(ctx, 0, mc(ctx, kind, execute=1, action=0, dmode=0), ctx.scratch + 8)
    result = ctx.run(ADDI8 + [Asm.EBREAK])
    clear_triggers(ctx)
    expect(result == (1, ctx.scratch + 0x20), f'trigger fired with mte=0: {result}')


@check('trig.debug_mode_silent')
def trig_debug_mode_silent(ctx):
    """Triggers do not fire for program-buffer accesses in Debug Mode."""
    ctx.require('load' in ctx.p['triggers']['accesses'], 'needs a load trigger; silence alone is not evidence')
    kind = _addr_type(ctx)
    ctx.require(ctx.p['progbufsize'] + int(ctx.p['impebreak']) >= 2, 'needs a program buffer')
    data = ctx.scratch + DATA
    set_trigger(ctx, 0, mc(ctx, kind, load=1), data)
    ctx.set_gpr(S0, data)
    error = ctx.exec_progbuf(Asm.lw(S1, S0))
    clear_triggers(ctx)
    expect(error == 0, f'program-buffer load gave cmderr {error}')
    expect(ctx.halted() and cause_of(ctx) == 3, 'a trigger fired in Debug Mode')


# ============================================================================ system bus (#156)
def _sba(ctx):
    ctx.require(ctx.p['sba'] is not None, 'profile declares no system-bus access')
    return ctx.p['sba']


@check('sba.capabilities')
def sba_capabilities(ctx):
    """sbcs reports version 1, the declared address width and access sizes."""
    sba = _sba(ctx)
    cs = ctx.read(SBCS)
    expect(cs >> 29 == 1, f'sbversion {cs >> 29}')
    expect((cs >> 5) & 0x7f == sba['asize'], f'sbasize {(cs >> 5) & 0x7f}')
    want = sum(1 << {8: 0, 16: 1, 32: 2, 64: 3, 128: 4}[s] for s in sba['sizes'])
    expect(cs & 31 == want, f'sbaccess bits 0x{cs & 31:x}, declared 0x{want:x}')
    ctx.observe('capabilities', [cs >> 29, (cs >> 5) & 0x7f, cs & 31])


@check('sba.sizes')
def sba_sizes(ctx):
    """Each declared size writes and reads memory; an independent path confirms the bytes."""
    sba = _sba(ctx)
    base = ctx.scratch + DATA
    independent = 'memory' if 'memory' in ctx.p['abstract'] else 'progbuf'
    for bits in (b for b in sba['sizes'] if b <= 64):
        size = bits // 8
        value = 0xf1e2d3c4b5a69788 & ((1 << bits) - 1)
        ctx.mem_write(base, 0, 8 if ctx.xlen == 64 else 4, via=independent)
        ctx.sba_write(base, value, size)
        expect(ctx.sba_read(base, size) == value, f'{bits}-bit SBA readback differs')
        if independent == 'memory' or size >= 4:
            got = ctx.mem_read(base, max(size, 4), via=independent) & ((1 << bits) - 1)
            expect(got == value, f'{bits}-bit SBA write not seen through {independent}')
    ctx.observe('sizes', sba['sizes'])


@check('sba.autoincrement')
def sba_autoincrement(ctx):
    """sbautoincrement advances sbaddress by the access size after each access."""
    _sba(ctx)
    base = ctx.scratch + DATA
    ctx.sbcs(access=2, autoinc=1, error=7, busyerror=1)
    ctx.write(SBADDRESS1, base >> 32) if ctx.p['sba']['asize'] > 32 else None
    ctx.write(SBADDRESS0, base & 0xffffffff)
    for index in range(4):
        ctx.write(SBDATA0, 0x100 + index)
        ctx.sb_wait()
    address = ctx.read(SBADDRESS0)
    expect(address == (base + 16) & 0xffffffff, f'sbaddress0 0x{address:x}, expected base+16')
    values = [ctx.mem_read(base + 4 * i, 4) for i in range(4)]
    expect(values == [0x100, 0x101, 0x102, 0x103], f'memory {values}')


@check('sba.readondata')
def sba_readondata(ctx):
    """sbreadonaddr starts a read; sbreadondata streams the next words."""
    _sba(ctx)
    base = ctx.scratch + DATA
    for index in range(3):
        ctx.mem_write(base + 4 * index, 0x200 + index)
    ctx.sbcs(access=2, autoinc=1, readonaddr=1, readondata=1, error=7, busyerror=1)
    ctx.write(SBADDRESS1, base >> 32) if ctx.p['sba']['asize'] > 32 else None
    ctx.write(SBADDRESS0, base & 0xffffffff)
    values = []
    for _ in range(3):
        ctx.sb_wait()
        values.append(ctx.read(SBDATA0))
    ctx.sbcs(access=2)
    expect(values == [0x200, 0x201, 0x202], f'streamed {values}')


@check('sba.alignment')
def sba_alignment(ctx):
    """A misaligned access sets the declared sberror (spec: 3) and does not write; W1C clears it."""
    _sba(ctx)
    base = ctx.scratch + DATA
    ctx.mem_write(base, 0)
    ctx.mem_write(base + 4, 0)
    ctx.sbcs(access=2, error=7, busyerror=1)
    ctx.write(SBADDRESS1, base >> 32) if ctx.p['sba']['asize'] > 32 else None
    ctx.write(SBADDRESS0, (base + 2) & 0xffffffff)
    ctx.write(SBDATA0, 0xffffffff)
    cs = ctx.sb_wait()
    ctx.sbcs(access=2, error=7)
    want = ctx.p['sba']['misaligned_error']
    expect((cs >> 12) & 7 == want, f'sberror {(cs >> 12) & 7}, declared {want}')
    expect((ctx.read(SBCS) >> 12) & 7 == 0, 'W1C did not clear sberror')
    expect(ctx.mem_read(base) == 0 and ctx.mem_read(base + 4) == 0, 'a misaligned access wrote memory')


@check('sba.unsupported_size')
def sba_unsupported_size(ctx):
    """An undeclared access size sets the declared sberror (spec: 4)."""
    sba = _sba(ctx)
    missing = [b for b in (8, 16, 32, 64, 128) if b not in sba['sizes']]
    ctx.require(missing, 'every size is declared')
    code = {8: 0, 16: 1, 32: 2, 64: 3, 128: 4}[missing[0]]
    ctx.sbcs(access=code, readonaddr=1, error=7, busyerror=1)
    ctx.write(SBADDRESS0, (ctx.scratch + DATA) & 0xffffffff)
    cs = ctx.sb_wait()
    ctx.sbcs(access=2, error=7)
    want = ctx.p['sba']['size_error']
    expect((cs >> 12) & 7 == want, f'sberror {(cs >> 12) & 7}, declared {want}')


def _region_error(ctx, kind, default):
    _sba(ctx)
    regions = [r for r in ctx.p['memory'] if r['kind'] == kind]
    ctx.require(regions, f'profile declares no {kind} region')
    region = regions[0]
    want = region['sberror'] or default
    write = kind == 'readonly'
    ctx.sbcs(access=2, readonaddr=int(not write), error=7, busyerror=1)
    ctx.write(SBADDRESS1, region['base'] >> 32) if ctx.p['sba']['asize'] > 32 else None
    ctx.write(SBADDRESS0, region['base'] & 0xffffffff)
    if write:
        ctx.write(SBDATA0, 0x1)
    cs = ctx.sb_wait()
    ctx.sbcs(access=2, error=7)
    expect((cs >> 12) & 7 == want, f'{kind} region: sberror {(cs >> 12) & 7}, declared {want}')
    ctx.observe('sberror', want)


@check('sba.bus_error')
def sba_bus_error(ctx):
    """An access to a declared error region reports its declared sberror."""
    _region_error(ctx, 'error', 2)


@check('sba.permission')
def sba_permission(ctx):
    """A write to a declared read-only region reports its declared sberror."""
    _region_error(ctx, 'readonly', 2)


@check('sba.power_off')
def sba_power_off(ctx):
    """An access to a declared powered-off region reports its declared sberror."""
    _region_error(ctx, 'off', 7)


@check('sba.error_blocks')
def sba_error_blocks(ctx):
    """While sberror is set, new accesses do not start."""
    _sba(ctx)
    base = ctx.scratch + DATA
    ctx.mem_write(base, 0x5)
    ctx.sbcs(access=2, error=7, busyerror=1)
    ctx.write(SBADDRESS1, base >> 32) if ctx.p['sba']['asize'] > 32 else None
    ctx.write(SBADDRESS0, (base + 1) & 0xffffffff)
    ctx.write(SBDATA0, 0x6)                 # misaligned: sets sberror
    ctx.sb_wait()
    ctx.write(SBADDRESS0, base & 0xffffffff)
    ctx.write(SBDATA0, 0x7)                 # must not start
    ctx.sb_wait()
    ctx.sbcs(access=2, error=7)
    expect(ctx.mem_read(base) == 0x5, 'an access started while sberror was set')


@check('sba.busyerror', reference=False)
def sba_busyerror(ctx):
    """A second access while sbbusy sets sbbusyerror."""
    _sba(ctx)
    ctx.require(ctx.p['busy_probe'], 'profile disables busy probing')
    base = ctx.scratch + DATA
    ctx.sbcs(access=2, readonaddr=1, error=7, busyerror=1)
    ctx.write(SBADDRESS1, base >> 32) if ctx.p['sba']['asize'] > 32 else None
    ctx.write(SBADDRESS0, base & 0xffffffff)
    ctx.read(SBDATA0)                       # readondata=0: starts nothing, collides while busy
    cs = ctx.read(SBCS)
    if not (cs >> 21) & 1:
        ctx.sbcs(access=2, error=7, busyerror=1)
        raise Inconclusive('sbbusy was not observed after the colliding read')
    ctx.sb_wait()
    cs = ctx.read(SBCS)
    ctx.sbcs(access=2, error=7, busyerror=1)
    expect((cs >> 22) & 1, 'sbbusyerror not set')


@check('sba.concurrent_cpu')
def sba_concurrent_cpu(ctx):
    """SBA works while the hart runs: it sees hart stores and the hart sees SBA stores."""
    _sba(ctx)
    data = ctx.scratch + DATA
    ctx.mem_write(data, 0)
    ctx.mem_write(data + 8, 0)
    loop = [Asm.lw(T1, A0, 8), Asm.bne(T1, 0, 20), Asm.lw(T0, A0), Asm.addi(T0, T0, 1), Asm.sw(T0, A0),
            Asm.j(-20), Asm.EBREAK]
    base = ctx.write_code(CODE, loop)
    ctx.set_gpr(A0, data)
    ctx.set_csr(DPC, base)
    ctx.resume()
    first = ctx.sba_read(data)
    for _ in range(20):
        ctx.status()
    second = ctx.sba_read(data)
    ctx.sba_write(data + 8, 1)
    halted = ctx.wait_halt()
    if not halted:
        ctx.halt()
    expect(second > first, 'SBA did not observe the running hart stores')
    expect(halted and cause_of(ctx) == 1, 'the hart did not observe the SBA store')
