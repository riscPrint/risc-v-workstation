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


def test_installer_reference_tests_install_pytest():
    root = Path(__file__).resolve().parents[2]
    text = (root / '.github/workflows/installer.yml').read_text()
    step = text.split('- name: Check the pinned reference policies')[1]
    assert 'uv sync --locked --extra dev --extra mcp --project rvw' in step
    assert step.index('uv sync') < step.index('python -m pytest')


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
    """An automatic check must not consume private hosted-runner minutes."""
    for name in ('ci.yml', 'conventional.yml', 'nightly.yml'):
        text = (REPO / '.github/workflows' / name).read_text()
        runners = [line.strip() for line in text.splitlines()
                   if line.strip().startswith('runs-on:')]
        assert runners, name
        assert all(line == 'runs-on: [self-hosted, macOS, rvw-local]'
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
