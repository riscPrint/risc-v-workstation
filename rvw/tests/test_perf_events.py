import gzip

import pytest

from perf_fixtures import analyze
from rvw.perf.analysis import render
from rvw.perf.kanata import read


def log(tmp_path, body):
    path = tmp_path / 'events.log'
    path.write_text('Kanata\t0004\nC=\t0\n' + body.replace('|', '\t') + '\n')
    return path


def test_samples_overlap_inference_unknown_and_commits(tmp_path):
    path = log(tmp_path, '''I|0|0|0
I|1|1|0
I|2|2|0
S|0|0|waiting
W|1|0|0
C|1
#rvw|1|stall|issue|operand_wait|measured
#rvw|1|stall|issue|operand_wait|measured
#rvw|1|stall|memory|load_miss|measured
#rvw|1|stall|rob|rob_full|inferred
#rvw|1|replay|1|ordering|measured
C|1
#rvw|1|stall|lsq|lsq_full|inferred
C|1
#rvw|1|stall|issue|structural|measured
#rvw|1|commit|0|architectural
R|0|0|0
#rvw|1|commit|1|predicated_off
R|1|1|0
C|1
R|2|2|0
C|5''')
    report = analyze(path)
    stalls = report['stall_causes']
    assert stalls['measured_cycles'] == 2
    assert stalls['measured_zero_retirement_cycles'] == 1
    assert stalls['overlap_cycles'] == 1
    assert stalls['overlaps'] == [{'causes': [{'scope': 'issue', 'cause': 'operand_wait'},
                                            {'scope': 'memory', 'cause': 'load_miss'}], 'cycles': 1}]
    assert stalls['unknown_zero_retirement_cycles'] == 7
    assert stalls['unknown_intervals'] == 3
    assert stalls['longest_unknown'][0] == {'start': 5, 'end': 10}
    assert len(stalls['by_cause']) == 5
    assert report['summary']['instret'] == 3
    assert report['commit_kinds']['physical_observed'] == 2
    assert report['commit_kinds']['architectural_observed'] == 1
    assert report['commit_kinds']['predicated_off_observed'] == 1
    assert report['commit_kinds']['unknown'] == 1
    assert report['commit_kinds']['architectural_total'] is None
    assert report['replays'] == [{'cause': 'ordering', 'evidence': 'measured', 'events': 1}]
    text = render(report)
    assert 'inferred lsq lsq_full' in text
    assert 'Measured stall cycles: 2' in text
    gz = tmp_path / 'events.log.gz'
    with gzip.open(gz, 'wt') as f:
        f.write(path.read_text())
    assert analyze(gz)['stall_causes'] == stalls


def test_no_events_never_implies_known_zero_stalls(tmp_path):
    path = log(tmp_path, 'I|0|0|0\nS|0|0|operand_wait\nC|100000000')
    report = analyze(path, window=1000000)
    assert report['stall_causes']['measured_cycles'] == 0
    assert report['stall_causes']['unknown_zero_retirement_cycles'] == 100000001
    assert report['stall_causes']['by_cause'] == []
    assert report['stall_causes']['unknown_intervals'] == 1


def test_fully_classified_commits(tmp_path):
    path = log(tmp_path, 'I|0|0|0\n#rvw|1|commit|0|predicated_off\nR|0|0|0')
    report = analyze(path)
    assert report['commit_kinds']['architectural_total'] == 0
    assert report['summary']['instret'] == 1


@pytest.mark.parametrize('body', [
    '#rvw|2|stall|q|operand_wait|measured',
    '#rvw|1|stall|q|operand_wait|guess',
    '#rvw|1|stall||operand_wait|measured',
    '#rvw|1|stall|q||measured',
    '#rvw|1|stall|q|operand_wait',
    '#rvw|1|replay|missing|ordering|measured',
    'I|0|0|0\nR|0|0|0\n#rvw|1|replay|0|ordering|measured',
    'I|0|0|0\n#rvw|1|commit|0|architectural',
    'I|0|0|0\n#rvw|1|commit|0|physical',
    'I|0|0|0\n#rvw|1|commit|0|architectural\nR|0|0|1',
    'I|0|0|0\n#rvw|1|commit|0|architectural\nC|1\nR|0|0|0',
    'I|0|0|0\n#rvw|1|commit|0|architectural\n#rvw|1|commit|0|architectural\nR|0|0|0',
    '#rvw|1|typo|q|cause|measured',
])
def test_bad_extensions_refuse(tmp_path, body):
    with pytest.raises(ValueError):
        read(log(tmp_path, body))
