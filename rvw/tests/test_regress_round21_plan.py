"""Stored evidence must cover the plan requested from the gate."""
from pathlib import Path

import pytest

from rvw.regress.cli import execute_json
from rvw.regress.plan import gate as run_gate, suites_plan, tier_plan
from rvw.regress.runner import Runner, RunOptions
from rvw.regress.source import describe
from test_regress_commit_gate import _mcp


def stored(fake, tmp_path, **options):
    output = tmp_path / 'stored'
    result = execute_json('run', core=str(fake.config), tier='quick', out=str(output),
                          no_cache=True, no_index=True, **options)
    assert result['ok']
    return output


def gate(fake, rvw, output, transport, **options):
    arguments = dict(core=str(fake.config), base=str(output), cand=str(output), **options)
    if transport == 'mcp':
        return _mcp('gate', **arguments)
    args = []
    for key, value in arguments.items():
        args.append('--' + key.replace('_', '-'))
        if value is not True:
            args.append(str(value))
    code, text, result = rvw('regress', 'gate', *args, '--json')
    assert result is not None, text
    assert code == {'accept': 0, 'reject': 1, 'inconclusive': 3}[result['verdict']]
    return result


@pytest.mark.parametrize('transport', ['cli', 'mcp'])
def test_quick_evidence_cannot_accept_full_plan(fake, rvw, tmp_path, transport):
    output = stored(fake, tmp_path)
    verdict = gate(fake, rvw, output, transport, tier='full', allow_missing=True)
    assert verdict['verdict'] == 'inconclusive'
    assert verdict['inconclusive_cause'] == 'stored_plan_incomplete'
    missing = verdict['stored_plan_problems']
    assert any(p['id'] == 'rv64ui-v-add' and p['why'] == 'missing test or seed' for p in missing)
    assert any(p['suite'] == 'elab' for p in missing)
    assert {p['side'] for p in missing} == {'base', 'candidate'}


@pytest.mark.parametrize('change', ['config', 'seeds', 'seed_base', 'options', 'elf', 'build_options'])
def test_equal_stored_inputs_must_match_requested_inputs(fake, rvw, tmp_path, change):
    run_options = {'tier': 'full'} if change == 'build_options' else {}
    if run_options:
        output = tmp_path / 'stored'
        assert execute_json('run', core=str(fake.config), out=str(output), no_cache=True,
                            no_index=True, **run_options)['ok']
    else:
        output = stored(fake, tmp_path)
    options = dict(tier='quick')
    if change == 'config':
        options['config'] = 'large'
    elif change == 'seeds':
        options['seeds'] = 2
    elif change == 'seed_base':
        options['seed_base'] = 9
    elif change == 'options':
        options['max_cycles'] = 2000
    elif change == 'elf':
        fake.prog('rv64ui-p-add', 'cycles=123')
    else:
        fake.config.write_text(fake.config.read_text().replace(
            '[suites.elab]', '[suites.elab]\nbuild_options = ["--wave"]'))
        options['tier'] = 'full'
    verdict = gate(fake, rvw, output, 'cli', **options)
    assert verdict['verdict'] == 'inconclusive'
    assert verdict['stored_plan_problems']


def test_matching_stored_plan_still_accepts(fake, rvw, tmp_path):
    output = stored(fake, tmp_path)
    assert gate(fake, rvw, output, 'cli', tier='quick')['verdict'] == 'accept'


def test_removed_option_does_not_reuse_stored_stimulus(fake, rvw, tmp_path):
    original = fake.config.read_text()
    adapter = tmp_path / 'echo-options.py'
    adapter.write_text(Path(__file__).with_name('fake_adapter.py').read_text().replace(
        'if metrics:', 'res["options"] = {"mode": job["mode"]}\n    if metrics:'))
    original = original.replace(str(Path(__file__).with_name('fake_adapter.py')), str(adapter))
    fake.config.write_text(original.replace('[suites.isa]', '[suites.isa]\noptions = {mode = "slow"}'))
    output = stored(fake, tmp_path)
    fake.config.write_text(original)
    verdict = gate(fake, rvw, output, 'cli', tier='quick')
    assert verdict['verdict'] == 'inconclusive'
    assert any(p['why'] == 'requested options differ or are missing'
               for p in verdict['stored_plan_problems'])


def test_full_evidence_can_cover_quick_plan(fake, rvw, tmp_path):
    output = tmp_path / 'stored'
    assert execute_json('run', core=str(fake.config), tier='full', out=str(output),
                        no_cache=True, no_index=True)['ok']
    assert gate(fake, rvw, output, 'cli', tier='quick')['verdict'] == 'accept'


def test_relative_declared_options_match_stored_paths(fake, tmp_path, monkeypatch):
    from test_regress_round20_options import configured
    core, policy = configured(fake, tmp_path, monkeypatch, spelling='relative')
    policy.write_text('pass')
    output = tmp_path / 'stored'
    opts = RunOptions(index=False, log=None)
    assert Runner(core, describe(fake.repo), output, opts).run(suites_plan(core, ['isa'], None))['ok']
    verdict = run_gate(core, 'quick', None, None, str(output), str(output), None,
                       opts, None, None)['verdict']
    assert verdict.verdict == 'accept', verdict.to_dict()


@pytest.mark.parametrize('channel', ['option', 'nested', 'build'])
def test_changed_declared_stimulus_cannot_reuse_stored_plan(fake, tmp_path, monkeypatch, channel):
    from test_regress_round20_options import configured
    core, policy = configured(fake, tmp_path, monkeypatch, channel=channel)
    policy.write_text('pass')
    if channel == 'build':
        from rvw.regress.config import TierRun
        core.tier('quick').runs = [TierRun('elab', configs=['small'])]
    tier = 'quick'
    output = tmp_path / 'stored'
    opts = RunOptions(index=False, log=None)
    assert Runner(core, describe(fake.repo), output, opts).run(tier_plan(core, tier, None))['ok']
    # This is an ordinary edit between commands, with no concurrent input changes.
    policy.write_text('fail')
    verdict = run_gate(core, tier, None, None, str(output), str(output), None,
                       opts, None, None)['verdict']
    assert verdict.verdict == 'inconclusive', verdict.to_dict()
    assert any(p['why'] == 'requested option input differs or is missing'
               for p in verdict.extra['stored_plan_problems'])


@pytest.mark.parametrize('change', [False, True])
def test_directory_option_requires_current_membership(fake, tmp_path, monkeypatch, change):
    from test_regress_round20_options import configured
    core, policy = configured(fake, tmp_path, monkeypatch)
    policy.unlink()
    policy.mkdir()
    (policy / 'status').write_text('pass')
    adapter = Path(core.adapter[1])
    adapter.write_text(adapter.read_text().replace("Path(job['policy']).read_text()",
                                                 "(Path(job['policy']) / 'status').read_text()"))
    output = tmp_path / 'stored'
    opts = RunOptions(index=False, log=None)
    assert Runner(core, describe(fake.repo), output, opts).run(tier_plan(core, 'quick', None))['ok']
    if change:
        (policy / 'another-input').write_text('new stimulus')
    verdict = run_gate(core, 'quick', None, None, str(output), str(output), None,
                       opts, None, None)['verdict']
    assert verdict.verdict == ('inconclusive' if change else 'accept'), verdict.to_dict()
