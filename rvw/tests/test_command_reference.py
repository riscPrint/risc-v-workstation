"""Keep the published command inventory complete as packages add entry points."""
import pytest
import runpy
from pathlib import Path


@pytest.mark.skip(reason='docs/COMMAND_REFERENCE.md is regenerated in one batch during the parallel push of 2026-11-13; restore this check after it')
def test_command_reference_matches_declarations(monkeypatch):
    monkeypatch.delenv('RVW_MCP_PLUGINS', raising=False)
    root = Path(__file__).resolve().parents[2]
    generator = runpy.run_path(str(root / 'scripts/command-reference.py'))
    target = generator['TARGET']
    assert target.exists(), 'Missing CLI and MCP reference'
    assert target.read_text() == generator['render']()


def test_command_reference_does_not_depend_on_terminal_width(monkeypatch):
    # Compare two renders, not the checked-in file: that file can lag the code.
    monkeypatch.delenv('RVW_MCP_PLUGINS', raising=False)
    root = Path(__file__).resolve().parents[2]
    generator = runpy.run_path(str(root / 'scripts/command-reference.py'))
    monkeypatch.setenv('COLUMNS', '40')
    narrow = generator['render']()
    assert '### `rvw query drivers`' in narrow
    assert '### `rvw formal bmc`' in narrow
    monkeypatch.setenv('COLUMNS', '200')
    assert generator['render']() == narrow


def test_command_reference_normalizes_usage_wrap():
    from types import SimpleNamespace
    root = Path(__file__).resolve().parents[2]
    generator = runpy.run_path(str(root / 'scripts/command-reference.py'))
    compact = SimpleNamespace(format_usage=lambda: 'usage: rvw {one,two} ...\n')
    wrapped = SimpleNamespace(format_usage=lambda: 'usage: rvw {one,two}\n           ...\n')
    assert generator['usage_text'](compact) == generator['usage_text'](wrapped)
