import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('spike_adapter', Path(__file__).resolve().parents[1] / 'spike.py')


@pytest.fixture
def adapter():
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def log(*rows):
    return ''.join(f'core   {hart}: 0x{pc:016x} (0x{bits:08x}) instruction\n'
                   for hart, pc, bits in rows)


def test_standard_and_compressed(adapter, tmp_path):
    # beq +8, C.BEQZ +8; each followed by its actual target.
    src, dst = tmp_path / 'spike.log', tmp_path / 'trace.txt'
    src.write_text(log((0, 0x100, 0x463), (0, 0x108, 0xc401), (0, 0x110, 0x13)))
    adapter.convert(src, dst)
    assert dst.read_text() == 'rvw.branch-trace/1 3\nB 1 100 1\nB 2 108 1\nEND\n'


@pytest.mark.parametrize('text', [
    '',
    log((0, 0x100, 0x463)),  # missing successor
    log((0, 0x100, 0x463), (1, 0x108, 0x13)),
    log((0, 0x100, 0x463), (0, 0x999, 0x13)),  # trap/discontinuity
    log((0, 0x100, 0x263), (0, 0x104, 0x13)),  # target == fallthrough
    log((0, 0x100, 0x463)) + 'core 0: exception trap_illegal_instruction\n',
])
def test_ambiguous_refused(adapter, tmp_path, text):
    src, dst = tmp_path / 'log', tmp_path / 'trace'
    src.write_text(text)
    with pytest.raises(ValueError):
        adapter.convert(src, dst)
    assert not dst.exists()


def test_verified_hash_binding(adapter, tmp_path):
    src = tmp_path / 'loop.stderr'
    src.write_text(log((0, 0x100, 0x463), (0, 0x104, 0x13)))
    row = {'id': 'loop', 'status': 'pass', 'exit_code': 0, 'timed_out': False,
           'elf_sha256': 'a'*64, 'stderr_sha256': hashlib.sha256(src.read_bytes()).hexdigest(),
           'profile': {'counts': {'instructions': 2}}}
    report = tmp_path / 'verify.json'
    report.write_text(json.dumps({'schema': 'rvw.workload-verify/1', 'status': 'pass',
                                'oracle': {'path': '/bin/spike', 'sha256': 'b'*64},
                                'workloads': [row]}))
    assert adapter.select(report, 'loop')[0] == src
    src.write_text(src.read_text() + '\n')
    with pytest.raises(ValueError, match='hash'):
        adapter.select(report, 'loop')


def test_native_study(adapter, engine, tmp_path):
    src = tmp_path / 'loop.stderr'
    src.write_text(log((0, 0x100, 0x463), (0, 0x108, 0x13),
                       (0, 0x10c, 0x463), (0, 0x110, 0x13)))
    report = tmp_path / 'verify.json'
    report.write_text(json.dumps({'schema': 'rvw.workload-verify/1', 'status': 'pass',
        'oracle': {'path': '/native/spike', 'sha256': 'b'*64}, 'workloads': [{
            'id': 'loop', 'status': 'pass', 'exit_code': 0, 'timed_out': False,
            'elf_sha256': 'a'*64, 'stderr_sha256': adapter.digest(src),
            'profile': {'counts': {'instructions': 4}}}]}))
    result = adapter.study(report, 'loop', engine, tmp_path / 'study',
                           model='bimodal', entries=8)
    assert result['instructions'] == 4
    assert result['branches'] == 2
    assert result['direction_misses'] == 1
    assert result['mpki'] == 250
    assert result['oracle_mpki'] == 0
    assert result['verify']['sha256'] == adapter.digest(report)
    assert result['engine']['sha256'] == adapter.digest(engine)
    assert json.loads((tmp_path / 'study/report.json').read_text()) == result


@pytest.mark.parametrize('bits,offset', [(0xfe000ee3, -4), (0xdc7d, -2),
                                       (0xc401, 8), (0x463, 8)])
def test_immediate_decode(adapter, bits, offset):
    assert adapter.target(0x100, bits) == 0x100 + offset
