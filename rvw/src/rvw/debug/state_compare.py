"""Compare full integer state at single-step halts with native Spike."""
from .suite import Ctx, DPC, DCSR, Fail


def compare_steps(ctx, spike, count, csrs=(0x340,)):
    """Start from equal, explicit GPR/mscratch state. Never seed from DUT observations."""
    if count < 1:
        raise ValueError('steps must be positive')
    ctx.prepare()
    for reg in range(1, 32):
        ctx.set_gpr(reg, 0)
        spike.set_reg(reg, 0)
    ctx.set_csr(0x340, 0)
    spike.set_mscratch(0)
    pc = spike.platform.reset_pc
    ctx.set_csr(DPC, pc)
    # stepie=0: no external interrupts are driven by this campaign.
    ctx.set_csr(DCSR, (ctx.csr(DCSR) & ~(1 << 11)) | 4)
    rows = []
    for index in range(count):
        ctx.resume()
        if not ctx.wait_halt():
            raise Fail(f'no single-step halt at retirement {index + 1}')
        cause = (ctx.csr(DCSR) >> 6) & 7
        if cause != 4:
            raise Fail(f'halt cause {cause}, expected single step at retirement {index + 1}')
        effect = spike.step()
        if effect['trap'] or effect['halted']:
            raise Fail(f'reference did not retire a normal instruction at step {index + 1}')
        expected_csrs = spike.csr_snapshot([hex(csr) for csr in csrs])
        actual = {'pc': ctx.csr(DPC), 'gprs': [ctx.gpr(reg) for reg in range(32)],
                  'csrs': {hex(csr): ctx.csr(csr) for csr in csrs}}
        expected = {'pc': effect['pc_next'], 'gprs': effect['regs'], 'csrs': expected_csrs}
        diff = {key: {'actual': actual[key], 'expected': expected[key]}
                for key in actual if actual[key] != expected[key]}
        rows.append({'retirement': index + 1, 'status': 'fail' if diff else 'pass',
                     'pc': actual['pc'], 'differences': diff})
        if diff:
            break
    return rows


def run(out, profile, elf, platform, shim, steps=16, csrs=None, port=None):
    from . import profile as profiles, suite
    from rvw.cosim.platform import Platform
    from rvw.cosim.spike import Spike, capture_shim
    from rvw.common.capture import Capture
    from pathlib import Path
    p = profiles.load(profile)
    if port is not None:
        p['transport'] = {**p['transport'], 'kind': 'remote_bitbang', 'port': port, 'host': '127.0.0.1'}
    if not p.get('transport_declared') or p['transport']['kind'] in ('model', 'jtag-model'):
        raise ValueError('state comparison requires a declared RTL transport')
    target = suite.open_target(p)
    ref = None
    try:
        captured_shim = capture_shim(Capture(Path(out) / 'inputs'), Path(shim))
        ref = Spike(Platform.load(None, platform), elf, shim=captured_shim)
        if ref.platform.xlen != p['xlen']:
            raise ValueError('profile and platform XLEN differ')
        ctx = Ctx(target, p)
        ctx.prepare()
        # Reload independently: an earlier debug session may have changed RAM.
        # The same validated ELF segments initialize Spike and RTL.
        for address, data, memsz in ref.elf.segments:
            data = data + bytes(memsz - len(data))
            offset = 0
            while offset < len(data):
                size = 4 if (address + offset) % 4 == 0 and len(data) - offset >= 4 else 1
                ctx.mem_write(address + offset, int.from_bytes(data[offset:offset + size], 'little'), size)
                offset += size
        if p['fence_i']:
            from .hart import Asm
            if ctx.exec_progbuf(Asm.FENCE_I):
                raise Fail('fence.i failed after ELF load')
        rows = compare_steps(ctx, ref, steps, tuple(int(v, 0) for v in (csrs or ['0x340'])))
        tests = [{'id': f'state.retirement_{row["retirement"]}', 'status': row['status'],
                  'observations': {'pc': row['pc'], 'differences': row['differences']},
                  **({'message': 'architectural state differs', 'signature': 'debug:state',
                      'message_complete': True} if row['differences'] else {})} for row in rows]
        from .api import _write_tests
        result = _write_tests(out, tests, suite_name='debug-state', core=p['name'],
                              config='single-step', extra={'steps_requested': steps,
                              'gprs_per_halt': 32, 'csrs': csrs or ['0x340']})
        result.update(status='mismatch' if result['exit'] else 'match',
                      halts_compared=len(rows), gprs_per_halt=32, csrs=csrs or ['0x340'])
    finally:
        target.close()
        if ref is not None:
            ref.close()
    return result
