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


def run_cut(database, manifest, out, *, timeout=30, engine='smtbmc:yices', depth=6):
    """Prove each structurally resolved connection in a source-cut RTL cone."""
    from types import SimpleNamespace
    from rvw.common.capture import Capture
    from rvw.query.db import DesignDB, QueryError
    from rvw.formal.connectivity import resolve, campaign
    from .connectivity import load
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    capture = Capture(out/'inputs')
    table = capture.file(Path(manifest).resolve())
    db = DesignDB(database, capture=capture)
    rows = []
    try:
        for index, declaration in enumerate(load(table.copy, format_path=manifest)):
            row = resolve(db, declaration)
            rows.append(row)
            if declaration['kind'] != 'required' or row['structural_status'] != 'dependency_found':
                row['reason'] = 'Source-cut proof needs a resolved required dependency.'
                continue
            directory = out/f'connection-{index}'
            directory.mkdir()
            args = SimpleNamespace(timeout=min(timeout, 20), depth=depth, engine=engine,
                                   proof_mode='prove', clock='clk', reset='reset', cone_cut=True)
            try:
                row['campaign'] = campaign(db, declaration, directory, capture, args)
                row['status'] = row['campaign']['status']
            except (ValueError, QueryError) as exc:
                row['reason'] = str(exc)
    finally:
        db.close()
    status = 'fail' if any(r['status']=='contradicted' for r in rows) else (
        'proven' if rows and all(r['status']=='proven' for r in rows) else 'inconclusive')
    report = dict(status=status, generated=True, ran=True, checks=len(rows), connections=rows,
                  scope='Per-connection source-cut RTL transfer proofs with activation witnesses; module outputs outside the observed hierarchy are unconstrained.',
                  input_capture=capture.record())
    (out/'result.json').write_text(json.dumps(report, indent=2)+'\n')
    return report
