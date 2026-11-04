import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('ci_summary', Path(__file__).resolve().parents[2] / 'scripts/ci-test-summary.py')
summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summary)


@pytest.mark.parametrize('seconds,code', [(299.9, 0), (300, 1), (301, 1)])
def test_fast_budget_and_explicit_counts(tmp_path, seconds, code):
    report = tmp_path / 'report.xml'
    report.write_text(f'<testsuites><testsuite tests="12" failures="0" errors="0" skipped="2" time="{seconds}"/></testsuites>')
    text, actual = summary.summarize(report, 300)
    assert actual == code
    assert '10 passed, 2 skipped, 0 failed, 0 errors' in text


def test_nightly_counts_keep_failures(tmp_path):
    report = tmp_path / 'report.xml'
    report.write_text('<testsuites><testsuite tests="12" failures="1" errors="2" skipped="3" time="900"/></testsuites>')
    text, code = summary.summarize(report)
    assert code == 1
    assert '6 passed, 3 skipped, 1 failed, 2 errors; 900.00 s' in text
    assert 'target' not in text
