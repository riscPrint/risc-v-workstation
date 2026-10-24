"""Command-owned C8 inputs. Capture the complete comparison before parsing traces."""
from dataclasses import dataclass
from pathlib import Path

from rvw.common.capture import Capture, Captured
from rvw.results import load_run


@dataclass(frozen=True)
class Inputs:
    trace: Captured
    result: Captured | None = None
    artifact_matches: bool | None = None


def present(path):
    """Absence is optional only during discovery. Broken links and errors must refuse."""
    try:
        Path(path).lstat()
        return True
    except FileNotFoundError:
        return False


def capture_input(capture: Capture, path, *, result=None, saved=False):
    trace = capture.file(Path(path))
    if saved:
        return Inputs(trace)
    result_path = Path(result) if result is not None else Path(path).parent / 'result.json'
    if result is None and not present(result_path):
        return Inputs(trace)
    counters = capture.file(result_path)
    # Read the declaration from the private copy. It selects another input, not live metadata.
    run = load_run(counters.copy)
    artifact = run.artifacts.get('konata')
    if not artifact:
        return Inputs(trace, counters)
    artifact_path = Path(counters.source).parent / artifact
    # Resolve relative to the C1 lookup directory, even if C1 is a symlink.
    matches = False
    if present(artifact_path):
        declared = artifact_path.resolve(strict=True)
        if not declared.is_file():
            raise ValueError(f"{artifact_path}: not a regular file")
        matches = str(declared) == trace.resolved
    return Inputs(trace, counters, matches)
