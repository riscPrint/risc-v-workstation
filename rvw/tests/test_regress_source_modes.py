"""Executable input modes must affect source identity."""
import pytest

from rvw.regress.source import content_hash

pytestmark = pytest.mark.fast


@pytest.mark.parametrize('directory', [False, True])
def test_executable_mode_changes_content_identity(tmp_path, directory):
    script = tmp_path / 'adapter.sh'
    script.write_text('#!/bin/sh\nexit 0\n')
    script.chmod(0o644)
    target = tmp_path if directory else script
    before = content_hash(target)
    script.chmod(0o755)
    assert content_hash(target) != before
