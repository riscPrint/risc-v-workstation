"""Debug profile (`rvw.debug-profile/1`): the declared Debug Module option set of one target.

A profile lives in project data beside `rvw.toml` (`[debug_module] profile = "..."`).
It names the transport, the Debug Specification version and every optional
feature the campaigns may test. Undeclared options are not tested. A check for
an option the profile does not declare is reported as unsupported, never as a pass.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import tomllib

SCHEMA = 'rvw.debug-profile/1'

DEFAULTS = dict(
    version='1.0', xlen=64, harts=1, unavailable=[], hartsellen=None, hart_array=False,
    haltgroups=False, progbufsize=2, impebreak=False, datacount=2, autoexec=True,
    abstract=['gpr', 'csr'], aarsizes=None, csr_missing_cmderr=2, abstract_latency=0,
    hartreset=False, resethaltreq=True, modes='MSU', reset_vector=0x80000000,
    scratch=None, scratch_size=0x1000, memory=None, triggers=None, sba=None,
    ticks_per_access=1, ips=1, fence_i=True, idle_loop=True, busy_probe=True, elf=None,
    postincrement=True, skip=None,
)
TRIGGER_DEFAULTS = dict(count=0, types=[6], matches=[0, 1, 2, 3, 4, 5, 8, 9, 12, 13], actions=[0, 1],
                        timing=[0, 1], chain=True, unsupported_type=15, tcontrol=True, maskmax=31,
                        version=1, store_data_timing='after', load_data_timing='after', sizes=[0],
                        accesses=['execute', 'load', 'store'])
SBA_DEFAULTS = dict(sizes=[8, 16, 32, 64], asize=64, latency=0, misaligned_error=3, size_error=4)
TRANSPORTS = {'model', 'jtag-model', 'remote_bitbang', 'dmi_process'}


class ProfileError(ValueError):
    pass


def _int(value, name):
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError:
            raise ProfileError(f'{name} must be an integer') from None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ProfileError(f'{name} must be an integer')
    return value


def normalize(raw, *, base=None):
    if raw.get('schema', SCHEMA) != SCHEMA:
        raise ProfileError(f'profile schema must be {SCHEMA}')
    unknown = set(raw) - set(DEFAULTS) - {'schema', 'transport', 'name'}
    if unknown:
        raise ProfileError(f'unknown profile keys: {", ".join(sorted(unknown))}')
    p = {**DEFAULTS, **{k: v for k, v in raw.items() if k in DEFAULTS}}
    p['name'] = raw.get('name', 'debug-target')
    if p['version'] not in ('0.13.2', '1.0'):
        raise ProfileError('version must be "0.13.2" or "1.0"')
    if p['xlen'] not in (32, 64):
        raise ProfileError('xlen must be 32 or 64')
    for key in ('harts', 'progbufsize', 'datacount', 'abstract_latency', 'ticks_per_access', 'ips',
                'reset_vector', 'scratch_size', 'csr_missing_cmderr'):
        p[key] = _int(p[key], key)
    if not 1 <= p['harts'] <= 1 << 20:
        raise ProfileError('harts must be 1..2**20')
    if not 0 <= p['progbufsize'] <= 16 or not 0 <= p['datacount'] <= 12:
        raise ProfileError('progbufsize must be 0..16 and datacount 0..12')
    p['unavailable'] = [_int(v, 'unavailable') for v in p['unavailable']]
    p['hartsellen'] = _int(p['hartsellen'], 'hartsellen') if p['hartsellen'] is not None else max(1, p['harts'].bit_length())
    if not set(p['modes']) <= set('MSU') or 'M' not in p['modes']:
        raise ProfileError('modes must contain M and only M, S, U')
    abstract = set(p['abstract'])
    if not abstract <= {'gpr', 'csr', 'fpr', 'memory', 'quick'}:
        raise ProfileError('abstract must list gpr, csr, fpr, memory or quick')
    p['abstract'] = sorted(abstract)
    p['aarsizes'] = [2, 3] if p['aarsizes'] is None and p['xlen'] == 64 else (p['aarsizes'] or [2])
    p['scratch'] = _int(p['scratch'], 'scratch') if p['scratch'] is not None else None
    if p['memory'] is None:
        start = p['scratch'] if p['scratch'] is not None else p['reset_vector']
        low = min(start, p['reset_vector'])
        p['memory'] = [dict(base=low, size=max(0x10000, start + p['scratch_size'] - low))]
    p['memory'] = [dict(base=_int(r['base'], 'memory.base'), size=_int(r['size'], 'memory.size'),
                        kind=r.get('kind', 'ram'), sberror=r.get('sberror'))
                   for r in p['memory']]
    for region in p['memory']:
        if region['kind'] not in ('ram', 'readonly', 'error', 'off'):
            raise ProfileError('memory kind must be ram, readonly, error or off')
    triggers = {**TRIGGER_DEFAULTS, **(p['triggers'] or {})}
    unknown = set(triggers) - set(TRIGGER_DEFAULTS)
    if unknown:
        raise ProfileError(f'unknown trigger keys: {", ".join(sorted(unknown))}')
    triggers['count'] = _int(triggers['count'], 'triggers.count')
    for key in ('store_data_timing', 'load_data_timing'):
        if triggers[key] not in ('before', 'after', None, 'none'):
            raise ProfileError(f'triggers.{key} must be "before", "after" or "none"')
        triggers[key] = None if triggers[key] == 'none' else triggers[key]
    if not set(triggers['accesses']) <= {'execute', 'load', 'store'} or 'execute' not in triggers['accesses']:
        raise ProfileError('triggers.accesses must list execute and optionally load and store')
    if triggers['load_data_timing'] == 'before':
        raise ProfileError('a load-data trigger cannot fire before the load returns data')
    p['triggers'] = triggers
    skip = p['skip'] or {}
    if not isinstance(skip, dict) or not all(isinstance(v, str) and v for v in skip.values()):
        raise ProfileError('skip must map check ids to a reason string')
    p['skip'] = skip
    if p['sba'] is not None:
        sba = {**SBA_DEFAULTS, **p['sba']}
        if set(sba) - set(SBA_DEFAULTS):
            raise ProfileError('unknown sba keys')
        if not set(sba['sizes']) <= {8, 16, 32, 64, 128}:
            raise ProfileError('sba.sizes must be bit widths 8..128')
        p['sba'] = sba
    else:
        p['sba'] = None
    transport = dict(raw.get('transport', {'kind': 'model'}))
    if transport.get('kind') not in TRANSPORTS:
        raise ProfileError(f'transport.kind must be one of {", ".join(sorted(TRANSPORTS))}')
    if transport['kind'] == 'dmi_process':
        command = transport.get('command')
        if not isinstance(command, list) or not command or not all(isinstance(c, str) for c in command):
            raise ProfileError('dmi_process transport needs a command list')
        if base is not None:
            transport['command'] = [str((base / c)) if c.startswith(('./', '../')) else c for c in command]
    if transport['kind'] == 'remote_bitbang':
        transport['host'] = transport.get('host', '127.0.0.1')
        transport['port'] = _int(transport.get('port', 0), 'transport.port')
    p['transport'] = transport
    if p['elf'] is not None:
        elf = Path(p['elf'])
        if base is not None and not elf.is_absolute():
            elf = base / elf
        p['elf'] = str(elf)
        p['image'] = load_elf(elf, p['xlen'])
    return p


def load_elf(path, xlen):
    """PT_LOAD segments of a little-endian RISC-V ELF as (address, bytes) pairs."""
    import struct
    data = Path(path).read_bytes()
    if data[:4] != b'\x7fELF' or data[5] != 1:
        raise ProfileError(f'{path}: not a little-endian ELF')
    wide = data[4] == 2
    if wide != (xlen == 64):
        raise ProfileError(f'{path}: ELF class does not match xlen {xlen}')
    if wide:
        phoff, = struct.unpack_from('<Q', data, 0x20)
        phentsize, phnum = struct.unpack_from('<HH', data, 0x36)
    else:
        phoff, = struct.unpack_from('<I', data, 0x1c)
        phentsize, phnum = struct.unpack_from('<HH', data, 0x2a)
    segments = []
    for i in range(phnum):
        at = phoff + i * phentsize
        if wide:
            kind, _, offset, vaddr, paddr, filesz, memsz = struct.unpack_from('<IIQQQQQ', data, at)
        else:
            kind, offset, vaddr, paddr, filesz, memsz = struct.unpack_from('<IIIIII', data, at)
        if kind == 1 and memsz:
            segments.append((paddr, data[offset:offset + filesz] + bytes(memsz - filesz)))
    return segments


def load(path):
    path = Path(path)
    data = path.read_bytes()
    try:
        raw = tomllib.loads(data.decode())
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ProfileError(f'{path}: {exc}') from None
    profile = normalize(raw, base=path.parent)
    # A campaign needs a named target. Without [transport], normalize selects the built-in model.
    profile['transport_declared'] = 'transport' in raw
    profile['path'] = str(path)
    profile['sha256'] = hashlib.sha256(data).hexdigest()
    return profile


def from_project(project=None):
    from rvw.common.project import load_project
    selected = load_project(project)
    if selected is None or selected.get('debug_module', 'profile') is None:
        raise ProfileError('no profile given and no project [debug_module] profile')
    return load(selected.get('debug_module', 'profile'))
