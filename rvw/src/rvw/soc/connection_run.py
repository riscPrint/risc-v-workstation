"""Run the existing formal connectivity consumer with a bounded wall time."""
import json
import sys
from pathlib import Path

from rvw.common.proc import run_group


def run(database, manifest, out, *, timeout=120, engine='smtbmc:yices', depth=10):
    out = Path(out).resolve()
    log = out.with_suffix('.log')
    command = [sys.executable, '-m', 'rvw', 'formal', 'connectivity', str(manifest),
               '--db', str(database), '--out', str(out), '--run', '--proof-mode', 'prove',
               '--engine', engine, '--depth', str(depth), '--timeout', str(min(timeout, 30)), '--json']
    with log.open('w') as stream:
        process = run_group(command, stdout=stream, stderr=stream, timeout=timeout)
    path = out/'result.json'
    report = json.loads(path.read_text()) if path.is_file() else {}
    rows = report.get('connections', [])
    # The formal command deliberately returns 1 even for resolved contracts.
    # Require each transfer and its nonvacuity witness, not that exit code.
    def proven(row):
        campaign = row.get('campaign', {})
        observations = campaign.get('observations', {})
        transfer = observations.get('transfer', {})
        activation = observations.get('activation', {})
        return (row.get('status') == 'proven' and campaign.get('proof_kind') == 'unbounded'
                and transfer.get('status') == 'pass' and transfer.get('returncode') == 0
                and transfer.get('proof_kind') == 'unbounded'
                and activation.get('status') == 'fail' and activation.get('returncode') == 1)
    status = 'inconclusive'
    if not process.timed_out and process.returncode in (0, 1) and rows:
        if any(row.get('status') == 'contradicted' for row in rows):
            status = 'fail'
        elif all(proven(row) for row in rows):
            status = 'proven'
    return dict(status=status, generated=True, ran=True, timed_out=process.timed_out,
                returncode=process.returncode, checks=len(rows), details=report,
                scope='Declared RTL value transfers with activation witnesses; reverse influence gaps remain in details.')
