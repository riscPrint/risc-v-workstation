"""Check the repository's commit policy with accepted and rejected messages."""
import importlib.util
import re
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "conventional", Path(__file__).resolve().parents[2] / "scripts/check-conventional.py")
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


@pytest.mark.parametrize("message", [
    "ci(tests): add fast checks\n\nRefs: #16",
    "feat(api)!: change schema\n\nBREAKING CHANGE: use v2\nCloses: #41",
])
def test_valid_commit(message):
    assert policy.errors(message) == []


@pytest.mark.parametrize("message", [
    "Update checks", "ci: add checks\n\nRefs: #16",
    "ci(tests): Add checks\n\nRefs: #16",
    "ci(tests): add checks.\n\nRefs: #16",
    "ci(tests): " + "x" * 73 + "\n\nRefs: #16",
    "ci(tests): add checks", "feat(api)!: change schema\n\nRefs: #16",
])
def test_invalid_commit(message):
    assert policy.errors(message)


def test_title_needs_no_footer():
    assert policy.errors("ci(tests): add checks", title=True) == []


def test_installer_workflow_runs_local_runtime_qualification():
    root = Path(__file__).resolve().parents[2]
    text = (root / '.github/workflows/installer.yml').read_text()
    assert text.count('python3 scripts/qualify-install.py --case "$CASE"') == 2
    assert text.count('if: always()') == 2
    assert text.count('actions/upload-artifact@') == 2
    runner = (root / 'scripts/qualify-install.py').read_text()
    assert "'test_reference_mmu.py'" in runner
    assert "'test_platform_policy.py'" in runner
    assert "'--locked'" in runner and "'--extra', 'dev'" in runner


def test_local_ci_uses_committed_python_lock():
    text = (Path(__file__).resolve().parents[2] / 'scripts/ci-local.sh').read_text()
    assert 'lock suite uv sync --locked' in text
    assert "pip install -e" not in text


def test_push_checks_do_not_duplicate_pull_request_checks():
    root = Path(__file__).resolve().parents[2]
    for name in ('ci.yml', 'conventional.yml'):
        text = (root / '.github/workflows' / name).read_text()
        push = text.split('  push:')[1].split('  pull_request:')[0]
        assert 'branches: [main, p1/integration, p2/integration]' in push


def test_long_installer_builds_require_explicit_manual_request():
    root = Path(__file__).resolve().parents[2]
    text = (root / '.github/workflows/installer.yml').read_text()
    job = text.split('  long-install:')[1]
    assert "if: github.event_name == 'workflow_dispatch' && inputs.long_builds && !inputs.cosim_only" in job
    assert 'long_builds:' in text and 'default: false' in text

REPO = Path(__file__).resolve().parents[2]


def test_automatic_workflows_use_only_local_runner():
    """Hosted runners require the single disabled Linux switch."""
    for name in ('ci.yml', 'conventional.yml', 'nightly.yml'):
        text = (REPO / '.github/workflows' / name).read_text()
        runners = [line.strip() for line in text.splitlines()
                   if line.strip().startswith('runs-on:')]
        assert runners, name
        assert all(line in ('runs-on: [self-hosted, macOS, ARM64, rvw-local]', 'runs-on: ubuntu-latest')
                   for line in runners), name
        assert 'cancel-in-progress:' in text
        assert 'scripts/ci-local.sh ' in text


def test_linux_workflows_need_manual_dispatch_and_linux_runner():
    for name in ('installer.yml', 'linux-boot.yml'):
        text = (REPO / '.github/workflows' / name).read_text()
        triggers = text.split('\non:', 1)[1].split('\nconcurrency:', 1)[0]
        assert re.findall(r'^  (\w+):', triggers, re.M) == ['workflow_dispatch'], name
        assert 'runs-on: [self-hosted, Linux, X64, rvw-linux]' in text
        assert 'ubuntu-latest' not in text
        assert 'ubuntu-24.04' not in text


