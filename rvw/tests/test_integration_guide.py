"""Validate guide command syntax without executing core or tool operations."""
from pathlib import Path
import shlex
import pytest
from rvw.cli import build_parser

pytestmark=pytest.mark.fast
GUIDE=Path(__file__).resolve().parents[2]/'docs/INTEGRATION_GUIDE.md'


def test_guide_rvw_commands_parse_without_execution():
    parser=build_parser()
    commands=[line for line in GUIDE.read_text().splitlines() if line.startswith('rvw ')]
    assert len(commands)>=20
    for command in commands:
        argv=shlex.split(command)[1:]
        if '--help' in argv:
            continue
        parser.parse_args(argv)


def test_guide_retains_evidence_boundaries():
    text=GUIDE.read_text()
    for term in ('Spike only','Fixture only','Ran on RTL','untested','inconclusive'):
        assert term in text
    assert 'pull/690' in text and 'pull/689' in text
