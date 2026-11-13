"""Explicit C1 option conformance checks for a project's adapter (`rvw doctor --conformance`).

Each check runs the adapter with one option or option pair and compares the written C1 result
with the request. A check that cannot run its program, or whose evidence is missing, is not ready.
Nothing here names a core.
"""
import json
from pathlib import Path
import shlex
import struct
import tempfile

from rvw.common.proc import run_group
from rvw.results.schema import validate_run


def _check(name, ok, detail, fix):
    return dict(name='conformance.' + name, status='ready' if ok else 'error', detail=detail, fix=fix)


def _result(directory):
    path = Path(directory) / 'result.json'
    return json.loads(path.read_text()) if path.is_file() else None


def looping_copy(elf, out):
    """A copy of a RISC-V ELF whose entry instruction is `jal x0, 0`: a program that never ends."""
    data = bytearray(Path(elf).read_bytes())
    if data[:4] != b'\x7fELF' or data[5] != 1:
        raise ValueError('not a little-endian ELF')
    wide = data[4] == 2
    if wide:
        entry, phoff = struct.unpack_from('<QQ', data, 24)
        phentsize, phnum = struct.unpack_from('<HH', data, 54)
    else:
        entry, phoff = struct.unpack_from('<II', data, 24)
        phentsize, phnum = struct.unpack_from('<HH', data, 42)
    for i in range(phnum):
        at = phoff + i * phentsize
        if wide:
            kind, _, offset, vaddr, _, filesz = struct.unpack_from('<IIQQQQ', data, at)
        else:
            kind, offset, vaddr, _, filesz = struct.unpack_from('<IIIII', data, at)
        if kind == 1 and vaddr <= entry and entry + 4 <= vaddr + filesz:
            struct.pack_into('<I', data, offset + entry - vaddr, 0x0000006f)
            Path(out).write_bytes(data)
            return out
    raise ValueError('the ELF entry is not in a loaded segment')


