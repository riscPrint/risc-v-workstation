"""`rvw doctor --conformance`: C1 option checks against a fake adapter with selectable faults."""
import json
import struct
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.fast

from rvw.doctor.c1suite import conformance, looping_copy

FAKE = r'''
import json, os, sys, random
from pathlib import Path
fault = os.environ.get('FAKE_FAULT', '')
argv = sys.argv[1:]
cmd = argv[0]
def opt(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default
if cmd == 'build':
    sys.exit(0)
def run_one(job):
    out = Path(job['out']); out.mkdir(parents=True, exist_ok=True)
    data = Path(job['elf']).read_bytes()
    if data[:4] != b'\x7fELF':
        record = dict(schema='rvw.run/1', status='error', message='not an ELF')
    else:
        looping = int.from_bytes(data[84:88], 'little') == 0x6f
        cycles = 100 if fault != 'nondeterministic' else random.randint(100, 200)
        limit = int(job.get('max_cycles') or 200000)
        status = 'timeout' if looping or limit < cycles else 'pass'
        if fault == 'pass_on_loop' and looping:
            status = 'pass'
        record = dict(schema='rvw.run/1', core='fake', config=job.get('config') or 'default', status=status,
                      seed=int(job['seed']) if job.get('seed') is not None else 1,
                      max_cycles=limit, mem_latency=None if job.get('mem_latency') is None else int(job['mem_latency']),
                      cycles=min(cycles, limit), instret=10, rtl_sha256='a' * 64, elf_sha256='b' * 64,
                      irq_schedule=job.get('irq_schedule'))
        if fault == 'drop_seed':
            record['seed'] = 1
        if looping and job.get('wall_timeout') is not None:
            record['wall_clock_timeout'] = True
        replay = [sys.executable, __file__, 'run', '--elf', job['elf'], '--out', job['out'] + '-replay',
                  '--seed', str(record['seed']), '--max-cycles', str(limit)]
        if record['mem_latency'] is not None:
            replay += ['--mem-latency', str(record['mem_latency'])]
        record['replay'] = ' '.join(replay)
    (out / 'result.json').write_text(json.dumps(record))
    return record
if cmd == 'run':
    if opt('--config', 'default') != 'default':
        sys.exit(2)
    job = dict(elf=opt('--elf'), out=opt('--out'), seed=opt('--seed'), max_cycles=opt('--max-cycles'),
               mem_latency=opt('--mem-latency'), irq_schedule=opt('--irq-schedule'), wall_timeout=opt('--wall-timeout'))
    r = run_one(job)
    sys.exit(2 if fault == 'replay_exit' and '-replay' in job['out'] else 0 if r['status'] == 'pass' else 2 if r['status'] == 'error' else 1)
if cmd == 'run-many':
    jobs = [json.loads(l) for l in Path(opt('--manifest')).read_text().splitlines()]
    sys.exit(0 if all(run_one(j)['status'] == 'pass' for j in jobs) else 1)
'''


def elf32(path, words=(0x00100093, 0x00000013)):
    """A minimal ELF32 with one PT_LOAD at 0x80000000; code at file offset 84."""
    code = b''.join(struct.pack('<I', w) for w in words)
    header = bytearray(52)
    header[:7] = b'\x7fELF\x01\x01\x01'
    struct.pack_into('<HHIIIIIHHHHHH', header, 16, 2, 243, 1, 0x80000000, 52, 0, 0, 52, 32, 1, 0, 0, 0)
    phdr = struct.pack('<IIIIIIII', 1, 84, 0x80000000, 0x80000000, len(code), len(code), 5, 4)
    path.write_bytes(bytes(header) + phdr + code)
    return path


@pytest.fixture
def adapter(tmp_path):
    script = tmp_path / 'fake_adapter.py'
    script.write_text(FAKE)
    cfg = SimpleNamespace(adapter=[sys.executable, str(script)], path=tmp_path / 'rvw.toml', configs=['default'],
                          default_config='default', build_timeout_s=30, wall_timeout=True)
    return cfg, elf32(tmp_path / 'smoke.elf')


def statuses(checks):
    return {c['name'].removeprefix('conformance.'): c['status'] for c in checks}


def test_looping_copy_patches_the_entry(tmp_path):
    elf = elf32(tmp_path / 'p.elf')
    out = looping_copy(elf, tmp_path / 'loop.elf')
    data = out.read_bytes()
    assert struct.unpack_from('<I', data, 84)[0] == 0x6f
    assert data[:84] == elf.read_bytes()[:84]
    with pytest.raises(ValueError):
        looping_copy(tmp_path / 'p.elf' if False else _write(tmp_path / 'x', b'not elf'), tmp_path / 'y')


def _write(path, data):
    path.write_bytes(data)
    return path


def test_conforming_adapter_is_ready(adapter, tmp_path, monkeypatch):
    cfg, elf = adapter
    monkeypatch.delenv('FAKE_FAULT', raising=False)
    result = statuses(conformance(cfg, {'configs': ['default']}, elf, home=tmp_path, timeout=60))
    assert set(result.values()) == {'ready'}, result
    assert {'replay', 'run_many', 'no_completion', 'wall_timeout', 'determinism'} <= result.keys()


@pytest.mark.parametrize('fault,failing', [
    ('nondeterministic', 'determinism'),
    ('drop_seed', 'options.recorded'),
    ('pass_on_loop', 'no_completion'),
    ('replay_exit', 'replay'),
])
def test_each_fault_is_reported(adapter, tmp_path, monkeypatch, fault, failing):
    cfg, elf = adapter
    monkeypatch.setenv('FAKE_FAULT', fault)
    result = statuses(conformance(cfg, {'configs': ['default']}, elf, home=tmp_path, timeout=60))
    assert result[failing] == 'error', result
