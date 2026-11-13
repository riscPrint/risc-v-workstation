#!/usr/bin/env python3
"""Validate native reduction trial traces and write a compact evidence record."""
import argparse
import hashlib
import json
from pathlib import Path

from rvw.cosim.trace import Trace
from rvw.results import load_run


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def summarize(path):
    data = json.loads(path.read_text())
    if not data.get('final') or not data.get('reproduced'):
        raise ValueError('need a completed, reproducing reduction report')
    trials = []
    for trial in data['trials']:
        root = Path(trial['dir'])
        run = load_run(root)
        trace = root / run.artifacts['rvfi_trace']
        checked = Trace(trace)
        try:
            records = list(checked)
        finally:
            checked.close()
        if (not run.details.get('c2_schema_validated') or not records
                or records[-1].get('event') != 'end'
                or records[-1].get('status') != run.status):
            raise ValueError('native trial lacks validated, complete C2 evidence')
        if not trial['conclusive'] or trial['status'] != run.status:
            raise ValueError('native trial is inconclusive or disagrees with C1')
        row = {key: trial[key] for key in ('id', 'status', 'cycles', 'wall_s', 'match', 'conclusive')}
        row.update(instret=run.instret, elf_sha256=run.elf_sha256, trace_sha256=sha(trace),
                   c2_schema_validated=True,
                   trap_events=sum(record.get('event') == 'trap' for record in records))
        for key in ('instructions_kept', 'irq_schedule'):
            if key in trial:
                row[key] = trial[key]
        trials.append(row)
    return dict(report_sha256=sha(path), signature=data['signature'], streams=data['streams'],
                wall_s=data['wall_s'], trials=trials, best_trial=data['best']['trial'],
                source={key: value for key, value in {**data['source'], **run.source}.items()
                        if key in ('core_rev', 'core_rev_full', 'core_dirty', 'core_fingerprint',
                                   'core_sha256', 'core_tree_sha256')}, cache_key=data['cache_key'],
                scope='intentional failing software and IRQ fixtures on captured whole-core RTL; no new core defect or global minimum')


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--instructions', type=Path, required=True)
    parser.add_argument('--irq', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    report = dict(schema='rvw.native-reduction-evidence/1',
                  instructions=summarize(args.instructions), irq=summarize(args.irq))
    args.out.write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
