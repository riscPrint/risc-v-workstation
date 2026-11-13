"""Group failed native observations by their last recorded C2 trap cause."""
import hashlib
from pathlib import Path
from rvw.cosim.trace import Trace
from rvw.results import load_run


def observed_trap(directory, test, core, config, source):
    directory = Path(directory)
    run = load_run(directory)
    if run.why_inconclusive:
        raise ValueError('trap C1 is inconclusive')
    if (run.core, run.config, run.seed, run.status, run.elf_sha256) != (
            core, config, test.seed, test.status, test.extra.get('elf_sha256')):
        raise ValueError('trap C1 does not match its C3 entry')
    expected_source = dict(source)
    if expected_source.get('identity_complete') is False:
        expected_source.pop('identity_complete')
        expected_source.pop('identity_incomplete_reasons', None)
    if run.source != expected_source:
        raise ValueError('trap C1 source does not match C3')
    path = run.artifact('rvfi_trace')
    if path is None:
        raise ValueError('trap observation has no C1 trace')
    trace = Trace(path)
    try:
        header = trace.header
        claims = dict(core=core, config=config, seed=run.seed, elf_sha256=run.elf_sha256,
                      rtl_sha256=run.get('rtl_sha256'), source=run.source)
        if any(header.get(k) != v for k, v in claims.items()):
            raise ValueError('trap C2 header does not match C1')
        last, count, end = None, 0, None
        for record in trace:
            if record.get('event') == 'trap':
                last, count = record, count + 1
            if record.get('event') == 'end':
                end = record
        if end is None or end.get('status') != run.status:
            raise ValueError('trap C2 end does not match C1')
        if count != run.details.get('traps') or not last:
            raise ValueError('trap C2 count does not match C1')
        return dict(cause=hex(last['cause']), interrupt=last['intr'], tval=hex(last['tval']),
                    cycle=last['cycle'], traps=count, selection='last-recorded-trap',
                    trace_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                    c1_sha256=hashlib.sha256((directory/'result.json' if directory.is_dir() else directory).read_bytes()).hexdigest(),
                    root_cause='not_established')
    finally:
        trace.close()
