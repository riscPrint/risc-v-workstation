from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import threading

import pytest

from race_injection import race_injector
from rvw.results import generation as module
from rvw.results.generation import GenerationError, locate, open_current, open_generation, publish


def build(text):
    def writer(path):
        (path / 'suite').mkdir()
        (path / 'suite/result.json').write_text(text)
    return writer


def writable(path):
    for root, dirs, files in os.walk(path):
        Path(root).chmod(0o700)
        for name in files:
            (Path(root) / name).chmod(0o600)


def test_explicit_generation_and_read_only_inventory(tmp_path):
    out = tmp_path / 'out'
    first = publish(out, build('old'))
    publish(out, build('new'))
    reader = open_generation(out, first)
    assert reader.read_bytes('suite/result.json') == b'old'
    assert reader.files == (reader.entry('suite/result.json'),)
    assert reader.entry('missing') is None
    assert isinstance(reader.files, tuple)
    (out / 'current').unlink()
    assert open_generation(out, first).id == first
    with pytest.raises(GenerationError):
        open_current(out)
    for identifier in ('../escape', '0' * 31, None):
        with pytest.raises(GenerationError, match='invalid generation ID'):
            open_generation(out, identifier)


def test_locate_reuses_reader_and_keeps_explicit_id(tmp_path):
    out = tmp_path / 'out'
    first = publish(out, build('old'))
    readers = {}
    path, reader = locate(out / 'suite/result.json', readers=readers)
    publish(out, build('new'))
    assert locate(out / 'suite/result.json', readers=readers) == (path, reader)
    explicit, old = locate(out / 'generations' / first / 'suite/result.json', readers=readers)
    assert explicit == path and old.id == first
    plain = tmp_path / 'plain'
    assert locate(plain, readers=readers) == (plain, None)


def test_publish_manifest_and_immutable_reader(tmp_path):
    out = tmp_path / 'out'
    first = publish(out, build('old'))
    reader = open_current(out)
    assert reader.id == first
    assert reader.path == out / 'generations' / first
    manifest = reader.path / 'generation.json'
    assert reader.manifest_sha256 == hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert reader.read_bytes('suite/result.json') == b'old'
    assert reader.path.stat().st_mode & 0o222 == 0
    assert (reader.path / 'suite/result.json').stat().st_mode & 0o222 == 0
    second = publish(out, build('new'))
    assert first != second
    assert open_current(out).read_bytes('suite/result.json') == b'new'
    assert reader.read_bytes('suite/result.json') == b'old'
    reader.verify()


def test_reader_during_build_and_atomic_switch(tmp_path, race_injector):
    out = tmp_path / 'out'
    first = publish(out, build('old'))
    seen = []
    replace = module.os.replace

    def at_switch(src, dst):
        if Path(dst) == out / 'current':
            reader = open_current(out)
            seen.append((reader.id, reader.read_bytes('suite/result.json')))
        return replace(src, dst)

    def writer(path):
        seen.append((open_current(out).id, open_current(out).read_bytes('suite/result.json')))
        build('new')(path)

    module.os.replace = at_switch
    try:
        second = publish(out, writer)
    finally:
        module.os.replace = replace
    assert seen == [(first, b'old'), (first, b'old')]
    assert open_current(out).id == second


def test_resolve_pointer_once_during_publish(tmp_path, race_injector):
    out = tmp_path / 'out'
    first = publish(out, build('old'))
    injection = race_injector.at(module, '_read_pointer', lambda: publish(out, build('new')))
    reader = open_current(out)
    assert injection.fired and reader.id == first
    assert reader.read_bytes('suite/result.json') == b'old'


def test_concurrent_publishers_never_mix_generations(tmp_path):
    out = tmp_path / 'out'
    publish(out, build('initial'))
    barrier = threading.Barrier(2)

    def writer(text):
        def contents(path):
            build(text)(path)
            (path / 'other').write_text(text)
            barrier.wait(timeout=10)
        return publish(out, contents)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(writer, value) for value in ('a', 'b')]
        ids = {future.result(timeout=20) for future in futures}
    reader = open_current(out)
    assert reader.id in ids
    assert reader.read_bytes('other') == reader.read_bytes('suite/result.json')


@pytest.mark.parametrize('failure', ['exception', 'symlink', 'hardlink', 'reserved', 'cancel'])
def test_failed_build_never_changes_current(tmp_path, failure):
    out = tmp_path / 'out'
    first = publish(out, build('old'))
    external = tmp_path / 'external'
    external.write_text('outside')

    def writer(path):
        if failure == 'exception':
            raise ValueError('broken build')
        if failure == 'cancel':
            raise KeyboardInterrupt('cancel')
        if failure == 'symlink':
            (path / 'link').symlink_to(external)
        elif failure == 'hardlink':
            os.link(external, path / 'link')
        else:
            (path / 'generation.json').write_text('{}')

    with pytest.raises((GenerationError, ValueError, KeyboardInterrupt)):
        publish(out, writer)
    assert open_current(out).id == first
    assert not list((out / 'generations').glob('.building-*'))


@pytest.mark.parametrize('kind', ['missing', 'bad_json', 'escape', 'missing_generation', 'manifest_hash'])
def test_invalid_current_refuses(tmp_path, kind):
    out = tmp_path / 'out'
    if kind == 'missing':
        out.mkdir()
    else:
        publish(out, build('data'))
        pointer = out / 'current'
        record = json.loads(pointer.read_bytes())
        if kind == 'bad_json':
            pointer.chmod(0o600)
            pointer.write_text('{')
        else:
            record['id'] = '../escape' if kind == 'escape' else '0' * 32 if kind == 'missing_generation' else record['id']
            if kind == 'manifest_hash':
                record['manifest_sha256'] = '0' * 64
            pointer.chmod(0o600)
            pointer.write_text(json.dumps(record))
    with pytest.raises(GenerationError):
        open_current(out)


@pytest.mark.parametrize('kind', ['deleted', 'replaced', 'edited', 'symlink', 'extra'])
def test_reader_refuses_vanished_or_changed_generation(tmp_path, kind):
    out = tmp_path / 'out'
    publish(out, build('old'))
    reader = open_current(out)
    path = reader.path
    writable(path)
    if kind == 'deleted':
        shutil.rmtree(path)
    elif kind == 'replaced':
        path.rename(path.with_name('old'))
        path.mkdir()
    elif kind == 'edited':
        (path / 'suite/result.json').write_bytes(b'bad')
    elif kind == 'symlink':
        (path / 'suite/result.json').unlink()
        (path / 'suite/result.json').symlink_to(tmp_path / 'missing')
    else:
        (path / 'extra').write_text('extra')
    with pytest.raises(GenerationError):
        reader.verify()
    with pytest.raises(GenerationError):
        open_current(out)
    if kind in ('deleted', 'replaced'):
        with pytest.raises(GenerationError):
            _ = reader.path
    if kind != 'extra':
        with pytest.raises(GenerationError):
            reader.read_bytes('suite/result.json')


def test_generation_read_rejects_escaping_paths(tmp_path):
    publish(tmp_path / 'out', build('old'))
    reader = open_current(tmp_path / 'out')
    for path in ('../outside', '/etc/passwd', 'unknown', 'generation.json'):
        with pytest.raises(GenerationError):
            reader.read_bytes(path)