@pytest.mark.parametrize("exit_code", [0, 7])
def test_ci_cleanup_removes_readonly_results_and_keeps_status(tmp_path, exit_code):
    import os
    import subprocess

    prefix = (REPO / 'scripts/ci-local.sh').read_text().split(
        'export RVW_CI_SOURCE=', 1)[0]
    prefix = prefix.replace('root="$(cd "$(dirname "$0")/.." && pwd)"', 'root=' + str(REPO))
    command = prefix + f"""
mkdir -p "$job/results/generation"
printf result > "$job/results/generation/result.json"
chmod 555 "$job/results/generation"
exit {exit_code}
"""
    result = subprocess.run(['bash', '-c', command],
                            env={**os.environ, 'TMPDIR': str(tmp_path)},
                            capture_output=True, text=True)
    assert result.returncode == exit_code, result.stderr
    assert list(tmp_path.iterdir()) == [], result.stderr


def test_messages_bypass_dependency_install():
    text = (REPO / 'scripts/ci-local.sh').read_text()
    assert text.index('if [ "$mode" = messages ]') < text.index('mktemp')
    assert 'uv lock --check --project rvw' in text
    nightly = text.split('  nightly-python)')[1].split('    ;;')[0]
    assert '--component python' in nightly


def test_all_local_nightly_components_run():
    text = (REPO / 'scripts/ci-local.sh').read_text()
    assert 'for component in python scala rust javascript components vip' in text
    assert 'scripts/ci-copy-reports.py' in text
    assert 'nice -n 10' in text


def test_failed_job_reports_survive_cleanup(tmp_path):
    import runpy
    copy = runpy.run_path(str(REPO / 'scripts/ci-copy-reports.py'))['copy_reports']
    source = tmp_path / 'work'
    source.mkdir()
    (source / 'ci-results.xml').write_text('<testsuite tests="1" failures="1"/>')
    destination = tmp_path / 'reports'
    assert copy(source, destination) == 1
    assert (destination / 'ci-results.xml').read_text() == '<testsuite tests="1" failures="1"/>'


def test_all_tiers_have_execution_cases():
    text = (REPO / 'scripts/ci-local.sh').read_text().split('case "$mode" in')[-1]
    assert 'native-light|examples|nightly)' in text
    assert 'python scripts/ci-tiers.py --tier "$mode"' in text


@pytest.mark.parametrize('tier,count', [('native-light', 1), ('examples', 1), ('nightly', 6)])
def test_local_tier_dispatch_without_running_tools(tier, count):
    import os
    import subprocess
    text = (REPO / 'scripts/ci-local.sh').read_text()
    dispatch = 'case "$mode" in' + text.split('case "$mode" in')[-1]
    shell = 'python() { printf "CALLED %s\\n" "$*"; }; mode=' + tier + '\n' + dispatch
    env = {k: v for k, v in os.environ.items() if k != 'CI_COMPONENT'}
    result = subprocess.run(['bash', '-c', shell], env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.count('CALLED ') == count
    assert '--tier ' + tier in result.stdout


def test_linux_ci_has_one_disabled_switch_and_inventory_recipe():
    for name in ('ci.yml', 'nightly.yml'):
        text = (REPO / '.github/workflows' / name).read_text().split('  linux:')[1]
        assert "if: vars.RVW_LINUX_CI == 'enabled'" in text
        assert 'runs-on: ubuntu-latest' in text
        assert 'scripts/ci-linux-plan.py' in text
        assert 'untested' in text.lower()


def test_linux_apt_packages_come_from_inventory():
    import json
    import runpy
    data = json.loads((REPO / 'rvw/src/rvw/doctor/tools.json').read_text())
    packages = runpy.run_path(str(REPO / 'scripts/ci-linux-plan.py'))['packages']
    allowed = {p for tool in data['tools'] for p in tool['install']['apt'].split()}
    for tier in ('fast', 'native-light', 'examples', 'nightly'):
        assert set(packages(tier)) <= allowed
    assert packages('fast') == []


@pytest.mark.fast
def test_ci_uses_python3_without_versioned_alias(tmp_path):
    import os
    import subprocess
    binary = tmp_path / 'python3'
    binary.write_text('#!/bin/sh\necho selected-python3\nexit 73\n')
    binary.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if k not in ('CI_PYTHON', 'RVW_PYTHON')}
    env['PATH'] = str(tmp_path) + ':/usr/bin:/bin'
    env['TMPDIR'] = str(tmp_path)
    result = subprocess.run(['/bin/bash', str(REPO / 'scripts/ci-local.sh'), '--tier', 'fast'],
                            env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 73, result.stderr
    assert 'selected-python3' in result.stdout
    assert 'command not found' not in result.stderr
