"""Platform command requirements are selected before input capture."""
import sys

import pytest

from rvw.regress.config import load_config
from rvw.regress.plan import suites_plan
from rvw.regress.runner import Runner, RunOptions
from rvw.regress.source import describe


@pytest.mark.parametrize('platform,required', [('linux', False), ('darwin', True)])
def test_boom_requires_apple_commands_only_on_macos(monkeypatch, platform, required):
    monkeypatch.setattr(sys, 'platform', platform)
    core = load_config('boom')
    assert ('xcrun' in core.input_commands) is required
    assert ('xcode-select' in core.input_commands) is required
    assert 'make' in core.input_tools and 'ar' in core.input_commands


@pytest.mark.parametrize('platform,ok', [('linux', True), ('darwin', False)])
def test_selected_platform_commands_remain_required(fake, tmp_path, monkeypatch, platform, ok):
    fake.config.write_text(fake.config.read_text().replace(
        'input_complete = true', 'input_complete = true\ninput_commands_by_platform = '
        '{darwin = ["rvw-test-missing-apple-command"]}'))
    with monkeypatch.context() as patch:
        patch.setattr(sys, 'platform', platform)
        core = load_config(str(fake.config))
    runner = Runner(core, describe(fake.repo), tmp_path / 'output', RunOptions(index=False, log=None))
    summary = runner.run(suites_plan(core, ['isa'], None))
    assert summary['ok'] is ok
    if not ok:
        assert 'input_not_captured:command' in runner.input_change
        assert summary['inconclusive'] == 3 and not fake.calls('run')
