"""Check the repository's commit policy with accepted and rejected messages."""
import importlib.util
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
        assert triggers.strip() == 'workflow_dispatch:', name
        assert 'runs-on: [self-hosted, Linux, X64, rvw-linux]' in text
        assert 'ubuntu-latest' not in text
        assert 'ubuntu-24.04' not in text
