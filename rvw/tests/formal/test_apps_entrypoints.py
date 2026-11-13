"""Owned entry points retain every public tool and command."""
import argparse
from rvw.formal.apps_cli import register
from rvw.formal.apps_mcp import mcp_tools


def test_owned_commands_and_tools():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers()
    register(sub)
    names = {'testplan', 'proof-core', 'apps', 'autocheck', 'bench', 'recheck', 'cex', 'shortest'}
    assert names <= sub.choices.keys()
    tools = mcp_tools()
    assert {'formal_' + n.replace('-', '_') for n in names - {'bench'}} <= {t.name for t in tools}
