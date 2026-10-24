"""C8 regressions at parser, baseline, guard and publication boundaries."""
import hashlib
import json
from pathlib import Path

import pytest

from race_injection import race_injector
from rvw.cov import code, functional
from .test_code import dat


@pytest.mark.parametrize('revert', [False, True])
def test_dat_parse_and_identity_share_capture(tmp_path, race_injector, revert):
    path = dat(tmp_path / 'a.dat', [1])
    original = path.read_bytes()
    changed = original.replace(b"' 1", b"' 0")
    # iter_dat returns an iterator. Replacing at entry precedes its first read.
    edit = race_injector.file(code, 'iter_dat', path, changed, replace=True)
    restore = race_injector.at(code.SourceMap, 'location', lambda: path.write_bytes(original)) if revert else None
    result = code.merge([str(path)], tmp_path)
    assert edit.fired and (restore is None or restore.fired)
    assert result['points'][0]['count'] == 1
    assert next(iter(result['tests'].values()))['sha256'] == hashlib.sha256(original).hexdigest()


@pytest.mark.parametrize('revert', [False, True])
def test_trace_hash_matches_parsed_stream(tmp_path, monkeypatch, race_injector, revert):
    path = tmp_path / 'trace.jsonl'
    header = {'schema': 'rvw.rvfi/1', 'xlen': 64, 'isa': 'rv64i', 'core': 'unknown'}
    row = {'order': 0, 'insn': '0x00100093', 'rd': 1, 'mode': 3}
    original = (json.dumps(header) + '\n' + json.dumps(row) + '\n').encode()
    path.write_bytes(original)
    changed = original.replace(b'00100093', b'00200113')
    real_open = Path.open

    def boundary():
        pass

    # Shared fixture controls the named text-stream boundary. Only the production
    # parser's text open triggers it, after the descriptor is already open.
    import types
    hook = types.SimpleNamespace(boundary=boundary)
    def open_trace(p, *args, **kwargs):
        stream = real_open(p, *args, **kwargs)
        if p.name == 'trace.jsonl' and (not args or 'b' not in args[0]):
            hook.boundary()
        return stream
    edit = race_injector.file(hook, 'boundary', path, changed, replace=True)
    monkeypatch.setattr(Path, 'open', open_trace)
    restore = race_injector.at(functional, 'observations', lambda: path.write_bytes(original)) if revert else None
    result = functional.functional([path])
    assert edit.fired and (restore is None or restore.fired)
    assert list(result['traces']) == [hashlib.sha256(original).hexdigest()]
    bins = result['groups']['mnemonic_mode']['hits']
    assert bins == [{'bin': ['addi', 'M'], 'count': 1}]


@pytest.mark.parametrize('revert', [False, True])
def test_source_mapping_and_hash_use_one_capture(tmp_path, race_injector, revert):
    source = tmp_path / 'logic.v'
    source.write_text('assign a=b; // @ Original.scala:1\n')
    path = dat(tmp_path / 'a.dat', [1])
    original = source.read_bytes()
    edit = race_injector.file(code.SourceMap, 'location', source,
                              b'assign a=b; // @ Changed.scala:2\n', when='before' if revert else 'after', replace=True,
                              revert=revert)
    result = code.merge([str(path)], tmp_path)
    assert edit.fired
    assert result['points'][0]['scala']['file'] == ('Changed.scala' if revert else 'Original.scala')
    expected = b'assign a=b; // @ Changed.scala:2\n' if revert else original
    assert result['sources']['logic.v']['sha256'] == hashlib.sha256(expected).hexdigest()


def test_dat_export_reads_the_merge_capture(tmp_path, monkeypatch, race_injector):
    from rvw.cov import cli
    from rvw.common.proc import Result
    path = dat(tmp_path / 'a.dat', [1])
    edit = race_injector.file(code, 'merge', path, path.read_bytes().replace(b"' 1", b"' 0"),
                              when='after', replace=True)
    # Only the external export process is stubbed; it must receive the already
    # captured .dat, with exactly the bytes the structured parser consumed.
    def export(argv, **kwargs):
        Path(argv[2]).write_bytes(Path(argv[3]).read_bytes())
        return Result(0)
    monkeypatch.setattr(cli, 'run_group', export, raising=False)
    result = cli.execute_json('merge', inputs=[str(path)], source_root=str(tmp_path),
                              dat=str(tmp_path / 'merged.dat'))
    assert edit.fired
    assert result['points'][0]['count'] == 1
    assert code.read_counts(tmp_path / 'merged.dat') == {result['points'][0]['id']: 1}


@pytest.mark.parametrize('kind', ['c1', 'c3'])
def test_run_metadata_uses_the_first_capture(tmp_path, race_injector, kind):
    dat(tmp_path / 'coverage.dat', [1])
    run = {'schema': 'rvw.run/1', 'status': 'pass', 'elf': 'original.elf',
           'artifacts': {'coverage': 'coverage.dat'}}
    path = tmp_path / 'result.json'
    path.write_text(json.dumps(run))
    specification = path
    if kind == 'c3':
        specification = tmp_path / 'results.json'
        specification.write_text(json.dumps({'schema': 'rvw.results/1', 'run_id': 'r', 'suite': 's',
                                              'core': 'test', 'config': 'tiny', 'created': 'now', 'source': {},
                                              'tests': [{'id': 'test', 'status': 'pass', 'run': 'result.json'}]}))
    edit = race_injector.file(code, '_run_input', path,
                              json.dumps({**run, 'elf': 'changed.elf'}).encode(), replace=True, revert=True)
    result = code.merge([str(specification)], tmp_path)
    assert edit.fired
    assert next(iter(result['tests'].values()))['run']['elf'] == 'original.elf'


def test_annotations_read_the_report_capture_and_publish_a_generation(tmp_path, race_injector):
    from rvw.cov import cli
    from rvw.results.generation import open_current
    source = tmp_path / 'logic.v'
    source.write_text('assign original = value;\n')
    database = tmp_path / 'coverage.json'
    database.write_text(json.dumps(code.merge([str(dat(tmp_path / 'a.dat', [0]))], tmp_path)))
    edit = race_injector.file(code, 'report', source, b'assign changed = value;\n',
                              when='after', replace=True)
    target = tmp_path / 'annotations'
    result = cli.execute_json('report', database=str(database), annotate=str(target))
    assert edit.fired
    directory = target / 'generations' / result['annotations']['generation'] if result.get('annotations') else target
    assert 'original' in next(directory.glob('*.txt')).read_text()
    assert 'changed' not in next(directory.glob('*.txt')).read_text()
    generation = open_current(target)
    assert generation.id == result['annotations']['generation']
