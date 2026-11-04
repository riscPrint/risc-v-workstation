"""Keep the published command inventory complete as packages add entry points."""
import runpy
from pathlib import Path


def test_command_reference_matches_declarations(monkeypatch):
    monkeypatch.delenv('RVW_MCP_PLUGINS', raising=False)
    root = Path(__file__).resolve().parents[2]
    generator = runpy.run_path(str(root / 'scripts/command-reference.py'))
    target = generator['TARGET']
    assert target.exists(), 'Missing CLI and MCP reference'
    assert target.read_text() == generator['render']()


def test_command_reference_does_not_depend_on_terminal_width(monkeypatch):
    monkeypatch.setenv('COLUMNS', '120')
    root = Path(__file__).resolve().parents[2]
    generator = runpy.run_path(str(root / 'scripts/command-reference.py'))
    assert generator['TARGET'].read_text() == generator['render']()
