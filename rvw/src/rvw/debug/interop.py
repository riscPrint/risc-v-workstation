"""OpenOCD and GDB interoperability campaign (`rvw debug interop`).

GDB starts OpenOCD over a pipe (`gdb_port pipe`) against a remote_bitbang JTAG
target. A GDB Python script loads the ELF and checks register and memory writes,
software and hardware breakpoints, stepping, a watchpoint and reset-halt by their
effects. A connection alone is never a pass. Results are C3 (`debug-interop`).
"""
from __future__ import annotations

import datetime as _dt
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess

from rvw.common.proc import run_group

CHECKS = ('load', 'register_write', 'memory_write', 'breakpoint', 'hardware_breakpoint', 'stepi',
          'stepi_jump', 'watchpoint')
SCRIPT = Path(__file__).with_name('interop_gdb.py')


def find_gdb(gdb=None):
    for candidate in ([gdb] if gdb else ['riscv64-elf-gdb', 'riscv64-unknown-elf-gdb', 'gdb-multiarch']):
        path = shutil.which(candidate) if candidate else None
        if path:
            return path
    raise FileNotFoundError('no RISC-V GDB found (riscv64-elf-gdb, riscv64-unknown-elf-gdb, gdb-multiarch)')


def version(command):
    try:
        out = subprocess.run([command, '--version'], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (out.stdout or out.stderr).strip().splitlines()
    return text[0] if text else None


def openocd_config(port, *, host='127.0.0.1', irlen=5, idcode=None, log):
    expected = f' -expected-id 0x{idcode:08x}' if idcode is not None else ''
    return '\n'.join([
        'adapter driver remote_bitbang', f'remote_bitbang host {host}', f'remote_bitbang port {port}',
        'transport select jtag', f'jtag newtap dut cpu -irlen {irlen}{expected}',
        'target create dut.cpu riscv -chain-position dut.cpu', 'gdb_port pipe', 'tcl_port disabled',
        'telnet_port disabled', f'log_output {log}', 'init', 'halt', '']) + '\n'


def first_word(elf):
    """First four bytes at the ELF entry, from the file (an oracle independent of the target)."""
    import struct
    data = Path(elf).read_bytes()
    if data[:4] != b'\x7fELF' or data[4] not in (1, 2):
        raise ValueError('interop needs a 32-bit or 64-bit ELF')
    if data[4] == 2:
        entry, = struct.unpack_from('<Q', data, 0x18)
        phoff, = struct.unpack_from('<Q', data, 0x20)
        phentsize, phnum = struct.unpack_from('<HH', data, 0x36)
    else:
        entry, phoff = struct.unpack_from('<II', data, 0x18)
        phentsize, phnum = struct.unpack_from('<HH', data, 0x2a)
    for i in range(phnum):
        if data[4] == 2:
            kind, _, offset, vaddr, _, filesz, _ = struct.unpack_from('<IIQQQQQ', data, phoff + i * phentsize)
        else:
            kind, offset, vaddr, _, filesz = struct.unpack_from('<IIIII', data, phoff + i * phentsize)
        if kind == 1 and vaddr <= entry < vaddr + filesz:
            at = offset + entry - vaddr
            return data[at:at + 4].hex()
    raise ValueError('ELF entry is not in a loadable segment')


def assess(output, returncode, timed_out, *, expect_reset):
    checks = set(re.findall(r'^RVW_CHECK:(\w+)\s*$', output, re.M))
    failures = re.findall(r'^RVW_FAILURE:(.*)$', output, re.M)
    expected = set(CHECKS) | ({'reset_halt'} if expect_reset else set())
    complete = 'RVW_COMPLETE' in output
    if failures:
        status = 'fail'
    elif timed_out or not complete or 'RVW_CONNECTED' not in output:
        status = 'inconclusive'
    elif checks != expected:
        status = 'fail'
    else:
        status = 'pass'
    gdb = re.search(r'^RVW_GDB_VERSION:(.*)$', output, re.M)
    return {'status': status, 'checks': sorted(checks), 'missing': sorted(expected - checks),
            'failures': failures, 'timed_out': timed_out, 'returncode': returncode,
            'connected': 'RVW_CONNECTED' in output, 'gdb_version': gdb.group(1).strip() if gdb else None}


def run(*, port=None, profile=None, elf, openocd='openocd', gdb=None, out, timeout=120, reset_pc=None,
        idcode=None):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    endpoint = None
    if profile is not None:
        from . import serve
        from .profile import load_elf
        profile = dict(profile)
        profile['image'] = load_elf(elf, profile['xlen'])
        profile['idle_loop'] = False
        endpoint = serve.Endpoint(profile, ticks_per_ms=200).start()
        port = endpoint.port
        if reset_pc is None and profile['resethaltreq']:
            reset_pc = profile['reset_vector']
    if port is None:
        raise ValueError('give a target port or a profile')
    gdb = find_gdb(gdb)
    openocd_path = shutil.which(openocd)
    if not openocd_path:
        raise FileNotFoundError(f'{openocd} not found')
    log = out / 'openocd.log'
    config = out / 'openocd.cfg'
    config.write_text(openocd_config(port, idcode=idcode, log=log))
    env = {**os.environ, 'RVW_ELF': str(Path(elf).resolve()), 'RVW_FIRST_WORD': first_word(elf),
           'RVW_OPENOCD_PIPE': f'{shlex.quote(openocd_path)} -f {shlex.quote(str(config))}'}
    if reset_pc is not None:
        env['RVW_RESET_PC'] = hex(reset_pc)
    try:
        result = run_group([gdb, '-nx', '-batch', '-x', str(SCRIPT)], env=env, timeout=timeout, capture=True)
    finally:
        if endpoint:
            endpoint.stop()
    output = (result.stdout or '') + (result.stderr or '')
    (out / 'gdb.log').write_text(output)
    summary = assess(output, result.returncode, result.timed_out, expect_reset=reset_pc is not None)
    summary['openocd_version'] = version(openocd_path)
    summary['target'] = 'model' if endpoint else f'remote_bitbang:{port}'
    write_c3(summary, out)
    return summary


def write_c3(summary, out):
    created = _dt.datetime.now(_dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    tests = []
    expected = set(CHECKS) | set(summary['missing']) | set(summary['checks'])
    failures = list(summary['failures'])
    order = [c for c in (*CHECKS, 'reset_halt') if c in summary['missing']]
    if order:
        # A GDB error stops the script: it belongs to the first check not reached.
        failures = [f'{order[0]}:{f}' if f.startswith('gdb:') else f for f in failures]
    summary['failures'] = failures
    failed = {f.split(':', 1)[0] for f in failures}
    for name in sorted(expected):
        test = {'id': f'interop.{name}'}
        if name in failed:
            message = next(f for f in summary['failures'] if f.startswith(name))
            test.update(status='fail', signature=f'debug:interop.{name}', message=message, message_complete=True)
        elif name in summary['checks']:
            test['status'] = 'pass'
        else:
            test.update(status='error', signature='inconclusive',
                        inconclusive='not reached: ' + ('; '.join(summary['failures']) or 'campaign incomplete'))
        tests.append(test)
    results = {'schema': 'rvw.results/1', 'run_id': f'{created.replace(":", "-")}-debug-interop',
               'suite': 'debug-interop', 'core': summary['target'], 'config': 'openocd-gdb', 'created': created,
               'source': {}, 'tests': tests,
               'clients': {'gdb': summary['gdb_version'], 'openocd': summary['openocd_version']},
               'scope': 'functional GDB/OpenOCD operations; a connection alone is not a pass'}
    (out / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    summary['results'] = str(out / 'results.json')
