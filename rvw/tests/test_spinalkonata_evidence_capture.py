"""Standalone evidence commands must pin their inputs before analysis."""
import importlib
import json
from pathlib import Path

import pytest

from race_injection import race_injector

RAW = b'Kanata\t0004\nC=\t0\nI\t0\t0\t0\nC\t1\nR\t0\t0\t0\n'
OTHER = RAW.replace(b'C\t1', b'C\t9')


@pytest.fixture
def evidence(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'SpinalKonata/scripts'))
    return importlib.import_module('captured')


@pytest.mark.parametrize('replace,revert', [(True, False), (False, True)])
def test_roi_uses_captured_elf_and_report(tmp_path, evidence, monkeypatch, race_injector, replace, revert):
    import hashlib
    roi = importlib.import_module('roi_observations')
    trace, elf, assembly, tool = make_run(tmp_path, monkeypatch)
    hook = race_injector.file(roi, 'read', elf, b'not the captured assembly', when='before',
                              replace=replace, revert=revert)
    report = roi.observe(tmp_path)
    assert hook.fired
    assert report['marker_pc'] == '0x1000'
    assert any(f['sha256'] == hashlib.sha256(assembly).hexdigest() for f in report['capture']['files'])


def make_run(tmp_path, monkeypatch):
    import hashlib
    trace = tmp_path / 'konata.log'
    trace.write_text('Kanata\t0004\nC=\t0\nI\t0\t0\t0\nL\t0\t0\t1000: csrr a0,mcycle\n'
                     'C\t1\nR\t0\t0\t0\nI\t1\t1\t0\nL\t1\t0\t1000: csrr a0,mcycle\n'
                     'C\t2\nR\t1\t0\t0\n')
    elf = tmp_path / 'program.elf'
    assembly = b'00001000 <setStats>:\n 1000: 00000013 csrr a0,mcycle\n'
    elf.write_bytes(assembly)
    (tmp_path / 'result.json').write_text(json.dumps(dict(schema='rvw.run/1', status='pass',
        elf=str(elf), elf_sha256=hashlib.sha256(assembly).hexdigest(), cycles=4, instret=2,
        artifacts={'konata': trace.name}, source={})))
    (tmp_path / 'report.json').write_text(json.dumps(dict(trace_sha256=hashlib.sha256(trace.read_bytes()).hexdigest())))
    tool = tmp_path / 'objdump'
    tool.write_text('#!/bin/sh\nif [ "$1" = "--version" ]; then echo fixture; else /bin/cat "$2"; fi\n')
    tool.chmod(0o755)
    monkeypatch.setenv('RISCV_OBJDUMP', str(tool))
    return trace, elf, assembly, tool


def test_collect_publishes_captured_generation(tmp_path, evidence, monkeypatch, race_injector):
    import hashlib
    from rvw.results.generation import open_current
    from rvw.perf import analysis
    collector = importlib.import_module('collect')
    run = tmp_path / 'one'
    run.mkdir()
    trace, elf, assembly, tool = make_run(run, monkeypatch)
    counters = run / 'result.json'
    original = counters.read_bytes()
    raw = trace.read_bytes()
    # Publish only the captured inputs, even if a live trace changes during parsing.
    hook = race_injector.file(analysis, 'read', trace, OTHER, when='before', replace=True)
    collector.collect(tmp_path)
    assert hook.fired
    assert counters.read_bytes() == original
    generation = open_current(tmp_path / '.analysis')
    report = json.loads(generation.read_bytes('one/report.json'))
    assert report['trace_sha256'] == hashlib.sha256(raw).hexdigest()
    assert generation.read_bytes('one/report.txt')
    assert json.loads(generation.read_bytes('one/roi-observations.json'))['marker_pc'] == '0x1000'


@pytest.mark.parametrize('replace,revert', [(True, False), (False, True)])
def test_roi_full_report_is_read_from_capture(tmp_path, evidence, monkeypatch, race_injector, replace, revert):
    import hashlib
    roi = importlib.import_module('roi_observations')
    trace, elf, assembly, tool = make_run(tmp_path, monkeypatch)
    full = tmp_path / 'report.json'
    cross_check = {'result_sha256': hashlib.sha256((tmp_path / 'result.json').read_bytes()).hexdigest(),
                   'exact_counter_match': True}
    report = {'trace_sha256': hashlib.sha256(trace.read_bytes()).hexdigest(), 'cross_check': cross_check}
    full.write_text(json.dumps(report))
    changed = json.dumps({**report, 'cross_check': {'exact_counter_match': False}}).encode()
    hook = race_injector.file(Path, 'read_text', full, changed, when='before', occurrence=2,
                              replace=replace, revert=revert)
    result = roi.observe(tmp_path)
    assert hook.fired
    assert result['full_run_counter_check'] == cross_check


