"""Adapter identity documents (rvw.adapter-capture/2): one per model, claims bound to every C1."""
import json
import sys
from dataclasses import replace
import os
from pathlib import Path

import pytest

from rvw.regress.config import load_config
from rvw.regress.plan import suites_plan
from rvw.regress.runner import Runner, RunOptions
from rvw.regress.source import describe
from rvw.results import find_results, load_run

RTL = "ab" * 32
NATIVE = "12" * 32


def prepared(fake, tmp_path, *, corrupt=None, c1_rtl=RTL, c1_native=NATIVE, c1_tools_dirty=None, suites=("isa",),
             out="out", commit=True, model_file=None):
    """The fake adapter with a /2 `identity`. `corrupt` edits `document` before it is printed."""
    if commit:
        fake.commit({})
    core = load_config(str(fake.config))
    core.identity = True
    core.identity_capture = True
    adapter = tmp_path / 'adapter.py'
    text = Path(core.adapter[1]).read_text()
    def value(key, default):
        if model_file is None:
            return repr(default)
        return f'json.loads(Path({str(model_file)!r}).read_text())[{key!r}]'
    rtl = value('rtl_sha256', RTL)
    native = value('native_sha256', NATIVE)
    text = text.replace('def main():', '''def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'identity':
        config = sys.argv[sys.argv.index('--config') + 1]
        options = json.loads(sys.argv[sys.argv.index('--options') + 1])
        log('identity', config, json.dumps(options, sort_keys=True), os.environ['PATH'])
        document = {'schema': 'rvw.adapter-capture/2', 'complete': True,
                    'source': json.loads(os.environ['RVW_CAPTURE_SOURCE']),
                    'rtl_sha256': RTL, 'model': {'config': config},
                    'result_claims': {'rtl_sha256': RTL, 'tools.fake': '1',
                                      'tools.native_build.sha256': NATIVE}}
        CORRUPTION
        print(json.dumps(document))
        return 0
'''.replace('CORRUPTION', corrupt or 'pass').replace('RTL', rtl).replace('NATIVE', native))
    extra = '"rtl_sha256": ' + (rtl if model_file is not None else repr(c1_rtl)) + ',' if c1_rtl is not None else ''
    text = text.replace('"source": source_info(),', extra + (
        '"source": {**source_info(), "tools_dirty": ' + repr(c1_tools_dirty) + '},'
        if c1_tools_dirty is not None else '"source": source_info(),'))
    text = text.replace('"tools": {"fake": "1"}',
                        '"tools": {"fake": "1", "native_build": {"sha256": ' +
                        (native if model_file is not None else repr(c1_native)) + '}}')
    text = text.replace('if metrics:', "res['options'] = {key: value for key, value in job.items() "
                        "if key in ('wave', 'coverage', 'konata', 'rvfi_trace', 'rvfi_check')}\n    if metrics:")
    adapter.write_text(text)
    core.adapter[1] = str(adapter)
    runner = Runner(core, describe(fake.repo), tmp_path / out,
                    RunOptions(log=sys.stderr, index=False, results_root=tmp_path / 'results'))
    return runner, suites_plan(core, list(suites), None)


def test_identity_is_per_model_and_results_carry_the_rtl_hash(fake, tmp_path):
    runner, plan = prepared(fake, tmp_path, suites=("isa", "bench"))
    summary = runner.run(plan)
    assert summary['ok'] and summary['inconclusive'] == 0
    assert not runner.inputs.directory.exists()
    calls = fake.calls('identity')
    # One call per (config, model options); run options such as max_cycles are not model options.
    assert sorted(c.split()[1] for c in calls) == ['large', 'small']
    assert all(c.split()[2] == '{}' for c in calls)
    # The adapter runs on the real PATH, not a private tool directory.
    assert all(c.endswith(' ' + os.environ['PATH']) for c in calls)
    assert all(c.endswith(' src ' + str(fake.repo)) for c in fake.calls('build'))
    for suite in find_results(runner.out):
        manifest = suite.path / 'manifest.jsonl'
        for job in map(json.loads, manifest.read_text().splitlines()):
            assert Path(job['elf']).is_relative_to(runner.inputs.directory)
        for test in suite.tests:
            assert test.extra['rtl_sha256'] == RTL
            assert test.extra['adapter_identity'] in {i['sha256'] for i in runner.identities.values()}
            run = load_run(suite.path / test.run)
            assert run.extra['rtl_sha256'] == RTL
            assert not run.elf.startswith(str(runner.inputs.directory))


