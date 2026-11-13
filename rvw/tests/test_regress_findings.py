import hashlib
import json
import pytest
from rvw.regress.findings import classify, load_findings

pytestmark = pytest.mark.fast


def test_exact_finding_preserves_failure(tmp_path):
    trace = tmp_path / 'trace'
    trace.write_text('observed trace')
    entry = dict(core='example', test='case', trace_sha256=hashlib.sha256(trace.read_bytes()).hexdigest(),
                 observed_status='fail', reason='tohost 3', finding_id='CORE-1', reference='FINDINGS.md')
    catalog = tmp_path / 'known.json'
    catalog.write_text(json.dumps(dict(schema='rvw.known-findings/1', findings=[entry])))
    known = load_findings(catalog)
    row = dict(status='fail', test='case', reason='tohost 3')
    classify(row, 'example', trace, known)
    assert row == dict(status='known_finding', observed_status='fail', test='case', reason='tohost 3',
                       finding_id='CORE-1', finding_reference='FINDINGS.md')
    for status, core, test, content in [('match','example','case','observed trace'),
                                     ('fail','other','case','observed trace'),
                                     ('fail','example','other','observed trace'),
                                     ('fail','example','case','new trace'),
                                     ('mismatch','example','case','observed trace')]:
        trace.write_text(content)
        row = dict(status=status, test=test)
        classify(row, core, trace, known)
        assert row['status'] == status


@pytest.mark.parametrize('status', ['pass', 'match', 'error', 'inconclusive'])
def test_findings_cannot_waive_pass_or_missing_evidence(tmp_path, status):
    catalog = tmp_path / 'known.json'
    catalog.write_text(json.dumps(dict(schema='rvw.known-findings/1', findings=[dict(
        core='example', test='case', trace_sha256='a'*64, observed_status=status,
        finding_id='CORE-1', reference='FINDINGS.md') ])))
    with pytest.raises(ValueError):
        load_findings(catalog)


def test_changed_failure_reason_and_mismatch_are_new(tmp_path):
    trace = tmp_path / 'trace'
    trace.write_text('trace')
    common = dict(core='example', test='case', trace_sha256=hashlib.sha256(trace.read_bytes()).hexdigest(),
                  finding_id='CORE-1', reference='FINDINGS.md')
    row = dict(test='case', status='fail', reason='new failure')
    classify(row, 'example', trace, [dict(common, observed_status='fail', reason='old failure')])
    assert row['status'] == 'fail'
    differences = dict(tval=dict(expected='0x0', actual='0x55'))
    entry = dict(common, observed_status='mismatch', differences=differences)
    row = dict(test='case', status='mismatch', mismatch=dict(differences={'rd_wdata': {}}))
    classify(row, 'example', trace, [entry])
    assert row['status'] == 'mismatch'
    row['mismatch']['differences'] = differences
    classify(row, 'example', trace, [entry])
    assert row['status'] == 'known_finding'
    assert row['observed_status'] == 'mismatch'