def conformance(cfg, info, elf, *, home, timeout=300):
    """Run the checks for the project config `cfg` (rvw.regress.config.CoreConfig)."""
    checks = []
    adapter, cwd = list(cfg.adapter), cfg.path.parent
    elf = str(Path(elf).resolve())

    def run(directory, *args):
        process = run_group([*adapter, 'run', '--elf', elf, '--out', str(directory), *map(str, args), '--json'],
                            cwd=cwd, timeout=timeout, capture=True)
        return process, _result(directory)

    with tempfile.TemporaryDirectory(prefix='rvw-doctor-c1-') as tmp:
        tmp = Path(tmp)
        configs = info.get('configs') or cfg.configs
        for config in configs:
            build = run_group([*adapter, 'build', '--config', config, '--json'], cwd=cwd,
                              timeout=cfg.build_timeout_s, capture=True)
            checks.append(_check(f'build.{config}', build.returncode == 0,
                                 {'exit_code': build.returncode, 'stderr': (build.stderr or '')[-800:]},
                                 'Every config in info --json must build.'))

        first, one = run(tmp / 'fixed-a', '--seed', 7, '--mem-latency', 0, '--max-cycles', 100000)
        _, two = run(tmp / 'fixed-b', '--seed', 7, '--mem-latency', 0, '--max-cycles', 100000)
        errors = validate_run(one) if one else ['no result.json']
        recorded = bool(one) and not errors and one.get('status') == 'pass' and one.get('seed') == 7 \
            and one.get('mem_latency') == 0 and one.get('max_cycles') == 100000 \
            and one.get('config') == cfg.default_config and one.get('replay')
        checks.append(_check('options.recorded', recorded,
                             {'exit_code': first.returncode, 'errors': errors,
                              'result': {k: (one or {}).get(k) for k in ('status', 'seed', 'mem_latency', 'max_cycles', 'config')}},
                             'Record the requested seed, mem_latency, max_cycles and config in result.json; the ELF must pass.'))
        same = bool(one and two) and all(one.get(k) == two.get(k) for k in ('status', 'cycles', 'instret', 'rtl_sha256'))
        checks.append(_check('determinism', same and recorded,
                             {k: [(one or {}).get(k), (two or {}).get(k)] for k in ('status', 'cycles', 'instret', 'rtl_sha256')},
                             'The same seed and fixed latency must give the same cycles, instret and RTL identity.'))

        cycles = (one or {}).get('cycles') or 0
        limit = max(1, min(50, cycles // 2)) if cycles else 5
        _, short = run(tmp / 'limit', '--seed', 7, '--mem-latency', 0, '--max-cycles', limit)
        checks.append(_check('max_cycles', bool(short) and short.get('status') == 'timeout'
                             and short.get('max_cycles') == limit and (short.get('cycles') or 0) <= limit + 1,
                             {'max_cycles': limit, 'status': (short or {}).get('status'), 'cycles': (short or {}).get('cycles')},
                             'A run that reaches --max-cycles before completion must end as timeout.'))

        manifest = tmp / 'jobs.jsonl'
        jobs = [dict(elf=elf, out=str(tmp / 'many-1'), seed=3, mem_latency=0, max_cycles=100000),
                dict(elf=elf, out=str(tmp / 'many-2'), seed=4, max_cycles=100000)]
        manifest.write_text(''.join(json.dumps(j) + '\n' for j in jobs))
        many = run_group([*adapter, 'run-many', '--manifest', str(manifest), '--jobs', '1', '--json'],
                         cwd=cwd, timeout=timeout * 2, capture=True)
        results = [_result(j['out']) for j in jobs]
        checks.append(_check('run_many', many.returncode == 0 and all(r and r.get('status') == 'pass' for r in results)
                             and [r.get('seed') for r in results] == [3, 4]
                             and results[0].get('mem_latency') == 0 and results[1].get('mem_latency') is None,
                             {'exit_code': many.returncode, 'results': [{k: (r or {}).get(k) for k in ('status', 'seed', 'mem_latency')}
                                                                       for r in results]},
                             'run-many must run each manifest line with its own seed and latency.'))

        replayed = None
        replay = (one or {}).get('replay')
        if replay:
            words = shlex.split(replay)
            out = words[words.index('--out') + 1] if '--out' in words else None
            process = run_group(['bash', '-c', replay], cwd=home, timeout=timeout, capture=True)
            replayed = _result(out) if out else None
        checks.append(_check('replay', bool(replayed) and all(replayed.get(k) == one.get(k)
                                                             for k in ('status', 'cycles', 'instret', 'seed', 'rtl_sha256', 'elf_sha256')),
                             {'replay': replay, 'replayed': {k: (replayed or {}).get(k) for k in ('status', 'cycles', 'instret', 'seed')}},
                             'The recorded replay command must reproduce status, cycles, instret, seed and identity.'))

        process, unknown = run(tmp / 'config', '--config', 'rvw-doctor-no-such-config')
        # A usage error may stop before any result; a written result must say error.
        checks.append(_check('unknown_config', process.returncode == 2 and (unknown is None or unknown.get('status') == 'error'),
                             {'exit_code': process.returncode, 'status': (unknown or {}).get('status')},
                             'An unknown config must give status error and exit 2.'))
        bad = tmp / 'not-an-elf'
        bad.write_bytes(b'not an ELF file\n')
        process = run_group([*adapter, 'run', '--elf', str(bad), '--out', str(tmp / 'bad'), '--json'],
                            cwd=cwd, timeout=timeout, capture=True)
        result = _result(tmp / 'bad')
        checks.append(_check('bad_elf', process.returncode == 2 and (result or {}).get('status') == 'error',
                             {'exit_code': process.returncode, 'status': (result or {}).get('status')},
                             'An input that is not an ELF must give status error and exit 2.'))

        process, quiet = run(tmp / 'irq', '--seed', 7, '--mem-latency', 0, '--irq-schedule', '1:0x0')
        checks.append(_check('irq_schedule', bool(quiet) and quiet.get('status') == 'pass' and quiet.get('irq_schedule') == '1:0x0',
                             {'exit_code': process.returncode, 'status': (quiet or {}).get('status'),
                              'irq_schedule': (quiet or {}).get('irq_schedule')},
                             'An all-zero interrupt schedule must be accepted and recorded.'))
        hang = looping_copy(elf, tmp / 'looping.elf')
        process = run_group([*adapter, 'run', '--elf', str(hang), '--out', str(tmp / 'loop'), '--seed', '7',
                             '--mem-latency', '0', '--max-cycles', '2000', '--json'], cwd=cwd, timeout=timeout, capture=True)
        loop = _result(tmp / 'loop')
        checks.append(_check('no_completion', bool(loop) and loop.get('status') == 'timeout' and process.returncode == 1,
                             {'exit_code': process.returncode, 'status': (loop or {}).get('status')},
                             'A program that never writes tohost must end as timeout with exit 1, never pass.'))
        if cfg.wall_timeout:
            process = run_group([*adapter, 'run', '--elf', str(hang), '--out', str(tmp / 'wall'), '--seed', '7',
                                 '--max-cycles', '1000000000', '--wall-timeout', '3', '--json'],
                                cwd=cwd, timeout=timeout, capture=True)
            wall = _result(tmp / 'wall')
            checks.append(_check('wall_timeout', bool(wall) and wall.get('status') == 'timeout'
                                 and wall.get('wall_clock_timeout') is True,
                                 {'exit_code': process.returncode, 'status': (wall or {}).get('status'),
                                  'wall_clock_timeout': (wall or {}).get('wall_clock_timeout')},
                                 'With wall_timeout declared, --wall-timeout must end a hung run as a wall-clock timeout.'))
    return checks