@pytest.mark.parametrize('corrupt', [
    "document = []",
    "document = None",
    "document['schema'] = 'rvw.adapter-capture/1'",
    "document['result_claims'] = {'core|config': 'fake'}",
    "document['result_claims'] = {}",
    "document['complete'] = False",
    "document['source']['core_rev_full'] = '0' * 40",
    "document['source'] = {}",
])
def test_bad_identity_never_runs_or_caches(fake, tmp_path, corrupt):
    runner, plan = prepared(fake, tmp_path, corrupt=corrupt)
    summary = runner.run(plan)
    assert summary['inconclusive'] == 3
    assert not fake.calls('run')
    assert not list(runner.cache.dir.rglob('result.json'))


@pytest.mark.parametrize('c1_rtl', ['cd' * 32, None])
def test_c1_must_carry_the_claimed_rtl_hash(fake, tmp_path, c1_rtl):
    runner, plan = prepared(fake, tmp_path, c1_rtl=c1_rtl)
    summary = runner.run(plan)
    assert summary['inconclusive'] == 3
    assert not list(runner.cache.dir.rglob('result.json'))


def test_missing_c1_field_cannot_satisfy_a_null_claim(fake, tmp_path):
    runner, plan = prepared(fake, tmp_path, corrupt="document['result_claims'] = {'not_reported': None}")
    summary = runner.run(plan)
    assert summary['inconclusive'] == 3
    assert not list(runner.cache.dir.rglob('result.json'))


def test_claims_survive_resume_and_cache(fake, tmp_path):
    runner, plan = prepared(fake, tmp_path)
    assert runner.run(plan)['ok']
    calls = len(fake.calls('run'))
    again = Runner(runner.core, describe(fake.repo), runner.out, runner.opts)
    assert again.run(plan)['ok']  # resume
    assert len(fake.calls('run')) == calls
    cached = Runner(runner.core, describe(fake.repo), tmp_path / 'cached', runner.opts)
    assert cached.run(plan)['ok']
    assert len(fake.calls('run')) == calls
    for suite in find_results(cached.out):
        for test in suite.tests:
            assert test.extra.get('cached') and test.extra['rtl_sha256'] == RTL


@pytest.mark.parametrize('field', ['rtl_sha256', 'native_sha256'])
def test_changed_model_identity_cannot_reuse_a_pass(fake, tmp_path, field):
    # The adapter records model inputs in its identity, beyond regress's declared files.
    model_file = tmp_path / 'model.json'
    model = {'rtl_sha256': RTL, 'native_sha256': NATIVE}
    model_file.write_text(json.dumps(model))
    runner, plan = prepared(fake, tmp_path, model_file=model_file)
    assert runner.run(plan)['ok']
    calls = len(fake.calls('run'))
    model[field] = 'ef' * 32
    model_file.write_text(json.dumps(model))
    changed = Runner(runner.core, describe(fake.repo), tmp_path / 'changed', runner.opts)
    assert changed.tools_key == runner.tools_key
    assert changed.run(plan)['ok']
    assert len(fake.calls('run')) == calls + 3
    assert changed.identities != runner.identities


def test_dirty_adapter_sources_disable_the_cache(fake, tmp_path):
    runner, plan = prepared(fake, tmp_path, c1_tools_dirty=True,
                            corrupt="document['result_claims']['source.tools_dirty'] = True")
    summary = runner.run(plan)
    assert summary['ok'] and summary['inconclusive'] == 0
    assert not runner.cacheable
    assert not list(runner.cache.dir.rglob('result.json'))


@pytest.mark.parametrize('c1_native', ['34' * 32, None])
def test_c1_must_carry_the_claimed_native_identity(fake, tmp_path, c1_native):
    runner, plan = prepared(fake, tmp_path, c1_native=c1_native)
    summary = runner.run(plan)
    assert summary['inconclusive'] == 3
    assert not list(runner.cache.dir.rglob('result.json'))


def test_identity_memo_uses_config_and_model_options(fake, tmp_path):
    runner, plan = prepared(fake, tmp_path)
    item = plan[0]
    # A second suite requests the same model with a different cycle budget.
    same_model = replace(item.suite, name='same-model', max_cycles=2000)
    wave_model = replace(item.suite, name='wave-model', options={'wave': True})
    expanded = [item, replace(item, suite=same_model), replace(item, suite=wave_model)]
    assert runner.run(expanded)['ok']
    documents = [identity['document'] for identity in runner.identities.values()]
    assert len(documents) == 2
    calls = fake.calls('identity')
    assert len(calls) == 2
    assert any('"wave": true' in call for call in calls)
    assert all('--max-cycles' not in call and '2000' not in call for call in calls)


def test_build_suite_does_not_request_model_identity(fake, tmp_path):
    runner, plan = prepared(fake, tmp_path, suites=('elab',))
    assert runner.run(plan)['ok']
    assert not fake.calls('identity')
