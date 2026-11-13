"""Run the finite queued directory experiment shipped with SpinalChecks."""
import json
import sys
from rvw.common.proc import run_group
from rvw.runs.result import tools_root


def check(profile='mesi', lines=1, requests=1, limit=100000, bug=None):
    if profile not in ('mesi', 'moesi') or not 1 <= lines <= 2 or not 1 <= requests <= 3 or limit < 1:
        raise ValueError('unsupported directory profile or bounds')
    if bug not in (None, 'lost_ack', 'stale_data', 'early_grant', 'starvation', 'cyclic_wait'):
        raise ValueError('unknown directory defect')
    script = tools_root()/'SpinalChecks/coherence/directory.py'
    if not script.is_file():
        return {'status': 'inconclusive', 'reason': 'directory model is not installed in RVW_ROOT'}
    command = [sys.executable, str(script), '--profile', profile, '--lines', str(lines),
               '--requests', str(requests), '--limit', str(limit)]
    if bug:
        command += ['--bug', bug]
    result = run_group(command, timeout=30, capture=True)
    if result.timed_out:
        return {'status': 'inconclusive', 'reason': 'directory model wall timeout'}
    if result.returncode not in (0, 1, 3):
        return {'status': 'inconclusive', 'reason': result.stderr.strip() or 'directory model failed'}
    report = json.loads(result.stdout)
    expected = {'pass': 0, 'fail': 1, 'inconclusive': 3}
    if expected.get(report.get('status')) != result.returncode:
        raise ValueError('directory model verdict and exit disagree')
    return report
