#!/usr/bin/env python3
"""Summarize actual C1/C2 files without inferring ordering correctness."""
import argparse
import hashlib
import json
from pathlib import Path
from rvw.cosim.trace import Trace
from rvw.results import load_run


def summarize(directory):
    root = Path(directory)
    loaded = load_run(root/'result.json')
    c1 = json.loads((root/'result.json').read_text())
    report = dict(run=root.name, status=loaded.status,
                  c1_inconclusive=loaded.why_inconclusive, seed=c1.get('seed'),
                  cycles=c1.get('cycles'), instret=c1.get('instret'),
                  core_rev=c1.get('source', {}).get('core_rev_full'),
                  tools_rev=c1.get('source', {}).get('tools_rev'),
                  tools_dirty=c1.get('source', {}).get('tools_dirty'),
                  rtl_sha256=c1.get('rtl_sha256'), ordering='not_checked')
    path = root/'rvfi.jsonl'
    reader = Trace(path)
    try:
        if not reader.multihart:
            raise ValueError('multi-hart trace required')
        counts = {str(h): 0 for h in reader.header['harts']}
        done = {}
        for record in reader:
            if record.get('event') == 'hart_end':
                done[str(record['hart'])] = record['status']
            elif 'event' not in record:
                counts[str(record['hart'])] += 1
        report.update(per_hart_retirements=counts, hart_status=done,
                      trace_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        if sum(counts.values()) != c1.get('instret') or set(counts) != set(done):
            raise ValueError('C1/C2 counts or completion sets disagree')
        if loaded.status == 'pass' and (loaded.why_inconclusive or
                                       any(s != 'pass' for s in done.values())):
            report['status'] = 'inconclusive'
        return report
    finally:
        reader.close()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('runs', nargs='+')
    a = p.parse_args()
    print(json.dumps([summarize(path) for path in a.runs], indent=2))
