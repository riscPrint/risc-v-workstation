"""Adapters execute with their captured sibling modules and support files."""
from pathlib import Path

import pytest

from rvw.common.capture import Capture, CaptureError
from rvw.common.proc import run_group
from rvw.runs.adapter import Command
from rvw.runs.inputs import DebugInputs


@pytest.mark.parametrize('in_core', [False, True])
@pytest.mark.parametrize('language', ['python', 'shell'])
def test_adapter_keeps_siblings(tmp_path, monkeypatch, in_core, language):
    monkeypatch.setattr('rvw.runs.inputs.new_capture', lambda: Capture(tmp_path / 'capture'))
    root = tmp_path / 'core'
    directory = root / 'adapter'
    directory.mkdir(parents=True)
    if language == 'python':
        helper = directory / 'support.py'
        helper.write_text('VALUE = "captured sibling"\n')
        script = directory / 'adapter.py'
        script.write_text('#!/usr/bin/env python3\nimport support\nprint(support.VALUE)\n')
    else:
        helper = directory / 'support.sh'
        helper.write_text('printf "captured sibling\\n"\n')
        script = directory / 'adapter.sh'
        script.write_text('#!/bin/bash\nsource "$(dirname "$0")/support.sh"\n')
    script.chmod(0o755)
    inputs = DebugInputs()
    if in_core:
        inputs.source = inputs.build_tree(root, git=False)
    command = inputs.bind_adapter(Command(exe=[str(script)]))
    saved = Path(command.exe[-1])
    if in_core:
        assert saved == inputs.source.copy / 'adapter' / script.name
        assert len(inputs.record()['trees']) == 1
    assert (saved.parent / helper.name).read_text() == helper.read_text()
    # The adapter uses its private sibling even if the original is no longer available.
    helper.unlink()
    result = run_group(command.argv(), env=command.child_environment(), capture=True, timeout=10)
    assert result.returncode == 0, result.stderr
    assert result.stdout == 'captured sibling\n'
    inputs.verify()
    saved_helper = saved.parent / helper.name
    saved_helper.chmod(0o644)
    saved_helper.write_text('changed')
    with pytest.raises(CaptureError, match='captured source changed'):
        inputs.verify()
