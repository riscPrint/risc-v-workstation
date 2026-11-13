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


def test_package_counts_slowest_and_skip_reasons(tmp_path):
    report = tmp_path / 'x.xml'
    report.write_text('<testsuite><testcase classname="tests.formal.test_x" name="a" time="3"/><testcase classname="tests.formal.test_x" name="b" time="1"><skipped message="Yosys absent"/></testcase><testcase classname="tests.test_debug_x" name="c" time="2"><failure/></testcase></testsuite>')
    text = summary.details(report)
    assert '| formal | 1 | 0 | 1 |' in text
    assert '| debug | 0 | 1 | 0 |' in text
    assert text.index('test_x.a:') < text.index('test_debug_x.c:')
    assert 'Yosys absent' in text


@pytest.mark.parametrize('text,package,counts', [
    ('test result: ok. 28 passed; 0 failed; 2 ignored; 0 measured; 0 filtered out', 'rust', '| rust | 28 | 0 | 2 |'),
    ('# pass 14\n# fail 1\n# skipped 3', 'javascript', '| javascript | 14 | 1 | 3 |'),
])
def test_language_counts(text, package, counts):
    assert counts in summary.language_details(text, package)


def test_missing_language_counts_are_not_a_pass():
    assert 'unavailable' in summary.language_details('build started', 'rust')
