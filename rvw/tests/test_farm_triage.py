from pathlib import Path
from rvw.results import SuiteResults, TestEntry, save_results
from rvw.farm.triage import triage


import pytest

pytestmark = pytest.mark.fast


def report(path, tests):
    path.mkdir(exist_ok=True)
    save_results(SuiteResults('run', 'fixture', 'generic', 'small', '2026-11-13T00:00:00Z',
        source=dict(core_rev='a'*40, core_dirty=False), tests=tests), path)


def test_cluster_assertions_and_infrastructure(tmp_path):
    report(tmp_path, [TestEntry('a', 'assert', signature='assert:Unit.scala:12'),
                      TestEntry('b', 'assert', signature='assert:Unit.scala:12'), TestEntry('c', 'error', signature='error:worker')])
    result = triage(tmp_path)
    assert len(result['clusters']) == 2
    assert len(next(c for c in result['clusters'] if c['category'] == 'dut_failure')['members']) == 2
    assert not result['failures_waived']


def test_mismatch_identity_keeps_pc_and_instruction(tmp_path):
    report(tmp_path, [TestEntry(str(i), 'fail', signature='fail:1', extra=dict(details=dict(first_mismatch=dict(pc=pc, instruction='addi'))))
                      for i, pc in enumerate(['0x10', '0x20'])])
    assert len(triage(tmp_path)['clusters']) == 2


def test_empty_report_does_not_claim_checks(tmp_path):
    assert triage(tmp_path)['status'] == 'no_checks'


def test_recorded_commit_range_and_regression_diff(tmp_path):
    import json
    base, candidate = tmp_path / 'base', tmp_path / 'candidate'
    identity = dict(elf_sha256='d'*64, options={})
    report(base, [TestEntry('test', 'pass', seed=1, extra=identity)])
    report(candidate, [TestEntry('test', 'assert', seed=1, signature='assert:Unit.scala:12', extra=identity)])
    path = candidate / 'results.json'
    data = json.loads(path.read_text())
    data['source']['core_rev'] = 'b'*40
    path.write_text(json.dumps(data))
    result = triage(candidate, baseline=base)
    assert result['clusters'][0]['commit_ranges'] == ['a'*40 + '..' + 'b'*40]
    assert result['diff']['new_failures']


def test_unknown_details_keep_assertion_identity(tmp_path):
    report(tmp_path, [TestEntry('test', 'assert', signature='assert:Unit.scala:12', extra=dict(details=None))])
    assert triage(tmp_path)['clusters'][0]['signature'] == 'assert:Unit.scala:12'
