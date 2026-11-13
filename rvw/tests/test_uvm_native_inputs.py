"""Explicit DPI dependencies must change the identity and reject stale builds."""
from pathlib import Path
import pytest
from rvw.uvm.native_inputs import capture, verify

pytestmark = pytest.mark.fast


def test_files_and_directory_bytes_are_bound(tmp_path):
    lib = tmp_path/'shim.so'; lib.write_bytes(b'shim')
    headers = tmp_path/'headers'; headers.mkdir()
    header = headers/'effect.h'; header.write_text('header')
    hashes = capture([lib, headers])
    assert set(hashes) == {str(lib), str(header)}
    verify(hashes)
    lib.write_bytes(b'changed')
    with pytest.raises(ValueError, match='native dependency changed'):
        verify(hashes)
    assert hashes != capture([lib, headers])


def test_missing_or_empty_dependency_cannot_pass(tmp_path):
    with pytest.raises(FileNotFoundError):
        capture([tmp_path/'absent'])
    with pytest.raises(ValueError, match='empty native dependency'):
        capture([tmp_path])
    file = tmp_path/'image'; file.write_bytes(b'1')
    hashes = capture([file]); file.unlink()
    with pytest.raises(ValueError, match='native dependency changed'):
        verify(hashes)
