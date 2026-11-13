#!/usr/bin/env python3
"""Report observed FP cross bins from validated C2 captures."""
import argparse
import json
from pathlib import Path
from rvw.cov.fp import report

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--width', type=int, choices=[32, 64], required=True)
p.add_argument('--out', type=Path, required=True)
p.add_argument('traces', type=Path, nargs='+')
args = p.parse_args()
# Each run has a separate architectural register state.
reports = []
for trace in args.traces:
    with trace.open() as stream:
        header = json.loads(next(stream))
        if header['schema'] != 'rvw.rvfi/2' or 'state' not in header.get('capabilities', []):
            raise ValueError('FP coverage requires a C2/2 state trace')
        reports.append(report((json.loads(line) for line in stream), args.width))
args.out.write_text(json.dumps(reports, indent=2) + '\n')
