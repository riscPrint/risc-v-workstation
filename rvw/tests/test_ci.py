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
