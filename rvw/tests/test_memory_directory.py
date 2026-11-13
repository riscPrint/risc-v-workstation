import json
from pathlib import Path
import subprocess
import sys
import pytest
from rvw.common.proc import run_group


def run(*args):
    root = Path(__file__).resolve().parents[2]
    p = run_group([sys.executable, str(root/'SpinalChecks/coherence/directory.py'), *args], timeout=20,
                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return json.loads(p.stdout)


@pytest.mark.parametrize('profile', ['mesi', 'moesi'])
def test_directory_profiles_with_explicit_queues(profile):
    result = run('--profile', profile)
    assert result['status'] == 'pass', result
    assert result['bounds']['queue_capacity_per_channel'] == 1
    assert result['independent_model_crosscheck'] == 'not_run'


@pytest.mark.parametrize('bug', ['lost_ack', 'stale_data', 'early_grant', 'starvation', 'cyclic_wait'])
def test_seeded_directory_defects(bug):
    result = run('--profile', 'moesi', '--bug', bug)
    assert result['status'] == 'fail', result


def test_repeated_requests_and_two_active_lines_report_budget():
    assert run('--requests', '2', '--limit', '1')['status'] == 'inconclusive'
    result = run('--lines', '2', '--limit', '10000')
    assert result['status'] == 'pass', result
    assert run('--profile', 'moesi', '--requests', '2')['status'] == 'pass'


def test_public_directory_api_matches_native_script():
    from rvw.memory.directory_model import check
    assert check('moesi', requests=2)['status'] == 'pass'
    assert check('mesi', bug='cyclic_wait')['status'] == 'fail'
    assert check('mesi', limit=1)['status'] == 'inconclusive'
