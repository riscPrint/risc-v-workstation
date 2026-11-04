#!/usr/bin/env python3
"""Build the CLI and MCP reference from the installed rvw declarations."""
import argparse
from functools import partial
import os
import textwrap
from pathlib import Path

from rvw.cli import build_parser
from rvw.mcp.registry import Registry

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'docs/COMMAND_REFERENCE.md'


def usage_text(parser):
    # argparse changes line breaks between supported Python versions.
    return textwrap.fill(' '.join(parser.format_usage().split()), width=78,
                         subsequent_indent='    ', break_long_words=False,
                         break_on_hyphens=False)


def render():
    # Plugin tools belong to the client, not this checkout's reference.
    previous = os.environ.pop('RVW_MCP_PLUGINS', None)
    try:
        registry, problems = Registry.discover()
    finally:
        if previous is not None:
            os.environ['RVW_MCP_PLUGINS'] = previous
    try:
        if problems:
            raise ValueError(problems)
        lines = ['# CLI and MCP reference', '',
                 'Generated from the command parsers and built-in MCP declarations.',
                 'Run `rvw/.venv/bin/python scripts/command-reference.py` to update it.',
                 'Run the same command with `--check` to check it.', '',
                 'Use `rvw COMMAND --help` for argument details and defaults.',
                 'See the tool READMEs for examples, contracts and limits.',
                 'An entry here states availability. It does not qualify a native flow.', '',
                 '## CLI commands', '']

        def visit(parser):
            # argparse otherwise wraps usage at the caller's terminal width.
            parser.formatter_class = partial(parser.formatter_class, width=78)
            lines.extend(['### `' + parser.prog + '`', '', '```text',
                          usage_text(parser), '```', ''])
            for action in parser._actions:
                if isinstance(action, argparse._SubParsersAction):
                    for child in action.choices.values():
                        visit(child)
        visit(build_parser())
        lines.extend(['## MCP tools', '',
                      f'The default server exposes {len(registry.tools)} built-in tools, including the four job tools.',
                      '`--only` filters packages. `RVW_MCP_PLUGINS` can add tools.',
                      '`rvw mcp --list --json` returns full input schemas.',
                      'CLI commands without an MCP entry are CLI-only.',
                      'Isolated calls can return a job after the sync timeout, even when',
                      'they do not start a background job at once.', ''])
        for name, spec in sorted(registry.tools.items()):
            fields = spec.input_schema.get('properties', {})
            required = spec.input_schema.get('required', [])
            arguments = ', '.join('`' + key + '`' + (' (required)' if key in required else '')
                                  for key in fields) or 'none'
            lines.extend(['### `' + name + '`', '', spec.description.strip(), '',
                          'Arguments: ' + arguments + '.', '',
                          'Starts a background job: ' + ('yes' if spec.long else 'no') + '.', ''])
        return '\n'.join(lines)
    finally:
        registry.jobs.shutdown()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    text = render()
    if args.check:
        if not TARGET.exists() or TARGET.read_text() != text:
            parser.exit(1, 'Command reference is out of date.\n')
    else:
        TARGET.write_text(text)
