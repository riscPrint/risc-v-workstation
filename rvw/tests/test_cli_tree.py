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
