"""Workload pin, reference and incomplete-output regressions."""
import copy
import hashlib
import json
from pathlib import Path

import pytest

from rvw.workloads import core
from rvw.cli import main

pytestmark = pytest.mark.fast


def put(path, value):
    path.write_text(json.dumps(value))
    return str(path)


@pytest.fixture
def built(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'input').write_text('fixed input')
    elf = tmp_path / 'test.elf'
    elf.write_bytes(b'\x7fELF\x02\x01' + bytes(12) + b'\xf3\x00' + bytes(44))
    report = {'schema': 'rvw.workload-build/1', 'source_sha256': core.tree_hash(source),
              'workloads': [{'id': 'test', 'mode': 'bare', 'elf': str(elf),
                             'elf_sha256': core.digest(elf), 'args': [],
                             'stdout_sha256': core.EMPTY}]}
    spike = tmp_path / 'spike'
    spike.write_text('#!/bin/sh\nif [ "$1" = "--help" ]; then echo "Spike test"; exit 0; fi\nexit 0\n')
    spike.chmod(0o755)
    return tmp_path, report, spike


def check(built):
    root, report, spike = built
    return core.verify(put(root / 'build.json', report), root / 'check', str(spike), 1)


def test_default_has_pins_and_fp():
    data = core.load()
    assert len(data['revision']) == 40
    assert {w['id'] for w in data['workloads']} == {
        'crc32', 'matmult-int', 'slre', 'nettle-aes', 'minver', 'nbody'}
    for w in data['workloads']:
        assert '-march=rv64gc' in w['build']
        assert '-ffp-contract=off' in w['build']
        assert w['stdout_sha256'] == core.EMPTY


def test_cli_list(capsys):
    assert main(['workloads', 'list', '--json']) == 0
    assert json.loads(capsys.readouterr().out)['schema'] == 'rvw.workloads/1'


@pytest.mark.parametrize('bad', ['duplicate', 'id', 'mode', 'hash', 'compiler', 'empty'])
def test_reject_bad_manifest(tmp_path, bad):
    data = copy.deepcopy(core.load())
    if bad == 'duplicate':
        data['workloads'].append(data['workloads'][0])
    elif bad == 'id':
        data['workloads'][0]['id'] = '../bad'
    elif bad == 'mode':
        data['workloads'][0]['mode'] = 'native'
    elif bad == 'hash':
        data['workloads'][0]['stdout_sha256'] = ''
    elif bad == 'compiler':
        data['compiler_version'] = ''
    else:
        data['workloads'] = []
    with pytest.raises(ValueError):
        core.load(put(tmp_path / 'manifest.json', data))


def test_spike_help_identity(built):
    assert core.identity(str(built[2]))['version'] == 'Spike test'


def test_complete_reference_exit(built):
    report = check(built)
    assert report['status'] == 'pass'
    assert len(report['workloads']) == 1
    assert report['oracle']['sha256'] == core.digest(built[2])


@pytest.mark.parametrize('mode', ['nonzero', 'output', 'timeout'])
def test_incomplete_or_wrong_output_fails(built, mode):
    root, report, spike = built
    action = {'nonzero': 'exit 1', 'output': 'echo wrong', 'timeout': 'sleep 20'}[mode]
    spike.write_text('#!/bin/sh\nif [ "$1" = "--help" ]; then echo Spike; exit 0; fi\n' + action + '\n')
    result = check(built)
    assert result['status'] == 'fail'
    assert result['workloads'][0]['timed_out'] == (mode == 'timeout')


@pytest.mark.parametrize('changed', ['elf', 'input'])
def test_changed_bytes_refused(built, changed):
    root, report, spike = built
    path = Path(report['workloads'][0]['elf']) if changed == 'elf' else root / 'source/input'
    path.write_text('changed')
    with pytest.raises(ValueError, match='changed'):
        check(built)


def test_empty_report_refused(built):
    built[1]['workloads'] = []
    with pytest.raises(ValueError, match='nonempty'):
        check(built)


def test_wrong_oracle_mode_refused(built):
    built[1]['workloads'][0]['mode'] = 'linux'
    with pytest.raises(ValueError, match='requires'):
        check(built)


def test_linux_qemu_hook(built):
    root, report, spike = built
    qemu = root / 'qemu-riscv64'
    spike.rename(qemu)
    qemu.write_text('#!/bin/sh\nif [ "$1" = "--version" ]; then echo QEMU; fi\nexit 0\n')
    report['workloads'][0]['mode'] = 'linux'
    assert check((root, report, qemu))['status'] == 'pass'


def test_fresh_generation_required(built):
    check(built)
    with pytest.raises(FileExistsError):
        check(built)


def test_source_links(tmp_path):
    (tmp_path / 'a').write_text('a')
    (tmp_path / 'link').symlink_to('a')
    core.tree_hash(tmp_path)
    (tmp_path / 'link').unlink()
    (tmp_path / 'link').symlink_to('/etc/passwd')
    with pytest.raises(ValueError, match='external'):
        core.tree_hash(tmp_path)


def test_build_local_hook_and_wrong_elf(tmp_path):
    source = tmp_path / 'input'
    source.mkdir()
    (source / 'x.c').write_text('int main() {return 0;}')
    cc = tmp_path / 'cc'
    cc.write_text('#!/usr/bin/env python3\nimport sys\nfrom pathlib import Path\n'
                  'if "--version" in sys.argv: print("test compiler 1"); sys.exit(0)\n'
                  'Path(sys.argv[-1]).write_bytes(b"bad ELF")\n')
    cc.chmod(0o755)
    manifest = {'schema': 'rvw.workloads/1', 'compiler_version': 'test compiler 1',
                'source_sha256': core.tree_hash(source), 'workloads': [{
                    'id': 'local-spec', 'mode': 'linux', 'stdout_sha256': core.EMPTY,
                    'build': ['{cc}', '{out}/workload.elf']}]}
    file = put(tmp_path / 'local.json', manifest)
    with pytest.raises(ValueError, match='RV64 ELF'):
        core.build(file, source, tmp_path / 'out', str(cc))
    assert not (tmp_path / 'out/build.json').exists()
    manifest['compiler_version'] = 'wrong'
    put(Path(file), manifest)
    with pytest.raises(ValueError, match='compiler pin'):
        core.build(file, source, tmp_path / 'other', str(cc))
