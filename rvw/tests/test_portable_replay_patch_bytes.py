"""Portable replay must retain non-UTF-8 bytes in tracked source patches."""
import pytest

from rvw.runs.portable import pack, replay
from test_portable_replay import failing

pytestmark = pytest.mark.fast


def test_tracked_patch_keeps_source_encoding(failing, tmp_path):
    run, recipe, tools, _ = failing
    adapter = tools / 'adapter.py'
    expected = b'# coding: latin-1\n# caf\xe9\n' + adapter.read_bytes()
    adapter.write_bytes(expected)
    archive = tmp_path / 'encoded.rvw'
    pack(run, recipe, archive)
    out = tmp_path / 'replayed'
    assert replay(archive, out)['status'] == 'reproduced'
    assert (out / 'tools/adapter.py').read_bytes() == expected
