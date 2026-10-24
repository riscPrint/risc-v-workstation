"""Bisect replay descriptors retain their revision and captured bytes."""
import json
from pathlib import Path

import pytest

from race_injection import race_injector
from rvw import runs
from rvw.bisect.core import Bisector, Options
from rvw.runs import adapter
from test_debug_tools import CFG, fake_run, make_core


def test_bisect_descriptor_pins_each_revision_and_saved_replay(tmp_path, monkeypatch, race_injector):
    repo, git = make_core(tmp_path)
    config = tmp_path / 'debug.toml'
    config.write_text(CFG)
    monkeypatch.setenv('RVW_CORE_CONFIG', str(config))
    monkeypatch.setenv('RVW_NO_LOCK', '1')
    run = fake_run(tmp_path / 'run', '--seed', '9', env={'FAKE_CORE': str(repo)})
    hook = race_injector.file(adapter, 'execute', repo / 'f', b'live edit', replace=True)
    report = Bisector(str(run), Options(good='HEAD~7', core_repo=str(repo), workdir=tmp_path / 'bisect')).bisect()
    assert hook.fired and report['result']['first_bad']
    paths = set()
    for step in report['steps']:
        command = adapter.parse_replay(step['replay'])
        path = Path(command.env['RVW_CAPTURE_INPUTS'])
        descriptor = json.loads(path.read_text())
        assert descriptor['source']['core_rev_full'] == step['rev']
        assert descriptor['source']['core_repo'] == command.env['FAKE_CORE']
        assert descriptor['source']['core_sha256'] == step['source_sha256']
        paths.add(path)
    assert len(paths) == len({step['rev'] for step in report['steps']})
    final = adapter.parse_replay(report['command'])
    assert json.loads(Path(final.env['RVW_CAPTURE_INPUTS']).read_text())['source']['core_rev_full'] == report['result']['first_bad']
