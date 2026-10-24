"""C1 run directories and adapter re-runs for the debug tools.

`open_run` uses canonical C1 validation (`rvw.results`) and keeps the run's directory for
artifacts. `adapter` re-runs a run through its core adapter with changed options (seed, max cycles,
wave window, ...), each attempt in a fresh directory. Used by `rvw bundle`, `rvw reduce` and
`rvw bisect`. Nothing here is core-specific: the adapter command comes from the run's `replay` field.
"""
from .result import Run, open_run, tools_root  # noqa: F401
from .signature import WALL_CLOCK, inconclusive, signature, signature_matches  # noqa: F401
