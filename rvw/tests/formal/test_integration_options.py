"""Shared BMC execution must keep proof and event-model defaults separate."""
from rvw.cli import build_parser


def test_prove_has_single_clock_defaults():
    args = build_parser().parse_args(['formal', 'prove', '--out', '/tmp/unused'])
    assert args.event_model is False
    assert args.async_reset is False
    assert args.event_clock is None
