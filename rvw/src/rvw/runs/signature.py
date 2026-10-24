"""Failure signatures for the debug tools. The signature itself is the shared one from
`rvw.results` (contract C3: `fail:3`, `timeout`, `assert:lsu.scala:1241`, ...), with "pass" for
passing runs. Two runs "fail the same way" when their signatures are equal; a user can also give
a regex (`re:<regex>`) to match a family of signatures. A wall-clock timeout (`timeout:wall-clock`,
C3) says nothing about the core (machine load, a hung process), so it never matches anything, not
even through a regex. `assertion_location` finds any HDL/Scala
source location in a message (used for the SpinalTrace criterion).
"""
from __future__ import annotations

import re

from ..results.signature import WALL_CLOCK  # "timeout:wall-clock"

LOC_RX = re.compile(r"([A-Za-z0-9_\-]+\.(?:scala|sv|svh|v|vhd|vhdl|py|java|cpp|cc|c|h)):L?(\d+)")


def assertion_location(msg: str | None) -> tuple[str, int] | None:
    if not msg:
        return None
    m = LOC_RX.search(msg)
    return (m.group(1), int(m.group(2))) if m else None


def signature(result: dict) -> str:
    """The shared C3 signature (`rvw.results.run_signature`), with "pass" for passing runs."""
    from ..results import run_signature
    return run_signature(result) or "pass"


def inconclusive(sig: str | None) -> bool:
    """True for a signature that cannot show (or rule out) a failure: the wall clock ran out."""
    return sig == WALL_CLOCK


def signature_matches(sig: str, want: str) -> bool:
    """Does signature `sig` match `want` (exact, or `re:<regex>`)? Never for a wall-clock timeout,
    and never for a pass: a passing run reproduces no failure, whatever the pattern (review 10)."""
    if inconclusive(sig) or sig == "pass":
        return False
    if want.startswith("re:"):
        return re.search(want[3:], sig) is not None
    return sig == want