def test_collect_tool_change_preserves_previous_generation(tmp_path, evidence, monkeypatch, race_injector):
    from rvw.results.generation import GenerationError, open_current
    collector = importlib.import_module('collect')
    roi = importlib.import_module('roi_observations')
    run = tmp_path / 'one'
    run.mkdir()
    trace, elf, assembly, tool = make_run(run, monkeypatch)
    collector.collect(tmp_path)
    previous = open_current(tmp_path / '.analysis')
    # Change and restore the executable while the captured invocation runs.
    changed = tool.read_bytes() + b'# changed during execution\n'
    hook = race_injector.file(roi, 'run_group', tool, changed, when='before', revert=True)
    with pytest.raises(GenerationError, match='input_not_captured:tool'):
        collector.collect(tmp_path)
    assert hook.fired
    assert open_current(tmp_path / '.analysis').id == previous.id
    previous.verify()


def test_missing_c1_artifact_does_not_fall_back_to_another_path(tmp_path, evidence, monkeypatch, race_injector):
    import gzip
    from rvw.common.capture import CaptureError
    roi = importlib.import_module('roi_observations')
    captured = importlib.import_module('captured')
    trace, elf, assembly, tool = make_run(tmp_path, monkeypatch)
    trace.with_suffix('.log.gz').write_bytes(gzip.compress(trace.read_bytes()))
    hook = race_injector.at(captured, 'load_run', trace.unlink, when='after')
    with pytest.raises(CaptureError, match='input_not_captured'):
        roi.observe(tmp_path)
    assert hook.fired


@pytest.mark.parametrize('replace,revert', [(True, False), (False, True)])
def test_trace_measurements_keep_inconclusive_c1_and_captured_bytes(
        tmp_path, evidence, monkeypatch, race_injector, replace, revert):
    import hashlib
    reporter = importlib.import_module('trace_report')
    trace, elf, assembly, tool = make_run(tmp_path, monkeypatch)
    (tmp_path / 'report.json').unlink()
    counters = tmp_path / 'result.json'
    result = json.loads(counters.read_text())
    cause = 'input_not_captured:compiled_model: fixture build is not captured'
    result.update(status='error', observed_status='pass', inconclusive=cause, cache_key=None)
    counters.write_text(json.dumps(result))
    original, raw = counters.read_bytes(), trace.read_bytes()
    hook = race_injector.file(reporter, 'analyze', trace, OTHER, when='before',
                              replace=replace, revert=revert)
    report = reporter.write_report(tmp_path)
    assert hook.fired
    assert report['measurement_scope'] == 'trace_only'
    assert report['summary']['instret'] == 2
    assert report['trace_sha256'] == hashlib.sha256(raw).hexdigest()
    assert report['producer_result'] == dict(sha256=hashlib.sha256(original).hexdigest(),
                                             status='error', inconclusive=cause)
    assert 'cross_check' not in report
    assert report['cache_key'] is None
    assert counters.read_bytes() == original
    assert (tmp_path / 'report.txt').read_text().startswith('Trace-only measurement.')
    from rvw.perf.cli import execute_json
    assert execute_json([str(tmp_path / 'report.json')])['summary'] == report['summary']
    with pytest.raises(ValueError, match='inconclusive counter evidence'):
        execute_json([str(trace)])


def test_trace_measurements_capture_c1_before_parsing(tmp_path, evidence, monkeypatch, race_injector):
    reporter = importlib.import_module('trace_report')
    trace, elf, assembly, tool = make_run(tmp_path, monkeypatch)
    (tmp_path / 'report.json').unlink()
    counters = tmp_path / 'result.json'
    captured_c1 = json.loads(counters.read_text())
    captured_c1.update(status='error', inconclusive='input_not_captured:compiled_model')
    counters.write_text(json.dumps(captured_c1))
    original = counters.read_bytes()
    changed = json.loads(original)
    changed.update(status='pass', instret=999)
    hook = race_injector.file(reporter, 'load_run', counters, json.dumps(changed).encode(),
                              when='before', revert=True)
    report = reporter.write_report(tmp_path)
    assert hook.fired
    assert report['producer_result']['status'] == 'error'
    assert report['producer_result']['inconclusive'] == 'input_not_captured:compiled_model'
    assert report['summary']['instret'] == 2
    assert 'cross_check' not in report
    assert report['cache_key'] is None
