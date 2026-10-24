"""Trace measurements for BenchTrace's unpublished run directory.

BenchTrace seals and atomically publishes this directory after this command exits.
The C1 verdict is kept as producer metadata. It never supplies counter evidence.
"""
import json
from pathlib import Path
import sys

# The Scala launcher supplies the repository's Python source directory. The
# report has no complete dependency capture or cache claim.
if __name__ == '__main__':
    sys.path.insert(0, sys.argv[2])

from rvw.common.capture import Capture
from rvw.perf.analysis import analyze, render
from rvw.perf.inputs import Inputs
from rvw.results import load_run


def write_report(directory):
    directory = Path(directory)
    capture = Capture(directory / 'report-inputs')
    result = capture.file(directory / 'result.json')
    run = load_run(result.copy)
    trace = capture.file(Path(result.source).parent / run.artifacts['konata'])
    report = analyze(Inputs(trace), isa='riscv', queue_stage='Iq', issue_stage='Is')
    report['measurement_scope'] = 'trace_only'
    report['producer_result'] = {
        'sha256': result.sha256,
        'status': run.status,
        'inconclusive': run.why_inconclusive,
    }
    report['warnings'].append('Trace-only measurement. No C1 counter check or core verdict.')
    capture.verify_tools()
    report['capture'] = capture.record()
    report['cache_key'] = None
    # Refuse an accidental second writer in the unpublished directory.
    with (directory / 'report.json').open('x') as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False) + '\n')
    with (directory / 'report.txt').open('x') as stream:
        stream.write('Trace-only measurement. No C1 counter check or core verdict.\n' + render(report) + '\n')
    return report


if __name__ == '__main__':
    write_report(sys.argv[1])
