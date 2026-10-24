"""Input selection for the standalone evidence commands. All consumers use copies."""
from dataclasses import dataclass
import json
from pathlib import Path

from rvw.common.capture import Capture, Captured, CaptureError
from rvw.perf.inputs import Inputs, present
from rvw.results import load_run


def trace_file(capture, path):
    path = Path(path)
    return capture.file(path if present(path) else Path(str(path) + '.gz'))


@dataclass(frozen=True)
class RunInputs:
    result: Captured
    trace: Captured
    elf: Captured
    report: Captured | None = None

    def perf(self):
        return Inputs(self.trace, self.result, True)


def capture_run(capture: Capture, run, *, report=True):
    run = Path(run)
    result = capture.file(run / 'result.json')
    counters = load_run(result.copy)
    if why := counters.why_inconclusive:
        raise ValueError(f'{result.resolved}: inconclusive counter evidence: {why}')
    trace = capture.file(Path(result.source).parent / counters.artifacts['konata'])
    elf = capture.file(Path(counters.elf))
    if counters.elf_sha256 != elf.sha256:
        raise CaptureError('input_not_captured:elf', 'ELF copy does not match the C1 ELF hash')
    full = capture.file(run / 'report.json') if report else None
    if full is not None:
        saved = json.loads(full.copy.read_text())
        if saved.get('trace_sha256') != trace.sha256:
            raise CaptureError('input_not_captured:report', 'saved report does not identify the captured trace')
        counter_hash = saved.get('cross_check', {}).get('result_sha256')
        if saved.get('cross_check') is not None and counter_hash != result.sha256:
            raise CaptureError('input_not_captured:report', 'saved counter check does not identify the captured C1')
    return RunInputs(result, trace, elf, full)
