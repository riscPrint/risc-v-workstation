"""Whole-tree smoke checks that catch cross-area merge breakage early."""
import argparse

import pytest

pytestmark = pytest.mark.fast


def test_every_cli_parser_formats_help():
    import rvw.cli
    seen, failures = [], []

    def walk(parser):
        seen.append(parser.prog)
        try:
            parser.format_help()
        except Exception as exc:  # report every broken parser, not only the first
            failures.append(f'{parser.prog}: {type(exc).__name__}: {exc}')
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                for child in action.choices.values():
                    walk(child)
    walk(rvw.cli.build_parser())
    assert not failures
    assert len(seen) == len(set(seen)), 'duplicate command paths'


def test_every_mcp_package_loads(monkeypatch):
    monkeypatch.delenv('RVW_MCP_PLUGINS', raising=False)
    from rvw.mcp.registry import Registry
    registry, problems = Registry.discover()
    try:
        assert not problems  # a broken mcp_tools.py silently drops its whole package
    finally:
        registry.jobs.shutdown()


def _tracked(*patterns):
    import subprocess
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    names = subprocess.run(['git', 'ls-files', '-z', *patterns], cwd=root, check=True,
                           capture_output=True).stdout.decode().split('\0')
    return root, [name for name in names if name]


def test_tracked_python_json_and_toml_files_parse():
    # A keep-both rebase can leave a file that no fast test imports; parse all of them.
    import ast
    import json
    import tomllib
    root, names = _tracked('*.py', '*.json', '*.toml')
    failures = []
    for name in names:
        path = root / name
        if not path.is_file() or path.name.startswith('tsconfig'):  # tsconfig is JSON with comments
            continue
        try:
            if name.endswith('.py'):
                ast.parse(path.read_bytes(), filename=name)
            elif name.endswith('.json'):
                json.loads(path.read_bytes())
            else:
                tomllib.loads(path.read_text())
        except (SyntaxError, ValueError, UnicodeDecodeError) as exc:
            failures.append(f'{name}: {type(exc).__name__}: {exc}')
    assert not failures, '\n'.join(failures)
